# Eligibility — anti-sybil and whitelist patterns for airdrops

Who gets a leaf in the tree. The Merkle math (see `merkle.md`) is blind — it
distributes to whatever recipients you put in. Eligibility is where "the right
people, once each" is enforced. This file is a reference for the
`airdrop-planner` agent; it does not ship an on-chain eligibility program.

## Why eligibility matters

A drop that pays sybills (one operator farming many wallets) wastes the budget
and dilutes real recipients. A drop that misses eligible holders gets
community backlash. The eligibility layer runs **off-chain, before the tree is
built** — its output is the recipient list that feeds `build_drop.py`.

## Patterns

### Allowlist (explicit)
A curated list of (pubkey, amount) pairs — the simplest and most common for
early/community drops. Source: a form, a Discord role export, a manual list.
- Pro: exact control, no snapshot dependency.
- Con: curation effort; sybil risk if the list source is self-reported.
- Anti-sybil: cross-check pubkeys against known sybil clusters; require a
  single-claim signature (prove ownership of the key) before adding.

### Snapshot (balance-based)
Take a block-time snapshot of holders of a mint (or a set of mints) above a
threshold; each qualifying wallet gets a proportional or fixed amount.
- Pro: deterministic, auditable, no sign-up.
- Con: sybils who split balances across many wallets still qualify; snapshot
  block must be announced to prevent manipulation.
- Anti-sybil: cluster analysis (temporal/funding graph) to merge wallets that
  share funding sources; cap per-cluster; weight by holding duration.

### Proof-of-activity / contribution
Eligibility tied to on-chain or off-chain actions (governance votes, LP
deposits, GitHub contributions for a dev drop). Each action → a claim right.
- Pro: rewards actual engagement, sybil-resistant if the action is costly.
- Con: requires indexing the activity; defining "contribution" is subjective.

### Claim-gated (recipient proves eligibility at claim time)
Instead of baking eligibility into the leaf, the claim instruction requires an
extra signer/proof (gumdrop's `claimant_secret` / `temporal` OTP) so only the
intended recipient can claim a given leaf — even if the proof leaks.
- Pro: decouples distribution from the leaf; a leaked proofs file is useless
  to non-eligibles.
- Con: extra UX step; the secret/OTP must be delivered securely.

## Anti-sybil heuristics (off-chain, pre-tree)

These run on the candidate recipient set before `build_drop.py`:

1. **Funding graph clustering** — merge wallets funded by the same source
   within a short window; treat the cluster as one recipient.
2. **Dust filtering** — exclude wallets below a meaningful balance/activity
   threshold (sybills often hold dust).
3. **Age + activity** — prefer wallets with on-chain history older than the
   drop announcement; exclude wallets created after the snapshot block.
4. **Single-claim enforcement** — use a per-claimant claim-status PDA (the
   official template's `["claim", airdrop, claimant]`) so even a duplicated
   recipient entry cannot double-claim.

## Output to the engineer

The planner hands the engineer a **de-duplicated, anti-sybil-filtered**
recipient list (pubkey, raw amount) plus the filter that was applied. The
engineer builds the tree from exactly that list (`distribution.md`).

## What this skill does NOT do

- It does not run cluster analysis itself (that needs an indexer + graph
  engine; reference the kit's `wallet-analysis` / `birdeye` skills).
- It does not bake eligibility into the on-chain program beyond what the target
  program supports (claim-status PDAs, `claimant_secret`). The filter is
  off-chain and pre-tree.
