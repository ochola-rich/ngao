import os
import hmac
import hashlib
import json
import secrets
import time
from flask import Flask, request, abort
from github import Github, GithubException
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Configuration from environment variables
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
POW_DIFFICULTY = int(os.getenv('POW_DIFFICULTY', '4'))  # number of leading zeros required

if not GITHUB_TOKEN:
    print("Error: GITHUB_TOKEN environment variable not set.")
    exit(1)
if not WEBHOOK_SECRET:
    print("Error: WEBHOOK_SECRET environment variable not set.")
    exit(1)

g = Github(GITHUB_TOKEN)

# In-memory store: maps "owner/repo#pr_number" -> {"nonce": ..., "target": ..., "created_at": ...}
# In production this should be Redis or a DB; for the hackathon demo in-memory is fine.
pending_challenges: dict = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def verify_signature(payload_body: bytes, signature_header: str) -> bool:
    """Verify that the payload was sent from GitHub using HMAC-SHA256."""
    if not signature_header:
        return False
    parts = signature_header.split('=', 1)
    if len(parts) != 2 or parts[0] != 'sha256':
        return False
    sha_name, signature = parts
    mac = hmac.new(WEBHOOK_SECRET.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)


def generate_pow_challenge(difficulty: int = POW_DIFFICULTY) -> tuple[str, str]:
    """
    Generate a hashcash-style PoW challenge.
    Returns (nonce, target_prefix) where a valid solution hash must start with target_prefix.
    """
    nonce = secrets.token_hex(16)
    target = "0" * difficulty
    return nonce, target


def verify_pow_solution(nonce: str, target: str, solution: str) -> bool:
    """
    Verify that sha256(nonce + ":" + solution) starts with `target`.
    The contributor runs: solve-pow <nonce> <difficulty> and gets back a solution string.
    """
    combined = f"{nonce}:{solution}"
    digest = hashlib.sha256(combined.encode('utf-8')).hexdigest()
    return digest.startswith(target)


def challenge_key(repo_name: str, pr_number: int) -> str:
    return f"{repo_name}#{pr_number}"


def get_or_create_label(repo, name: str, color: str, description: str):
    """Ensure a label exists on the repo, create it if not."""
    try:
        return repo.get_label(name)
    except GithubException:
        return repo.create_label(name, color, description)


def set_pr_labels(pull_request, repo, label_name: str):
    """Remove all bot-managed labels and apply the given one."""
    managed = {"pending-verification", "verified-human", "spam-blocked"}
    current = {lbl.name for lbl in pull_request.get_labels()}
    for lbl in current & managed:
        pull_request.remove_from_labels(lbl)
    get_or_create_label(
        repo,
        label_name,
        {"pending-verification": "f29513",
         "verified-human": "0e8a16",
         "spam-blocked": "d93f0b"}.get(label_name, "cccccc"),
        {"pending-verification": "Awaiting PoW verification",
         "verified-human": "Human contributor verified via PoW",
         "spam-blocked": "Failed or invalid PoW verification"}.get(label_name, ""),
    )
    pull_request.add_to_labels(label_name)


# ---------------------------------------------------------------------------
# Webhook entry point
# ---------------------------------------------------------------------------

@app.route('/webhook', methods=['POST'])
def github_webhook():
    signature = request.headers.get('X-Hub-Signature-256', '')
    if not verify_signature(request.data, signature):
        abort(401, "Signature verification failed.")

    payload = request.get_json(force=True)
    event_type = request.headers.get('X-GitHub-Event', '')

    # DEBUG — log every incoming event so we can see what GitHub sends
    print(f"[WEBHOOK] event={event_type!r} action={payload.get('action')!r}")

    if event_type == 'pull_request' and payload.get('action') == 'opened':
        handle_pull_request_opened(payload)

    elif event_type == 'issue_comment' and payload.get('action') == 'created':
        handle_issue_comment_created(payload)

    return 'OK', 200


# ---------------------------------------------------------------------------
# PR opened — generate challenge, comment, label
# ---------------------------------------------------------------------------

