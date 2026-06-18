#!/usr/bin/env python3
"""
solve_pow.py — Ngao PoW solver for contributors
================================================
Usage:
    python3 solve_pow.py <nonce> <difficulty>

Example:
    python3 solve_pow.py a3f8c1d2e4b56789 4

This finds a solution string S such that:
    SHA-256("<nonce>:<S>") starts with <difficulty> leading zeros.

Paste the printed solution into the PR comment as:
    pow-solution: <solution>
"""

import hashlib
import itertools
import sys
import time


def solve(nonce: str, difficulty: int) -> str:
    target = "0" * difficulty
    print(f"🔍 Solving PoW challenge...")
    print(f"   Nonce      : {nonce}")
    print(f"   Difficulty : {difficulty} (hash must start with '{target}')")
    print()

    start = time.time()
    for i in itertools.count():
        candidate = str(i)
        digest = hashlib.sha256(f"{nonce}:{candidate}".encode()).hexdigest()
        if digest.startswith(target):
            elapsed = time.time() - start
            print(f"✅ Solution found in {elapsed:.2f}s after {i+1:,} attempts!")
            print()
            print(f"   Solution : {candidate}")
            print(f"   Hash     : {digest}")
            print()
            print("Reply to the PR comment with:")
            print(f"   pow-solution: {candidate}")
            return candidate

        # Print progress every 100k attempts
        if i > 0 and i % 100_000 == 0:
            elapsed = time.time() - start
            rate = i / elapsed
            print(f"   ... {i:,} attempts ({rate:,.0f} h/s)", end='\r')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    nonce = sys.argv[1]
    try:
        difficulty = int(sys.argv[2])
        if difficulty < 1 or difficulty > 8:
            raise ValueError
    except ValueError:
        print("Error: difficulty must be an integer between 1 and 8.")
        sys.exit(1)

    solve(nonce, difficulty)
