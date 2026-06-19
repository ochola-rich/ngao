# Ngao — PoW PR Triage Bot

**Ngao** (*shield* in Swahili) is a GitHub webhook server that stops AI-generated PR spam dead using **Proof-of-Work** — the same hashcash primitive that inspired Bitcoin's mining algorithm.

When a PR is opened, the bot posts a cryptographic challenge. Only a contributor who actually runs a solver (2 seconds of CPU) gets their PR labelled **verified-human** and enters the review queue. Bots, scripts, and AI-spam farms get **spam-blocked** automatically.

---

## How it works

```
PR opened
    │
    ▼
Bot posts PoW challenge (nonce + difficulty target)
    │
    ▼
Contributor runs: python3 solve_pow.py <nonce> <difficulty>
    │
    ▼
Contributor replies: "pow-solution: <answer>"
    │
    ├─ SHA-256(nonce:answer) starts with 0000? ──► ✅ verified-human label
    │
    └─ Invalid? ─────────────────────────────────► ❌ spam-blocked label
```

The PoW is **hashcash-style**: find a string `S` such that `SHA-256("<nonce>:<S>")` starts with N zeros.  
Default difficulty is 4 leading zeros (~65,000 attempts on average, ~2 seconds on a laptop). A bot farm that opens 1,000 PRs/day would need ~2,000 CPU-seconds per day — not free.

---

## Features

- Listens for `pull_request.opened` → generates unique per-PR challenge, posts instructions, labels `pending-verification`
- Listens for `issue_comment.created` → detects `pow-solution: <value>` replies, verifies hash, flips label
- Standalone `solve_pow.py` solver contributors run locally (no dependencies)
- HMAC-SHA256 webhook signature verification
- `GET /health` and `GET /challenges` debug endpoints

## Project layout

- `main.py` — application entrypoint
- `ngao/app.py` — Flask route wiring
- `ngao/config.py` — environment configuration
- `ngao/handlers.py` — GitHub webhook event handling
- `ngao/pow.py` — signature and proof-of-work helpers
- `ngao/store.py` — pending challenge storage
- `ngao/github_client.py` — GitHub API label helpers
- `ngao/messages.py` — GitHub comment templates
- `solve_pow.py` — standalone contributor solver

---

## Prerequisites

- Python 3.10+
- GitHub Personal Access Token (PAT) with `repo` scope (or a GitHub App)
- A public-facing URL — use [ngrok](https://ngrok.com/) for local dev: `ngrok http 5000`

---

## Installation

```bash
git clone https://github.com/ochola-rich/ngao.git
cd ngao
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file in the project root:

```env
GITHUB_TOKEN=ghp_your_personal_access_token
WEBHOOK_SECRET=your_chosen_random_secret
POW_DIFFICULTY=4   # optional, default is 4 (increase for stricter gating)
```

---

## Running locally

```bash
source venv/bin/activate
python main.py
# Server starts on http://0.0.0.0:5000
```

In a second terminal:

```bash
ngrok http 5000
# Note the https://xxxx.ngrok.io URL
```

---

## GitHub Webhook Setup

1. Go to your repo **Settings → Webhooks → Add webhook**
2. **Payload URL:** `https://xxxx.ngrok.io/webhook`
3. **Content type:** `application/json`
4. **Secret:** same value as `WEBHOOK_SECRET` in your `.env`
5. **Events:** select *Let me select individual events* → check **Pull requests** and **Issue comments**
6. Click **Add webhook**

---

## Contributor workflow

When you open a PR, you'll see a bot comment like this:

> 🛡️ Anti-Spam Verification Required
> **Nonce:** `a3f8c1d2e4b56789abcd`
> Reply with: `pow-solution: <solution>`

Run the solver:

```bash
python3 solve_pow.py a3f8c1d2e4b56789abcd 4
# ✅ Solution found in 1.3s after 52,847 attempts!
# pow-solution: 52847
```

Paste `pow-solution: 52847` as a PR comment. The bot verifies instantly and labels your PR ✅ **verified-human**.

---

## Why Proof-of-Work?

- **Zero friction for humans** — 2 seconds of CPU is imperceptible
- **High cost for spam farms** — 1,000 PRs/day = ~33 CPU-minutes of wasted compute
- **Traceable to Bitcoin's lineage** — hashcash was Satoshi's direct inspiration for Bitcoin mining
- **No identity required** — no accounts, no OAuth, no Nostr keys (Phase 2 roadmap)

---

## Roadmap

- [ ] Nostr private-key signing as an alternative to PoW (NIP-01)
- [ ] Lightning identity verification
- [ ] Redis-backed challenge store for multi-instance deployments
- [ ] GitHub Actions workflow for zero-infra deployment
- [ ] Configurable challenge expiry and automatic `spam-blocked` after timeout

---

## License

MIT
