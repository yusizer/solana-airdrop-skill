# CLAUDE.md — solana-airdrop-skill

This file activates the airdrop skill, agents, commands, and rules when this
repo (or its installed copy) is the active Claude Code project.

## Project

A Solana AI Kit **skill addon** for Merkle-tree token/SOL airdrops — recipient
ingestion, Merkle root + per-recipient proofs, on-chain claim-instruction
building for the real Solana Foundation / Metaplex gumdrop programs, anti-double-
claim PDA derivation, and anti-sybil eligibility. See `README.md`.

## Skill routing

The skill entry point is `skill/SKILL.md`. It is a **lazy router** — load
focused files only when a task needs them. Do not preload all `.md` files.

Intent → file map is defined inside `skill/SKILL.md`. Follow it.

## Agents

- `agents/airdrop-planner.md` — opus — drop shape, eligibility, program choice.
- `agents/distribution-engineer.md` — sonnet — build tree + proofs + claim txs.

## Commands

- `/airdrop-design` — `commands/airdrop-design.md`
- `/build-proofs` — `commands/build-proofs.md`
- `/verify-drop` — `commands/verify-drop.md`
- `/claim-tx` — `commands/claim-tx.md`

## Rules (auto-load on file read)

- `rules/freshness-before-publish.md` — confirm the target program's verifier before generating leaves.
- `rules/verify-before-launch.md` — every proof must verify before the root is published.

## Non-negotiables

1. **Verify before publish.** No root is published until `verify_all() == N`. A root built with a wrong encoding is unrecoverable after launch. See `rules/verify-before-launch.md`.
2. **Match the target verifier.** Leaf encoding + proof mode (index-based vs sorted-pair) must match the exact on-chain program the drop targets. Do not mix conventions. See `rules/freshness-before-publish.md`.
3. **Real APIs only.** Every program ID / leaf layout / npm version in a `.md` must be current and primary-sourced (`skill/resources.md`). If unsure, mark it "UNVERIFIED" rather than invent one.
4. **User signs.** This skill never custodies the airdrop authority key; `initialize` and funding are built as instructions for the user to sign.

## Two-Strike Rule

If the same SDK call, proof convention, or claim step fails twice in a row, stop. Present the two errors verbatim and ask the user for guidance. Do not retry a third time blind.