def handle_pull_request_opened(payload):
    repo_name = payload['repository']['full_name']
    pr_number = payload['pull_request']['number']
    pr_url    = payload['pull_request']['html_url']
    author    = payload['pull_request']['user']['login']

    print(f"[PR opened] {repo_name}#{pr_number} by @{author} — {pr_url}")

    try:
        repo = g.get_repo(repo_name)
        pull_request = repo.get_pull(pr_number)

        # Generate a fresh PoW challenge for this PR
        nonce, target = generate_pow_challenge()
        key = challenge_key(repo_name, pr_number)
        pending_challenges[key] = {
            "nonce": nonce,
            "target": target,
            "created_at": time.time(),
            "pr_number": pr_number,
            "repo": repo_name,
        }

        print(f"[PoW] Challenge for {key}: nonce={nonce} target={target}")

        comment = f"""## 🛡️ Anti-Spam Verification Required

Hey @{author}! This repo uses **Proof-of-Work** to prevent AI-generated PR spam.

> This is inspired by Bitcoin's original hashcash mechanism — a tiny amount of CPU work that costs a bot farm dearly at scale but takes a human seconds.

### Your challenge

**Nonce:** `{nonce}`
**Difficulty:** find a string so that `SHA-256("{nonce}:<your_string>")` starts with `{target}`

### Option A — one-liner (Linux/macOS)

```bash
curl -fsSL https://raw.githubusercontent.com/{repo_name.split('/')[0]}/ngao/main/solve_pow.py | python3 - {nonce} {POW_DIFFICULTY}
```

### Option B — download the solver

```bash
curl -O https://raw.githubusercontent.com/{repo_name.split('/')[0]}/ngao/main/solve_pow.py
python3 solve_pow.py {nonce} {POW_DIFFICULTY}
```

### Option C — solve it manually

```bash
python3 -c "
import hashlib, itertools, string
nonce='{nonce}'; target='{target}'
for i in itertools.count():
    s=str(i)
    if hashlib.sha256(f'{{nonce}}:{{s}}'.encode()).hexdigest().startswith(target):
        print(s); break
"
```

**Reply to this comment with:** `pow-solution: <your_solution_string>`

Once verified, your PR will be labelled ✅ **verified-human** and moved into the review queue.

_Challenge expires in 24 hours. Timeout or invalid solution will label this PR `spam-blocked`._"""

        pull_request.create_issue_comment(comment)
        set_pr_labels(pull_request, repo, "pending-verification")
        print(f"[PR opened] Challenge posted and label set for {repo_name}#{pr_number}")

    except Exception as e:
        print(f"[ERROR] handle_pull_request_opened: {e}")


# ---------------------------------------------------------------------------
# Comment created — look for PoW solution, verify, update label
# ---------------------------------------------------------------------------

