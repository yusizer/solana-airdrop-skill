---
name: solana-airdrop
description: Design, generate, and verify Solana token/SOL airdrops using Merkle trees — recipient ingestion, Merkle root + per-recipient proofs, on-chain claim-instruction building for the real Solana Foundation / Metaplex gumdrop programs, anti-double-claim PDA derivation, and anti-sybil eligibility patterns. Use when the user asks about airdrops, Merkle distribution, claim contracts, token distribution, recipient proofs, or whitelist/eligibility on Solana.
license: MIT
compatibility: claude-code, codex
metadata:
  solana-foundation-template: solana-foundation/templates/community/merkle-airdrop
  metaplex-gumdrop-mainnet: gdrpGjVffourzkdDRrQmySw4aTHr8a3xmQzzxSwFD1a
  hash: keccak256
  verified: 2026-06-26
---

# Solana Airdrop Skill

A production-grade skill for **Merkle-tree token/SOL airdrops on Solana**. It turns a coding agent into an expert airdrop engineer: **ingest → build tree → publish root → generate proofs → build claim tx → prevent double-claims**, with real on-chain program fidelity, current SDK calls, and a deterministic, unit-tested Merkle engine.

This skill is an **addon** that extends the core `solana-dev-skill`. It does not duplicate core program/CLI knowledge — it layers airdrop-distribution expertise on top.

> **Verify before you author.** On-chain Merkle verifiers are convention-fragile: a single wrong leaf byte, wrong endianness, or a sorted-pair-vs-index-based mismatch makes **100% of claims unverifiable** and bricks the airdrop. Do not author leaf encodings or proof conventions from memory — re-read the relevant file below and confirm it matches the *target program's on-chain verifier* before generating anything.

## What this skill is NOT

- **Not a token-launch / tokenomics skill** — it distributes tokens that already exist; it does not design supply, vesting, or launch curves (see the kit's tokenomics skills).
- **Not an NFT mint / candy-machine skill** — for NFT distribution use Metaplex's candy-machine; this skill covers fungible-token and SOL Merkle drops (gumdrop's NFT/print-edition path is referenced but out of primary scope).
- **Not a swap / aggregation skill** — it moves tokens from a vault to claimants, it does not trade.
- **Not a security auditor** — it builds correct distributions; for program auditing use the kit's auditor skills.
- This skill gives **analysis, code, and proofs**; it does not custody keys or hold funds. All signing stays with the user's wallet; the airdrop authority key never leaves the user's control.

## When to load this skill

Load the focused files below **only when the task needs them** (progressive, token-efficient loading). Do not read every file upfront.

| Task / intent | Load this | Then this |
|---|---|---|
| "Build an airdrop" / design a drop | [`distribution.md`](distribution.md) | [`merkle.md`](merkle.md) |
| "How do Merkle leaves/proofs work?" / leaf encoding | [`merkle.md`](merkle.md) | [`resources.md`](resources.md) (target program) |
| "Generate the root + proofs" | [`merkle.md`](merkle.md) | `../examples/merkle_tree.py` |
| "Build the claim transaction" / claim accounts | [`claim.md`](claim.md) | `../examples/claim_builder.ts` |
| "Prevent double claims" / claim-status PDA | [`claim.md`](claim.md) | [`merkle.md`](merkle.md) |
| "Who is eligible?" / anti-sybil / whitelist | [`eligibility.md`](eligibility.md) | [`distribution.md`](distribution.md) |
| "Which program / SDK / package version?" | [`resources.md`](resources.md) | — |
| "Verify a proof by hand" / debug a failing claim | [`merkle.md`](merkle.md) | `../examples/merkle_tree.py` |

## The three real Solana Merkle programs (know which one you target)

The skill supports the encodings of three **real, verified** programs. The leaf layout and proof convention MUST match the target on-chain verifier — they are NOT interchangeable.

