import time
from dataclasses import dataclass, asdict


@dataclass
class Challenge:
    nonce: str
    target: str
    created_at: float
    pr_number: int
    repo: str

    def to_dict(self) -> dict:
        return asdict(self)


def challenge_key(repo_name: str, pr_number: int) -> str:
    return f"{repo_name}#{pr_number}"


class ChallengeStore:
    """In-memory challenge store. Swap this for Redis or a DB in production."""

    def __init__(self) -> None:
        self._challenges: dict[str, Challenge] = {}

    def create(self, repo_name: str, pr_number: int, nonce: str, target: str) -> Challenge:
        challenge = Challenge(
            nonce=nonce,
            target=target,
            created_at=time.time(),
            pr_number=pr_number,
            repo=repo_name,
        )
        self._challenges[challenge_key(repo_name, pr_number)] = challenge
        return challenge

    def get(self, repo_name: str, pr_number: int) -> Challenge | None:
        return self._challenges.get(challenge_key(repo_name, pr_number))

    def pop(self, repo_name: str, pr_number: int) -> Challenge | None:
        return self._challenges.pop(challenge_key(repo_name, pr_number), None)

    def count(self) -> int:
        return len(self._challenges)

    def as_dict(self) -> dict:
        return {key: challenge.to_dict() for key, challenge in self._challenges.items()}
