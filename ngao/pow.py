import hashlib
import hmac
import secrets


def verify_signature(payload_body: bytes, signature_header: str, webhook_secret: str) -> bool:
    """Verify that the payload was sent from GitHub using HMAC-SHA256."""
    if not signature_header:
        return False

    parts = signature_header.split("=", 1)
    if len(parts) != 2 or parts[0] != "sha256":
        return False

    signature = parts[1]
    mac = hmac.new(
        webhook_secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    )
    return hmac.compare_digest(mac.hexdigest(), signature)


def generate_pow_challenge(difficulty: int) -> tuple[str, str]:
    """
    Generate a hashcash-style PoW challenge.
    Returns (nonce, target_prefix) where a valid solution hash must start with target_prefix.
    """
    nonce = secrets.token_hex(16)
    target = "0" * difficulty
    return nonce, target


def pow_digest(nonce: str, solution: str) -> str:
    return hashlib.sha256(f"{nonce}:{solution}".encode("utf-8")).hexdigest()


def verify_pow_solution(nonce: str, target: str, solution: str) -> bool:
    """
    Verify that sha256(nonce + ":" + solution) starts with `target`.
    The contributor runs: solve-pow <nonce> <difficulty> and gets back a solution string.
    """
    return pow_digest(nonce, solution).startswith(target)
