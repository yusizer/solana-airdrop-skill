---
name: build-proofs
description: Build the Merkle tree + per-recipient proofs from a recipient list and write proofs.json.
---

# /build-proofs

Runs `examples/build_drop.py` to build the Merkle tree and write `proofs.json` (root + per-recipient leaf + proof) using the encoding/mode from the plan.

## Usage

```
/build-proofs <recipients.csv> [--encoding solana-official|gumdrop|spl-vault|simple] [--mode index-based|sorted-pair] [--mint <64-hex>]
```

## Output

The Merkle root + `N/N proofs verify` against it. Exits non-zero if any proof fails — never publish a root that does not fully verify. See `../rules/verify-before-launch.md` and `../skill/merkle.md`.
