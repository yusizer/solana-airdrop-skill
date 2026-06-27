# solana-airdrop-skill

[![CI](https://github.com/yusizer/solana-airdrop-skill/actions/workflows/validate.yml/badge.svg)](https://github.com/yusizer/solana-airdrop-skill/actions/workflows/validate.yml)
[![Live](https://img.shields.io/badge/live-GitHub%20Pages-blue)](https://yusizer.github.io/solana-airdrop-skill/)

A production-grade **Solana AI Kit** skill for **Merkle-tree token/SOL airdrops**. It turns a coding agent into an expert airdrop engineer: ingest recipients → build the Merkle tree → publish the root → generate per-recipient proofs → build on-chain claim transactions → prevent double-claims — with **real on-chain program fidelity** (verified against the Solana Foundation template and Metaplex mpl-gumdrop mainnet), a **zero-dependency pure-Python Keccak-256 engine**, and a **quantified eval** (with-skill 256/256 claimable vs every tested baseline 0/256).

> Bounty: "Ship useful agent skills we can add to Solana AI Kit" — Superteam Brasil. This is a **Path-2 (novel) skill**: no existing kit skill, seeded idea, or any of the other bounty PRs covers Merkle airdrop distribution (verified by grepping the full PR list + the kit's 45 sendaifun skills + 18 submodules + 39-entry registry — 0 collisions).

## The problem it solves

Merkle airdrops are **convention-fragile**: a single wrong choice — `sha256` instead of `keccak256`, big-endian instead of little-endian, a missing `0x00` isClaimed byte, or sorted-pair proofs against an index-based on-chain verifier — makes **100% of claims unverifiable** and bricks the drop after launch. There is no official Solana Merkle library (`@solana/kit`, `web3.js`, `spl-token` ship none), so every builder hand-rolls the easy-to-get-wrong part. This skill gets it right and proves it.

## What's inside

```
solana-airdrop-skill/
  skill/
    SKILL.md            # lazy router entry point (kit structure)
    merkle.md           # leaf encodings, tree shape, proof generation/verification
    claim.md            # claim accounts, double-claim PDAs, claim tx for 3 programs
    distribution.md     # end-to-end drop design + workflow
    eligibility.md      # anti-sybil / whitelist patterns
    resources.md        # verified program IDs, leaf layouts, npm versions (primary-sourced)
  examples/
    merkle_tree.py      # zero-dep engine: pure-Python Keccak-256, 3 real encodings, proofs
    ts/claim_builder.ts # @solana/web3.js claim-instruction builders (tsc --noEmit clean)
    build_drop.py       # CLI: recipients.csv -> root + proofs.json
  tests/
    test_merkle.py      # 19 unit tests (Keccak KATs, encodings, round-trips, tamper rejection)
    test_eval.py        # quantified eval: with-skill 256/256 vs baselines 0/256, 0 forged-accepts
  agents/  commands/  rules/   # bundled agents, /commands, auto-load rules
  docs/
    EVAL.md             # methodology + results
    SUBMISSION.md       # paste-ready listing answers
    index.html          # live landing page
  .github/workflows/validate.yml   # tests + eval + typecheck + install on every push
  .github/workflows/deploy-pages.yml # publish the docs/ landing to GitHub Pages
  install.sh  README.md  LICENSE  CLAUDE.md
```

## Install

```bash
# into a Solana AI Kit project (Claude Code / Codex)
curl -fsSL https://raw.githubusercontent.com/yusizer/solana-airdrop-skill/main/install.sh | bash
```

Or manually: copy `skill/`, `agents/`, `commands/`, `rules/` into your `.claude/` and the `examples/` + `tests/` where you run code.

## Use (the happy path)

```bash
# 1. Build a drop from a recipient list -> root + per-recipient proofs
python examples/build_drop.py recipients.csv --encoding solana-official --out proofs.json
#   -> prints the merkle root; proofs.json has { index, pubkey, amount, proof[] } per recipient

# 2. Verify every proof against the root BEFORE publishing it
python -c "import json,sys; sys.path.insert(0,'examples'); from merkle_tree import AirdropDistribution, MerkleTree, leaf_hash; \
  d=json.load(open('proofs.json')); \
  ok=sum(MerkleTree.verify(bytes.fromhex(d['root']),r['index'],bytes.fromhex(r['leaf']),[bytes.fromhex(p) for p in r['proof']]) for r in d['recipients']); \
  print(f'{ok}/{len(d[\"recipients\"])} proofs verify')"

# 3. Publish the root on-chain (initialize_airdrop) + build a claim tx
#    -> see examples/claim_builder.ts and skill/claim.md
```

## The eval (the reason to trust it)

`tests/test_eval.py` is deterministic and runs in CI. It builds a 256-recipient drop with the **correct** on-chain encoding (Solana Foundation template), then measures how many claims succeed when the drop is built **with the skill** versus by a developer **without the skill** who reaches for plausible-but-wrong conventions:

| builder | claimable | rate |
|---|---:|---:|
| **with_skill** | **256 / 256** | **100%** |
| baseline: sha256-not-keccak | 0 / 256 | 0% |
| baseline: big-endian-amount | 0 / 256 | 0% |
| baseline: missing-isClaimed byte | 0 / 256 | 0% |
| baseline: convention-mismatch (sorted-pair proofs, index-based verifier) | 0 / 256 | 0% |
| **tamper guard** (forged claims accepted) | **0 / 4** | target 0 |

The 0% baselines are **not a trick** — Merkle verification is cryptographic: one wrong byte makes a proof unverifiable, so a wrong convention bricks the entire drop. That is exactly the failure mode this skill prevents. Full methodology: `docs/EVAL.md`.

## What it is NOT

- Not a token-launch/tokenomics skill (distributes existing tokens; doesn't design supply/vesting).
- Not an NFT candy-machine skill (fungible token + SOL; gumdrop NFT path referenced only).
- Not a swap, aggregator, or security auditor.
- Never custodies keys — all signing stays with the user's wallet.

## Verification status (real APIs only)

Program IDs, leaf layouts, and npm versions in `skill/resources.md` were verified against primary sources on 2026-06-26 (repo code, npm registry, on-chain `getAccountInfo`). Anything unverified is labeled `UNVERIFIED`, never invented. The pure-Python Keccak-256 is checked against the NIST KAT (`keccak256("") == c5d24601…`) in `tests/test_merkle.py`.

## License

MIT.