def handle_issue_comment_created(payload):
    # issue_comment events fire on both issues AND PRs; filter to PRs only
    if 'pull_request' not in payload.get('issue', {}):
        return

    repo_name  = payload['repository']['full_name']
    pr_number  = payload['issue']['number']
    commenter  = payload['comment']['user']['login']
    body       = payload['comment']['body'].strip()

    # Ignore comments from ourselves to avoid loops
    bot_login = g.get_user().login
    if commenter == bot_login:
        return

    key = challenge_key(repo_name, pr_number)
    challenge = pending_challenges.get(key)

    if not challenge:
        # No active challenge for this PR — nothing to do
        return

    # Parse "pow-solution: <value>"
    solution = None
    for line in body.splitlines():
        line = line.strip()
        if line.lower().startswith('pow-solution:'):
            solution = line.split(':', 1)[1].strip()
            break

    if solution is None:
        # Comment doesn't contain a solution attempt — ignore
        return

    print(f"[PoW] Solution attempt on {key} by @{commenter}: '{solution}'")

    nonce  = challenge['nonce']
    target = challenge['target']
    valid  = verify_pow_solution(nonce, target, solution)

    try:
        repo = g.get_repo(repo_name)
        pull_request = repo.get_pull(pr_number)

        if valid:
            pending_challenges.pop(key, None)
            set_pr_labels(pull_request, repo, "verified-human")
            pull_request.create_issue_comment(
                f"✅ **Verified!** PoW solution accepted for @{commenter}.\n\n"
                f"Hash: `{hashlib.sha256(f'{nonce}:{solution}'.encode()).hexdigest()}`\n\n"
                f"This PR is now labelled **verified-human** and is ready for maintainer review."
            )
            print(f"[PoW] ✅ Verified {key} — label → verified-human")
        else:
            set_pr_labels(pull_request, repo, "spam-blocked")
            pull_request.create_issue_comment(
                f"❌ **Invalid solution** from @{commenter}.\n\n"
                f"`SHA-256(\"{nonce}:{solution}\")` does not start with `{target}`.\n\n"
                f"Please try again or re-run the solver script. This PR has been labelled **spam-blocked**."
            )
            print(f"[PoW] ❌ Invalid solution for {key} — label → spam-blocked")

    except Exception as e:
        print(f"[ERROR] handle_issue_comment_created: {e}")


# ---------------------------------------------------------------------------
# Debug/health endpoints
# ---------------------------------------------------------------------------

@app.route('/health', methods=['GET'])
def health():
    return {'status': 'ok', 'pending_challenges': len(pending_challenges)}, 200


@app.route('/challenges', methods=['GET'])
def list_challenges():
    """Dev-only: list all active challenges (remove in production)."""
    return pending_challenges, 200


# ---------------------------------------------------------------------------
# Local solve endpoint — submit solution via curl instead of a GitHub comment
# ---------------------------------------------------------------------------

@app.route('/solve', methods=['POST'])
def solve():
    """
    Accept a PoW solution directly via curl (no GitHub comment needed).

    Usage:
        curl -s -X POST http://localhost:5000/solve \
             -H "Content-Type: application/json" \
             -d '{"repo":"owner/repo","pr_number":1,"solution":"12345"}'
    """
    data = request.get_json(force=True) or {}
    repo_name = data.get('repo', '').strip()
    pr_number  = data.get('pr_number')
    solution   = str(data.get('solution', '')).strip()

    if not repo_name or pr_number is None or not solution:
        return {'error': 'repo, pr_number and solution are required'}, 400

    try:
        pr_number = int(pr_number)
    except (TypeError, ValueError):
        return {'error': 'pr_number must be an integer'}, 400

    key = challenge_key(repo_name, pr_number)
    challenge = pending_challenges.get(key)

    if not challenge:
        return {
            'error': f'No active challenge for {key}. '
                     'Open a PR first so the bot generates one.'
        }, 404

    nonce  = challenge['nonce']
    target = challenge['target']
    valid  = verify_pow_solution(nonce, target, solution)

    digest = hashlib.sha256(f"{nonce}:{solution}".encode()).hexdigest()
    print(f"[/solve] {key} solution={solution!r} hash={digest} valid={valid}")

    try:
        repo = g.get_repo(repo_name)
        pull_request = repo.get_pull(pr_number)

        if valid:
            pending_challenges.pop(key, None)
            set_pr_labels(pull_request, repo, "verified-human")
            print(f"[/solve] ✅ {key} → verified-human")
            return {
                'result': 'verified',
                'label':  'verified-human',
                'hash':   digest,
                'message': f'PR #{pr_number} is now labelled verified-human ✅'
            }, 200
        else:
            set_pr_labels(pull_request, repo, "spam-blocked")
            print(f"[/solve] ❌ {key} → spam-blocked")
            return {
                'result':  'invalid',
                'label':   'spam-blocked',
                'hash':    digest,
                'target':  target,
                'message': f'Hash does not start with "{target}". Try again.'
            }, 400

    except Exception as e:
        print(f"[/solve] ERROR: {e}")
        return {'error': str(e)}, 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)