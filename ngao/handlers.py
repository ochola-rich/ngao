from github import Github

from .github_client import set_pr_labels
from .messages import challenge_comment, invalid_solution_comment, verified_comment
from .pow import generate_pow_challenge, pow_digest, verify_pow_solution
from .store import ChallengeStore, challenge_key


def parse_pow_solution(body: str) -> str | None:
    for line in body.splitlines():
        line = line.strip()
        if line.lower().startswith("pow-solution:"):
            return line.split(":", 1)[1].strip()
    return None


class WebhookHandlers:
    def __init__(self, github: Github, challenge_store: ChallengeStore, pow_difficulty: int) -> None:
        self.github = github
        self.challenge_store = challenge_store
        self.pow_difficulty = pow_difficulty

    def handle_pull_request_opened(self, payload: dict) -> None:
        repo_name = payload["repository"]["full_name"]
        pr_number = payload["pull_request"]["number"]
        pr_url = payload["pull_request"]["html_url"]
        author = payload["pull_request"]["user"]["login"]

        print(f"[PR opened] {repo_name}#{pr_number} by @{author} — {pr_url}")

        try:
            repo = self.github.get_repo(repo_name)
            pull_request = repo.get_pull(pr_number)

            nonce, target = generate_pow_challenge(self.pow_difficulty)
            self.challenge_store.create(repo_name, pr_number, nonce, target)

            key = challenge_key(repo_name, pr_number)
            print(f"[PoW] Challenge for {key}: nonce={nonce} target={target}")

            pull_request.create_issue_comment(
                challenge_comment(author, repo_name, nonce, target, self.pow_difficulty)
            )
            set_pr_labels(pull_request, repo, "pending-verification")
            print(f"[PR opened] Challenge posted and label set for {key}")

        except Exception as exc:
            print(f"[ERROR] handle_pull_request_opened: {exc}")

    def handle_issue_comment_created(self, payload: dict) -> None:
        if "pull_request" not in payload.get("issue", {}):
            return

        repo_name = payload["repository"]["full_name"]
        pr_number = payload["issue"]["number"]
        commenter = payload["comment"]["user"]["login"]
        body = payload["comment"]["body"].strip()

        bot_login = self.github.get_user().login
        if commenter == bot_login:
            return

        challenge = self.challenge_store.get(repo_name, pr_number)
        if not challenge:
            return

        solution = parse_pow_solution(body)
        if solution is None:
            return

        key = challenge_key(repo_name, pr_number)
        print(f"[PoW] Solution attempt on {key} by @{commenter}: '{solution}'")

        nonce = challenge.nonce
        target = challenge.target
        valid = verify_pow_solution(nonce, target, solution)
        digest = pow_digest(nonce, solution)

        try:
            repo = self.github.get_repo(repo_name)
            pull_request = repo.get_pull(pr_number)

            if valid:
                self.challenge_store.pop(repo_name, pr_number)
                set_pr_labels(pull_request, repo, "verified-human")
                pull_request.create_issue_comment(verified_comment(commenter, digest))
                print(f"[PoW] ✅ Verified {key} — label → verified-human")
            else:
                set_pr_labels(pull_request, repo, "spam-blocked")
                pull_request.create_issue_comment(
                    invalid_solution_comment(commenter, nonce, solution, target)
                )
                print(f"[PoW] ❌ Invalid solution for {key} — label → spam-blocked")

        except Exception as exc:
            print(f"[ERROR] handle_issue_comment_created: {exc}")
