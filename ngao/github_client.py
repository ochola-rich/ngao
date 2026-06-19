from github import Github, GithubException


MANAGED_LABELS = {"pending-verification", "verified-human", "spam-blocked"}

LABEL_METADATA = {
    "pending-verification": {
        "color": "f29513",
        "description": "Awaiting PoW verification",
    },
    "verified-human": {
        "color": "0e8a16",
        "description": "Human contributor verified via PoW",
    },
    "spam-blocked": {
        "color": "d93f0b",
        "description": "Failed or invalid PoW verification",
    },
}


def create_github_client(token: str) -> Github:
    return Github(token)


def get_or_create_label(repo, name: str, color: str, description: str):
    """Ensure a label exists on the repo, create it if not."""
    try:
        return repo.get_label(name)
    except GithubException:
        return repo.create_label(name, color, description)


def set_pr_labels(pull_request, repo, label_name: str) -> None:
    """Remove all bot-managed labels and apply the given one."""
    current = {label.name for label in pull_request.get_labels()}
    for label in current & MANAGED_LABELS:
        pull_request.remove_from_labels(label)

    metadata = LABEL_METADATA.get(
        label_name,
        {"color": "cccccc", "description": ""},
    )
    get_or_create_label(
        repo,
        label_name,
        metadata["color"],
        metadata["description"],
    )
    pull_request.add_to_labels(label_name)
