from flask import Flask, abort, request

from .config import Config, load_config
from .github_client import create_github_client, set_pr_labels
from .handlers import WebhookHandlers
from .pow import pow_digest, verify_pow_solution, verify_signature
from .store import ChallengeStore, challenge_key


def create_app(config: Config | None = None) -> Flask:
    config = config or load_config()

    app = Flask(__name__)
    github = create_github_client(config.github_token)
    challenge_store = ChallengeStore()
    handlers = WebhookHandlers(github, challenge_store, config.pow_difficulty)

    @app.route("/webhook", methods=["POST"])
    def github_webhook():
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(request.data, signature, config.webhook_secret):
            abort(401, "Signature verification failed.")

        payload = request.get_json(force=True)
        event_type = request.headers.get("X-GitHub-Event", "")

        print(f"[WEBHOOK] event={event_type!r} action={payload.get('action')!r}")

        if event_type == "pull_request" and payload.get("action") == "opened":
            handlers.handle_pull_request_opened(payload)
        elif event_type == "issue_comment" and payload.get("action") == "created":
            handlers.handle_issue_comment_created(payload)

        return "OK", 200

    @app.route("/health", methods=["GET"])
    def health():
        return {"status": "ok", "pending_challenges": challenge_store.count()}, 200

    @app.route("/challenges", methods=["GET"])
    def list_challenges():
        """Dev-only: list all active challenges (remove in production)."""
        return challenge_store.as_dict(), 200

    @app.route("/solve", methods=["POST"])
    def solve():
        """
        Accept a PoW solution directly via curl (no GitHub comment needed).

        Usage:
            curl -s -X POST http://localhost:5000/solve \
                 -H "Content-Type: application/json" \
                 -d '{"repo":"owner/repo","pr_number":1,"solution":"12345"}'
        """
        data = request.get_json(force=True) or {}
        repo_name = data.get("repo", "").strip()
        pr_number = data.get("pr_number")
        solution = str(data.get("solution", "")).strip()

        if not repo_name or pr_number is None or not solution:
            return {"error": "repo, pr_number and solution are required"}, 400

        try:
            pr_number = int(pr_number)
        except (TypeError, ValueError):
            return {"error": "pr_number must be an integer"}, 400

        key = challenge_key(repo_name, pr_number)
        challenge = challenge_store.get(repo_name, pr_number)
        if not challenge:
            return {
                "error": f"No active challenge for {key}. Open a PR first so the bot generates one."
            }, 404

        nonce = challenge.nonce
        target = challenge.target
        valid = verify_pow_solution(nonce, target, solution)
        digest = pow_digest(nonce, solution)

        print(f"[/solve] {key} solution={solution!r} hash={digest} valid={valid}")

        try:
            repo = github.get_repo(repo_name)
            pull_request = repo.get_pull(pr_number)

            if valid:
                challenge_store.pop(repo_name, pr_number)
                set_pr_labels(pull_request, repo, "verified-human")
                print(f"[/solve] ✅ {key} → verified-human")
                return {
                    "result": "verified",
                    "label": "verified-human",
                    "hash": digest,
                    "message": f"PR #{pr_number} is now labelled verified-human ✅",
                }, 200

            set_pr_labels(pull_request, repo, "spam-blocked")
            print(f"[/solve] ❌ {key} → spam-blocked")
            return {
                "result": "invalid",
                "label": "spam-blocked",
                "hash": digest,
                "target": target,
                "message": f'Hash does not start with "{target}". Try again.',
            }, 400

        except Exception as exc:
            print(f"[/solve] ERROR: {exc}")
            return {"error": str(exc)}, 500

    return app
