---
name: claim-tx
description: Build an unsigned on-chain claim (or initialize) instruction for a recipient/airdrop.
---

# /claim-tx

Builds the unsigned `claim_airdrop` (or `initialize_airdrop`, or gumdrop `claim`) instruction via `examples/ts/claim_builder.ts`. The user signs; the skill never custodies keys.

## Usage

```
/claim-tx <proofs.json> --recipient <index> [--program solana-official|gumdrop]
```

## Output

An unsigned `TransactionInstruction` (account metas + data) ready for the user's wallet to sign + send. See `../skill/claim.md` and `../agents/distribution-engineer.md`.
