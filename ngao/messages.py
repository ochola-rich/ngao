def challenge_comment(author: str, repo_name: str, nonce: str, target: str, difficulty: int) -> str:
    owner = repo_name.split("/")[0]
    return f"""## 🛡️ Anti-Spam Verification Required

Hey @{author}! This repo uses **Proof-of-Work** to prevent AI-generated PR spam.

> This is inspired by Bitcoin's original hashcash mechanism — a tiny amount of CPU work that costs a bot farm dearly at scale but takes a human seconds.

### Your challenge

**Nonce:** `{nonce}`
**Difficulty:** find a string so that `SHA-256("{nonce}:<your_string>")` starts with `{target}`

### Option A — one-liner (Linux/macOS)

```bash
curl -fsSL https://raw.githubusercontent.com/{owner}/ngao/main/solve_pow.py | python3 - {nonce} {difficulty}
```

### Option B — download the solver

```bash
curl -O https://raw.githubusercontent.com/{owner}/ngao/main/solve_pow.py
python3 solve_pow.py {nonce} {difficulty}
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


def verified_comment(commenter: str, digest: str) -> str:
    return (
        f"✅ **Verified!** PoW solution accepted for @{commenter}.\n\n"
        f"Hash: `{digest}`\n\n"
        "This PR is now labelled **verified-human** and is ready for maintainer review."
    )


def invalid_solution_comment(commenter: str, nonce: str, solution: str, target: str) -> str:
    return (
        f"❌ **Invalid solution** from @{commenter}.\n\n"
        f"`SHA-256(\"{nonce}:{solution}\")` does not start with `{target}`.\n\n"
        "Please try again or re-run the solver script. This PR has been labelled **spam-blocked**."
    )
