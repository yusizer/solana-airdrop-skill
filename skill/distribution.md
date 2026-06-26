# Distribution — end-to-end airdrop design + workflow

The full lifecycle a `airdrop-planner` + `distribution-engineer` run through.
Read this before `/airdrop-design`. The executable steps are `../examples/build_drop.py`
(tree + proofs) and `../examples/ts/claim_builder.ts` (instructions).

## 1. Decide what and to whom

- **Asset:** SOL, or an SPL token (need the mint address). For SPL, the target
  program is usually Metaplex `mpl-gumdrop` (mainnet) or the SPL-vault pattern;
  for SOL, the Solana Foundation template.
- **Eligibility:** a recipient list (CSV) or a rule (snapshot, balance
  threshold, allowlist). See `eligibility.md` for anti-sybil filtering.
- **Amounts:** per recipient, in **raw base units** (lamports for SOL, base
  units for the token — e.g. 1 USDC = 1_000_000). Never display decimals.

## 2. Pick the target program (fixes the encoding + verify mode)

| If distributing | Default program | `encoding` | `mode` |
|---|---|---|---|
| SOL | Solana Foundation template | `solana-official` | `index-based` |
| SPL token (mainnet) | Metaplex mpl-gumdrop | `gumdrop` | `sorted-pair` |
| SPL token (custom vault) | SPL-vault pattern | `spl-vault` | `index-based` |

Confirm the choice against the on-chain verifier code in `resources.md`.

## 3. Prepare the recipient list

- Validate every pubkey decodes to 32 bytes.
- De-duplicate on (pubkey, amount) — duplicates collide in the tree.
- Reject zero amounts (a 0-amount leaf is a no-op claim).
- Sort/order is irrelevant to the root but matters for the `index` each
  recipient gets (gumdrop/spl-vault bind the index into the leaf).

## 4. Build the tree + proofs

```bash
python examples/build_drop.py recipients.csv \
    --encoding solana-official --out proofs.json
# -> root printed; N/N proofs verified; proofs.json written
```

`proofs.json` contains, per recipient: `index`, `pubkey`, `amount`, `leaf`,
`proof[]`. Serve each recipient their entry (off-chain UI, API, or file).

## 5. Verify gate (non-negotiable)

`verify_all() == N` before publishing the root. See `../rules/verify-before-launch.md`.
If any proof fails, the encoding is wrong — stop and re-confirm the target
verifier. Do not patch the root.

## 6. Publish the root + fund (initialize)

Build the `initialize` instruction (`claim_builder.ts`):

- SOL: `buildInitializeAirdropInstruction({ programId, authority, merkleRoot, totalAmount })`
  — transfers `totalAmount` lamports from the authority to the `airdrop_state` PDA.
- SPL: the gumdrop `new_distributor` / equivalent — funds the vault ATA.

The **user signs** this. The root is now on-chain and immutable.

## 7. Claims

Each recipient builds + signs their `claim` (the skill builds the instruction;
the claimant signs). The on-chain verifier recomputes the root from
`(leaf, proof, index)`; if it matches the published root and the claim-status
PDA does not yet exist, the transfer executes. See `claim.md`.

## 8. Monitor

Track `amount_claimed` vs total. After the claim window, recover unclaimed
funds per the program's mechanism (`update_merkle_root` for the official
template; gumdrop has its own clawback).

## Common mistakes this workflow prevents

- Amounts in display units instead of raw → brick. (Step 1 + planner rule.)
- Wrong encoding for the chosen program → brick. (Step 2 + `freshness-before-publish`.)
- Publishing a root before verifying → unrecoverable brick. (Step 5 + `verify-before-launch`.)
- Custodying the authority key → not done; user signs. (Steps 6-7.)
