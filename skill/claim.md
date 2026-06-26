# On-chain claim transactions — accounts, PDAs, double-claim prevention

How a recipient turns a Merkle proof into an on-chain token transfer, for each
of the three real programs (primary sources in `resources.md`). The
TypeScript instruction builders are `../examples/ts/claim_builder.ts`
(`tsc --noEmit` clean, simulate-only — the user signs).

## General shape

A claim instruction does three things on-chain:
1. **Verify** the presented `(leaf, proof, index)` recomputes the published root.
2. **Check + mark claimed** so the same recipient cannot claim twice.
3. **Transfer** the amount from the funded vault/state to the claimant.

The skill builds the instruction; the **claimant signs and sends** it. The
airdrop authority key is not involved in a claim (it was used once, in
`initialize`, to publish the root and fund).

## 1. Solana Foundation template (SOL)

**`claim_airdrop(amount, proof, leaf_index)`** accounts:

| Account | Writable | Signer | Notes |
|---|---|---|---|
| `airdrop_state` | yes | no | PDA `["merkle_tree"]`; holds SOL lamports |
| `user_claim` | yes | no | PDA `["claim", airdrop_state, claimant]` — `init`, blocks replay |
| `claimant` | yes | yes | recipient + fee payer |
| `system_program` | no | no | |

**Double-claim prevention:** `user_claim` is `init` (Anchor). A second claim by
the same claimant fails because the account already exists. `amount_claimed` is
also tracked on `airdrop_state`.

**Funds:** SOL only. `claim_airdrop` subtracts lamports from `airdrop_state` and
credits the claimant. No token program, no mint, no vault ATA.

**Builder:** `buildClaimAirdropInstruction` in `claim_builder.ts`.

## 2. Metaplex mpl-gumdrop (SPL token, mainnet `gdrpGjVffourzkdDRrQmySw4aTHr8a3xmQzzxSwFD1a`)

**`claim(claim_bump, index, amount, claimant_secret, proof)`** accounts:

| Account | Writable | Signer | Notes |
|---|---|---|---|
| `distributor` | yes | no | PDA `["MerkleDistributor", base]`; holds drop config + root |
| `claim_status` | yes | no | PDA `["ClaimStatus", index_le, distributor]` — per-INDEX, `init` |
| `from` (vault) | yes | no | distributor's token account (funded) |
| `to` | yes | no | claimant's token account (ATA) |
| `temporal` | no | yes | optional OTP signer |
| `payer` | yes | yes | claimant |
| `system_program` | no | no | |
| `token_program` | no | no | SPL Token |

**Double-claim prevention:** per-INDEX `claim_status` PDA (`init`, space 8+49).
The leaf binds the `claimant_secret` (a wallet), so only the intended recipient
can claim a given index.

**Funds:** SPL token — `from` (the distributor's vault ATA) → `to` (claimant
ATA) via Token Program CPI signed by the distributor PDA.

**Builder:** `buildGumdropClaimInstruction` in `claim_builder.ts`.

## 3. SPL-token vault pattern (reference)

- `state` PDA `["airdrop_state"]`; `vault_authority` PDA `["airdrop_vault_authority"]`;
  `vault` = ATA(mint, vault_authority).
- Double-claim: a compact **bitmap** in `state.claimed_bitmap` (bit per index),
  not a per-claimant PDA.
- Claim accounts: `state`, `claimer` (signer), `mint`, `vault_authority`,
  `vault`, `claimer_token_account`, `system_program`, `token_program`,
  `associated_token_program`.
- Leaf: `keccak256(index_le_u32 ‖ pubkey ‖ amount_le_u64)`.

This is the cleanest SPL-token-vault reference (the official template has no
vault; gumdrop uses a pre-existing `from` token account). The program ID in the
reference repo is devnet/personal and **UNVERIFIED** on mainnet — do not deploy
against it without re-verifying.

## PDA derivation quick reference

```ts
// Solana Foundation template
deriveAirdropState(programId)                       // ["merkle_tree"]
deriveClaimStatus(programId, airdropState, claimant)// ["claim", airdropState, claimant]

// gumdrop
deriveGumdropDistributor(programId, base)           // ["MerkleDistributor", base]
deriveGumdropClaimStatus(programId, index, distributor) // ["ClaimStatus", index_le, distributor]
```

All via `PublicKey.findProgramAddressSync` (`@solana/web3.js`); see
`claim_builder.ts`.

## What the skill never does

- Does not sign `claim` or `initialize` — the user does.
- Does not custody the airdrop authority key.
- Does not invent PDAs or discriminators — every seed above is from the
  on-chain source code in `resources.md`.
