# Resources — real Solana Merkle airdrop programs, SDKs, and versions

Every program ID, leaf layout, and package version below was verified against
primary sources on **2026-06-26** (repo code, npm registry, on-chain
`getAccountInfo`). If you re-verify and something has drifted, update this file
and `skill/SKILL.md`'s frontmatter `verified:` date — do not author from memory.

## Real Solana Merkle airdrop programs

### 1. Solana Foundation merkle-airdrop template (SOL)

- **Repo:** https://github.com/solana-foundation/templates/tree/main/community/merkle-airdrop
- **Template page:** https://solana.com/developers/templates/merkle-airdrop
- **On-chain program file:** `anchor/programs/solana-distributor/src/lib.rs`
- **Off-chain tree file:** `anchor/lib/merkle-tree-manager.ts`
- **Program ID:** no canonical mainnet ID — each deployer generates one with
  `solana-keygen`. The template maintainer's devnet instance is
  `6Gs656WdKHM2XuZU3CZQ7SJNo63FecawsLECE6wFnozT` (**devnet-verified** via
  `getAccountInfo`: owner `BPFLoaderUpgradeab1e11111111111111111111111`, executable).
- **Stack:** Anchor (`anchor-lang`/`anchor-spl` 0.32.1 per Cargo.toml) + Codama
  codegen + `@solana/kit` (frontend) + `gill` (scripts) + `js-sha3`.
- **Instructions:**
  - `initialize_airdrop(merkle_root: [u8;32], amount: u64)`
  - `claim_airdrop(amount: u64, proof: Vec<[u8;32]>, leaf_index: u64)`
  - `update_merkle_root(new_merkle_root: [u8;32], additional_amount: u64)`
- **Leaf (on-chain, authoritative):** `keccak256(pubkey_32 ‖ amount_le_u64 ‖ 0x00)`
  (the `0x00` is the `isClaimed` flag at leaf-creation time).
- **Verify:** index-based — `if index % 2 == 0 { computed = H(computed ‖ sibling) } else { computed = H(sibling ‖ computed) }; index /= 2`.
- **PDA seeds:** airdrop state = `["merkle_tree"]` (one drop per deployment — a real limitation to note); claim status = `["claim", airdrop_state, claimant]`.
- **Funds:** SOL only — `airdrop_state` itself holds lamports (no token vault/mint).
- **⚠️ Known inconsistency:** the JS helper `verifyGillProof` in `merkle-tree-manager.ts` uses **sorted pairing**, which does NOT match the on-chain index-based verifier. The tree *build* is consistent; the verify helper is not. Follow the on-chain convention.

### 2. Metaplex mpl-gumdrop (SPL token — MAINNET)

- **Repo:** https://github.com/metaplex-foundation/mpl-gumdrop (last commit 2025-03-13, not archived)
- **Program ID:** `gdrpGjVffourzkdDRrQmySw4aTHr8a3xmQzzxSwFD1a` (**mainnet-verified** via `api.mainnet-beta.solana.com` `getAccountInfo`).
- **Client:** `@metaplex-foundation/mpl-gumdrop` (npm; depends on `@metaplex-foundation/mpl-toolbox`, web3.js-based — NOT `@solana/kit`).
- **Leaf (token claim, on-chain):** `keccak256(0x00 ‖ index_le_u64 ‖ claimant_secret_32 ‖ mint_32 ‖ amount_le_u64)`. NFT/candy variants add `resource` + `resource_nonce`.
- **Verify:** OpenZeppelin `MerkleProof.sol` v3.4.0 port — **sorted pairs** with domain separators: leaf `0x00`, node `0x01`. `if computed <= proof { computed = H(0x01 ‖ computed ‖ proof) } else { computed = H(0x01 ‖ proof ‖ computed) }`.
- **PDA seeds:** distributor = `["MerkleDistributor", base]`; claim status = `["ClaimStatus", index_le, distributor]` (**per-index**, not per-claimant); claim count = `["ClaimCount", index_le, distributor]`.
- **Actively used:** yes — Metaplex's canonical print-edition / token distributor.

### 3. SPL-token vault pattern (reference)

- **Reference repo:** https://github.com/bl0ckchaindev/solana-airdrop (devnet/personal; mainnet **UNVERIFIED** — `declare_id!` and `Anchor.toml` keys mismatch; treat the program ID as unverified).
- **Leaf:** `keccak256(index_le_u32 ‖ pubkey_32 ‖ amount_le_u64)` — no domain separator, no mint, no isClaimed byte.
- **Verify:** index-based.
- **Double-claim:** compact **bitmap** in `AirdropState.claimed_bitmap` (no per-claimant PDA).
- **PDA seeds:** state = `["airdrop_state"]`; vault authority = `["airdrop_vault_authority"]`; vault = ATA(mint, vault_authority). This is the cleanest SPL-token-vault reference (the official template has no vault; gumdrop uses a pre-existing `from` token account).

## Current JS/SDK versions (verified via npm registry 2026-06-26)

| Package | Latest | Notes |
|---|---|---|
| `@solana/kit` | 6.10.0 | modern RPC/tx/codec client (anza-xyz/kit) |
| `@solana/web3.js` | 1.98.4 | legacy; used by gumdrop's mpl-toolbox |
| `@solana/spl-token` | 0.4.14 | SPL token client (no Merkle tree shipped) |
| `@metaplex-foundation/umi` | 1.5.1 | |
| `@metaplex-foundation/mpl-gumdrop` | (npm) | gumdrop client |
| `gill` | 0.14.0 | tx construction (official template scripts) |
| `js-sha3` | 0.9.3 | `keccak_256` — used by the official template |
| `@noble/hashes` | (sha3) | `keccak_256` — alternative |
| `@openzeppelin/merkle-tree` | 1.0.8 | sorted-pair standard (same convention as gumdrop's on-chain Rust port of `MerkleProof.sol` v3.4.0 — not the JS lib itself) |
| `merkletreejs` | 0.6.0 | general tree (sorted & unsorted) |

**No official Solana package ships a Merkle tree** — `@solana/kit`, `@solana/web3.js`, and `@solana/spl-token` were all grepped and contain no merkle code. Devs hand-roll with `js-sha3`/`@noble/hashes`, or use `@openzeppelin/merkle-tree` (for OZ-sorted verifiers like gumdrop). This skill's `examples/merkle_tree.py` is the Python equivalent — zero-dependency, keccak-by-default.

## How to build claim instructions in 2026

- **Modern (official template):** Codama codegen from the Anchor IDL → generated
  `getClaimAirdropInstruction({...})` returning `@solana/kit`/`gill` `IInstruction`s.
  See `examples/claim_builder.ts` for the concrete call shape.
- **Legacy (gumdrop):** `@solana/web3.js` hand-rolled `TransactionInstruction` + `AccountMeta[]`.

## Verification checklist before you trust any number above

- [ ] `getAccountInfo` on the program ID returns `executable: true` with `BPFLoaderUpgradeab1e` owner.
- [ ] The leaf layout in `lib.rs` matches `skill/merkle.md` for your chosen encoding.
- [ ] The on-chain verify loop (index-based vs sorted-pair) matches `merkle_tree.py`'s `mode`.
- [ ] npm versions re-checked the day you generate instructions.
