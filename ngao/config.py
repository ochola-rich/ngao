import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    github_token: str
    webhook_secret: str
    pow_difficulty: int = 4


def load_config() -> Config:
    load_dotenv()

    github_token = os.getenv("GITHUB_TOKEN")
    webhook_secret = os.getenv("WEBHOOK_SECRET")
    pow_difficulty = int(os.getenv("POW_DIFFICULTY", "4"))

    if not github_token:
        raise RuntimeError("GITHUB_TOKEN environment variable not set.")
    if not webhook_secret:
        raise RuntimeError("WEBHOOK_SECRET environment variable not set.")

    return Config(
        github_token=github_token,
        webhook_secret=webhook_secret,
        pow_difficulty=pow_difficulty,
    )
