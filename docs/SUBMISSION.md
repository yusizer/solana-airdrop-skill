# Superteam listing submission — solana-airdrop-skill

Listing: https://earn.superteam.fun/listings/superteambr/skills
Bounty: "Ship useful agent skills we can add to Solana AI Kit" — Superteam Brasil
Deadline: 2026-07-01 · Reward: 3 000 USDG across 10 winners (1–5 = 400, 6–10 = 200)

## Deliverables (all done)

- [x] Public GitHub repo: https://github.com/yusizer/solana-airdrop-skill (default branch `main`)
- [x] PR to https://github.com/solanabr/skill-bounty (Path-2 novel skill) — **#74**: https://github.com/solanabr/skill-bounty/pull/74
- [x] README (problem / install / eval)
- [x] SKILL.md entry point following kit structure (lazy router, frontmatter, "What it is NOT", provenance)
- [x] MIT licensed
- [x] **19 unit tests** (Keccak-256 KATs, 3 real leaf encodings, round-trips, tamper rejection) + **quantified eval 256/256 vs every baseline 0/256, 0/4 forged-accepts** — runs in CI
- [x] `tsc --noEmit` clean claim-instruction builder (`@solana/web3.js` 1.98.x) — typechecked in CI
- [x] Live GitHub Pages landing (`docs/index.html` + `deploy-pages.yml`)
- [x] **Submit PR link + questionnaire on the listing  ← only step left (Yusif does this)**

## Paste into the listing form

### Q1. Did you contribute towards existing repos or is it a new idea?

**New idea (Path-2).** A Merkle-tree token/SOL airdrop skill — recipient ingestion, Merkle root + per-recipient proof generation, on-chain claim-instruction building for real Solana programs, anti-double-claim PDA derivation, and anti-sybil eligibility. It is **not** one of the three seeded ideas, not in the Solana AI Kit, and not covered by any of the other bounty PRs (74 at the time of writing — 0 collisions) — I verified all three by grepping the full PR list (titles + bodies for "airdrop", "merkle", "claim", "distribute") and by enumerating the kit's 45 `sendaifun` skills, 18 submodules, and 39-entry registry. Nearly every token launch involves an airdrop, yet **no official Solana package ships a Merkle tree** (`@solana/kit`, `@solana/web3.js`, `@solana/spl-token` were grepped — none contain merkle code), so every builder hand-rolls the convention-fragile part. This skill gets it right and proves it.

### Q2. What is your closest "competing" skill?

**No bounty PR competes** — 0 collisions (verified across all 74 PRs). The closest *kit* references are all non-competing:
- `sendaifun/skills` (orca/meteora/raydium/jupiter/kamino…) — DeFi primitives (swap, LP, lend); none distribute tokens via Merkle proofs.
- `jup-ag/agent-skills` — swaps/aggregation, not distribution.
- `metaplex-foundation/skill` — NFT standards (Core, Candy Machine); mpl-gumdrop is a *program* this skill builds claim txs for, not an agent skill.
This is the first skill to bundle **ingest → build tree → publish root → prove → claim → prevent double-claim** with a zero-dependency pure-Python **Keccak-256** engine (verified against the NIST KAT), the exact leaf encodings of three real on-chain programs (Solana Foundation template, Metaplex mpl-gumdrop mainnet, SPL-token vault pattern), a quantified eval (with-skill 256/256 claimable vs every baseline 0/256, 0/4 forged-accepts), a `tsc`-clean claim-instruction builder, and safe-launch rules.

### Q3. Links/proofs showing why you should be the creator of this skill (founder-market fit)

- **Standalone repo + PR** — production structure matching the kit: `skill/SKILL.md` lazy router, `agents/`, `commands/`, `rules/`, `install.sh`, MIT.
- **Real on-chain fidelity (verified 2026-06-26):** three actual programs with primary-source citations in `skill/resources.md` — Solana Foundation `merkle-airdrop` template (leaf `keccak256(pubkey‖amt‖0x00)`, index-based verify, devnet program `6Gs656…nozT` verified via `getAccountInfo`); Metaplex `mpl-gumdrop` on **mainnet** `gdrpGjVffourzkdDRrQmySw4aTHr8a3xmQzzxSwFD1a` (leaf `keccak256(0x00‖index‖claimant‖mint‖amt)`, OpenZeppelin sorted-pair verify); SPL-token vault pattern (bitmap double-claim). Anything unverified is labeled `UNVERIFIED` — nothing invented.
- **Executable + tested:** `examples/merkle_tree.py` — zero-dependency, pure-Python Keccak-256 (NIST KAT-checked) + 3 encodings + index-based AND sorted-pair trees. `tests/test_merkle.py` — **19 unit tests** (KATs, encodings, power-of-two + non-power-of-two round-trips, single recipient, tamper/wrong-index/corrupted-proof rejection). `tests/test_eval.py` — **quantified eval: with-skill 256/256 vs every baseline 0/256, 0/4 forged claims accepted** (runs in CI).
- **Typed claim builder (REAL crypto):** `examples/ts/claim_builder.ts` on `@solana/web3.js` 1.98.x with `@noble/hashes` Keccak-256 + SHA-256 — initialize + claim + gumdrop-claim instruction builders with Anchor layouts verified byte-for-byte against on-chain `lib.rs` (correct arg order `claim_airdrop(amount, proof, leaf_index)`, gumdrop `claim_bump` + required `temporal` signer, real `sha256("global:<ix>")` discriminators), PDA derivation, index-based verify helper that rejects out-of-range indices — `tsc --noEmit` clean, typechecked in CI.
- **Honest eval methodology:** the 0% baselines are not a strawman — Merkle verification is cryptographic and binary, so a single wrong convention (sha256-vs-keccak, big-endian, missing `0x00`, sorted-pair-vs-index-based) makes 100% of claims unverifiable. The eval reflects the real airdrop failure mode: pass/fail per drop, not graded on a curve. Full methodology + scope in `docs/EVAL.md`.
- **CI:** `validate.yml` runs the 19 unit tests, the quantified eval, a build-drop CLI smoke (solana-official + gumdrop), the TS `tsc --noEmit` typecheck, and a **real install-layout test** (installs into a temp project and asserts the flat `.claude/skills/solana-airdrop/SKILL.md` layout — no nesting). Green runs are on the standalone repo's `main` (badge in README); the workflow is included in the PR.
- **Live site:** GitHub Pages landing (`docs/index.html`).
- **Novel angles:** zero-dep pure-Python Keccak-256 (no `pycryptodome` needed — runs in bare CI), the convention-mismatch failure mode explicitly called out (the real JS-helper bug in the official template), an anti-hallucination "verify before you author" discipline at the top of SKILL.md, and per-program "What this skill is NOT" negative-scope routing so it fits the kit without overlapping the 60+ other skills.

## Links to attach

- PR: https://github.com/solanabr/skill-bounty/pull/74
- Repo: https://github.com/yusizer/solana-airdrop-skill
- Live site: https://yusizer.github.io/solana-airdrop-skill/
- Eval report: https://github.com/yusizer/solana-airdrop-skill/blob/main/docs/EVAL.md

## Contact

Listing contact: @kauenet (Kaue Cano).