| Program | Encoding (leaf) | Verify mode | Double-claim | Status |
|---|---|---|---|---|
| **Solana Foundation template** (SOL) | `keccak256(pubkey ‖ amount_le_u64 ‖ 0x00)` | index-based | PDA `["claim", airdrop, claimant]` | devnet-verified |
| **Metaplex mpl-gumdrop** (SPL, mainnet `gdrpGjVf…FD1a`) | `keccak256(0x00 ‖ index_le_u64 ‖ claimant ‖ mint ‖ amount_le_u64)` | sorted-pair (OZ, `0x00`/`0x01` separators) | PDA `["ClaimStatus", index_le, distributor]` | **mainnet** |
| **SPL-token vault** (pattern) | `keccak256(index_le_u32 ‖ pubkey ‖ amount_le_u64)` | index-based | bitmap in state | reference |

See [`resources.md`](resources.md) for primary-source links, program IDs, and npm versions; [`claim.md`](claim.md) for the full claim-account lists and PDA derivations.

## Core loop

```
1. INGEST    recipient list (pubkey, amount) — validate, de-dup, raw units   (distribution.md)
2. BUILD     Merkle tree over leaves with the TARGET program's encoding       (merkle.md + merkle_tree.py)
3. PUBLISH   the root on-chain (initialize_airdrop) + fund the vault           (claim.md + claim_builder.ts)
4. PROVE     per-recipient inclusion proofs (off-chain, served to claimants)   (merkle.md)
5. CLAIM     claimant submits leaf + proof -> claim_airdrop; PDA blocks replay  (claim.md)
6. VERIFY    every proof round-trips against the published root before launch  (merkle_tree.py, test_eval.py)
```

## The leaf (inline, the one thing you must get right)

```python
# examples/merkle_tree.py — Solana Foundation template leaf
def leaf_hash(pubkey: bytes, amount: int) -> bytes:
    # keccak256(pubkey_32 || amount_le_u64 || 0x00)  — matches on-chain claim_airdrop
    return keccak256(pubkey + amount.to_bytes(8, "little") + b"\x00")
```

Get any of {keccak-not-sha, little-endian, the `0x00` byte, index-based verify} wrong and **every** claim fails. The skill's `merkle_tree.py` ships a zero-dependency pure-Python Keccak-256 (verified against the NIST KAT) so this runs anywhere — including CI — without `pycryptodome`.

## Agents & commands bundled

- Agents: `airdrop-planner` (decide drop shape, eligibility, program choice), `distribution-engineer` (build tree + proofs + claim txs). See [`../agents/`](../agents).
- Commands: `/airdrop-design`, `/build-proofs`, `/verify-drop`, `/claim-tx`. See [`../commands/`](../commands).
- Rules (auto-load): [`../rules/freshness-before-publish.md`](../rules/freshness-before-publish.md), [`../rules/verify-before-launch.md`](../rules/verify-before-launch.md).

## Rules of engagement

- **Never** publish a root until every recipient's proof verifies against it (`verify_all()` == N). A root computed with a wrong encoding is unrecoverable after launch. See [`../rules/verify-before-launch.md`](../rules/verify-before-launch.md).
- **Always** confirm the target program's on-chain verifier (index-based vs sorted-pair; leaf fields) before generating leaves. See [`../rules/freshness-before-publish.md`](../rules/freshness-before-publish.md).
- This skill never custodies the airdrop authority key; `initialize_airdrop` and funding are built as instructions for the user to sign.

## Provenance

- On-chain program + leaf layout: `solana-foundation/templates/community/merkle-airdrop` (Anchor `lib.rs`, `merkle-tree-manager.ts`) — primary source, read 2026-06-26.
- Mainnet SPL reference: Metaplex `mpl-gumdrop`, program `gdrpGjVffourzkdDRrQmySw4aTHr8a3xmQzzxSwFD1a`, `programs/mpl-gumdrop/src/merkle_proof.rs` (OpenZeppelin MerkleProof v3.4.0 port).
- Engine + tests: `examples/merkle_tree.py`, `tests/test_merkle.py`, `tests/test_eval.py` (this repo). Eval report: `docs/EVAL.md`.
