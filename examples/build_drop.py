#!/usr/bin/env python3
"""
build_drop.py — CLI: recipients.csv -> Merkle root + per-recipient proofs.json.

Pure-Python, zero hard dependencies (base58 is optional — only needed if your
CSV uses base58 pubkeys; hex pubkeys need nothing extra). Uses the verified
Merkle engine in merkle_tree.py and the REAL on-chain leaf encodings.

Usage:
  python examples/build_drop.py recipients.csv \\
      --encoding solana-official --out proofs.json

CSV columns: pubkey,amount   (pubkey as 64-char hex OR base58; amount = raw u64)

The script prints the Merkle root and verifies every proof against it before
writing proofs.json. Exit non-zero if any proof fails to verify.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from merkle_tree import AirdropDistribution, LEAF_ENCODINGS, ENCODING_MODE  # noqa: E402


def parse_pubkey(s: str) -> bytes:
    """Decode a 32-byte Solana address from hex (64 chars) or base58."""
    s = s.strip()
    if len(s) == 64 and all(c in "0123456789abcdefABCDEF" for c in s):
        return bytes.fromhex(s)
    try:
        import base58  # optional dependency for base58 pubkeys
    except ImportError as e:
        raise SystemExit(
            "base58 pubkey detected but the `base58` package is not installed "
            "(pip install base58), or supply the pubkey as 64-char hex."
        ) from e
    b = base58.b58decode(s)
    if len(b) != 32:
        raise SystemExit(f"pubkey decodes to {len(b)} bytes, expected 32: {s}")
    return b


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a Solana Merkle airdrop.")
    ap.add_argument("recipients", help="CSV with columns: pubkey,amount")
    ap.add_argument("--encoding", default="solana-official", choices=LEAF_ENCODINGS)
    ap.add_argument("--mode", default=None,
                    choices=["index-based", "sorted-pair"],
                    help="verify mode; defaults to the encoding's required mode")
    ap.add_argument("--mint", default=None,
                    help="32-byte mint as hex (required for 'gumdrop')")
    ap.add_argument("--out", default="proofs.json")
    args = ap.parse_args()

    # Enforce the encoding↔mode binding (non-negotiable #2): a mismatch silently
    # bricks 100% of claims on-chain. The mode defaults to the encoding's
    # required mode and cannot be overridden to an incompatible value.
    required_mode = ENCODING_MODE[args.encoding]
    if args.mode is None:
        args.mode = required_mode
    elif args.mode != required_mode:
        ap.error(
            f"encoding '{args.encoding}' requires --mode '{required_mode}' "
            f"(got '{args.mode}'); a mismatch bricks 100% of claims on-chain"
        )

    mint: bytes | None = None
    if args.encoding == "gumdrop":
        if not args.mint:
            ap.error("--mint is required for encoding 'gumdrop'")
        mint = bytes.fromhex(args.mint)
        if len(mint) != 32:
            ap.error("--mint must be 64 hex chars (32 bytes)")

    recips: list[tuple[bytes, int]] = []
    with open(args.recipients, newline="") as f:
        for row in csv.DictReader(f):
            recips.append((parse_pubkey(row["pubkey"]), int(row["amount"])))
    if not recips:
        raise SystemExit("no recipients in CSV")

    # de-dup check (same pubkey+amount would collide in the tree)
    seen = set()
    for pk, amt in recips:
        key = (pk, amt)
        if key in seen:
            raise SystemExit(f"duplicate recipient (pubkey+amount): {pk.hex()} {amt}")
        seen.add(key)

    dist = AirdropDistribution.build(
        recips, encoding=args.encoding, mode=args.mode, mint=mint
    )
    ok = dist.verify_all()
    out = {
        "encoding": args.encoding,
        "mode": args.mode,
        "root": dist.root_hex,
        "n": len(recips),
        "recipients": [
            {
                "index": i,
                "pubkey": pk.hex(),
                "amount": amt,
                "leaf": dist.tree.leaves[i].hex(),
                "proof": [p.hex() for p in dist.proofs[i]],
            }
            for i, (pk, amt) in enumerate(recips)
        ],
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)

    print(f"encoding : {args.encoding} ({args.mode})")
    print(f"root     : {dist.root_hex}")
    print(f"verified : {ok}/{len(recips)} proofs against root")
    print(f"written  : {args.out}")
    return 0 if ok == len(recips) else 1


if __name__ == "__main__":
    sys.exit(main())
