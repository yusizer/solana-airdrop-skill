# Rule — confirm the target verifier before generating leaves

**Before generating any leaf or proof, confirm the target on-chain program's leaf encoding AND proof convention (index-based vs sorted-pair) from its source code.**

## Why

Three real Solana Merkle programs use three different leaf encodings and two different verify conventions (see `skill/resources.md`):
- Solana Foundation template: `keccak256(pubkey ‖ amount_le ‖ 0x00)`, index-based.
- Metaplex mpl-gumdrop (mainnet): `keccak256(0x00 ‖ index_le ‖ claimant ‖ mint ‖ amount_le)`, sorted-pair (OpenZeppelin).
- SPL-token vault pattern: `keccak256(index_le_u32 ‖ pubkey ‖ amount_le)`, index-based.

They are NOT interchangeable. Sorted-pair proofs against an index-based verifier (the exact JS-helper bug in the official template) produce proofs that look fine off-chain but fail on-chain.

## How to apply

1. Identify the target program and read its on-chain verify code (link in `skill/resources.md`).
2. Note: hash function, leaf field order, byte order (little-endian throughout), domain separators, and verify mode.
3. Generate leaves/proofs with `merkle_tree.py` using the matching `encoding` + `mode`.
4. Re-verify (`[[verify-before-launch]]`) before publishing.

## What this rule prevents

Convention mismatch — the most common cause of bricked airdrops.
