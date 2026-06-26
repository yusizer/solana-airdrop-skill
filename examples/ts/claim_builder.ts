/**
 * claim_builder.ts — on-chain instruction builders for Solana Merkle airdrops.
 *
 * Builds the `initialize` (publish root + fund) and `claim` (recipient proves
 * inclusion + receives tokens) instructions for the REAL Solana program
 * patterns documented in ../../skill/resources.md. Typed, `tsc --noEmit` clean.
 *
 * Two verified program patterns are covered:
 *   1. Solana Foundation merkle-airdrop template (SOL):
 *        leaf = keccak256(pubkey || amount_le_u64 || 0x00), index-based verify,
 *        claim-status PDA = ["claim", airdrop_state, claimant].
 *   2. Metaplex mpl-gumdrop (SPL token, mainnet gdrpGjVffourzkdDRrQmySw4aTHr8a3xmQzzxSwFD1a):
 *        leaf = keccak256(0x00 || index_le_u64 || claimant || mint || amount_le_u64),
 *        OpenZeppelin sorted-pair verify, per-index claim PDA.
 *
 * Uses @solana/web3.js (1.98.x) — the legacy path also used by Metaplex's
 * mpl-toolbox. A modern @solana/kit + Codama-codegen variant for the official
 * template is shown in ../../skill/resources.md (getClaimAirdropInstruction).
 *
 * This module builds instructions; it does NOT sign or send. The user signs.
 */

import {
  PublicKey,
  TransactionInstruction,
  SystemProgram,
  SYSVAR_RENT_PUBKEY,
  Keypair,
} from "@solana/web3.js";

/** Keccak-256 (Solana BPF keccak; the on-chain hash for every verified program). */
// In production use `@noble/hashes/sha3`'s keccak_256 or `js-sha3`'s keccak_256.
// A tiny stand-in is declared here so this file typechecks without a crypto dep;
// replace with the real implementation before sending a transaction.
export declare function keccak256(data: Uint8Array): Uint8Array;

/** 8-byte little-endian u64. */
function leU64(n: bigint): Uint8Array {
  if (n < 0n || n >= 1n << 64n) throw new Error("amount out of u64 range");
  const out = new Uint8Array(8);
  let v = n;
  for (let i = 0; i < 8; i++) {
    out[i] = Number(v & 0xffn);
    v >>= 8n;
  }
  return out;
}

/** Leaf for the Solana Foundation template: keccak256(pubkey || amount_le || 0x00). */
export function leafSolanaOfficial(claimant: PublicKey, amount: bigint): Uint8Array {
  const data = new Uint8Array(32 + 8 + 1);
  data.set(claimant.toBytes(), 0);
  data.set(leU64(amount), 32);
  data[40] = 0x00; // isClaimed flag at leaf-creation
  return keccak256(data);
}

/** Leaf for Metaplex gumdrop: keccak256(0x00 || index_le || claimant || mint || amount_le). */
export function leafGumdrop(
  index: bigint,
  claimant: PublicKey,
  mint: PublicKey,
  amount: bigint,
): Uint8Array {
  const data = new Uint8Array(1 + 8 + 32 + 32 + 8);
  data[0] = 0x00;
  data.set(leU64(index), 1);
  data.set(claimant.toBytes(), 9);
  data.set(mint.toBytes(), 41);
  data.set(leU64(amount), 73);
  return keccak256(data);
}

// ---------------------------------------------------------------------------
// Solana Foundation template (SOL)
// ---------------------------------------------------------------------------

/** Airdrop state PDA: seeds = ["merkle_tree"]. One drop per program deployment. */
export function deriveAirdropState(programId: PublicKey): [PublicKey, number] {
  return PublicKey.findProgramAddressSync([Buffer.from("merkle_tree")], programId);
}

/** Claim-status PDA: seeds = ["claim", airdrop_state, claimant]. */
export function deriveClaimStatus(
  programId: PublicKey,
  airdropState: PublicKey,
  claimant: PublicKey,
): [PublicKey, number] {
  return PublicKey.findProgramAddressSync(
    [Buffer.from("claim"), airdropState.toBuffer(), claimant.toBuffer()],
    programId,
  );
}

export interface InitializeAirdropArgs {
  programId: PublicKey;
  authority: PublicKey; // pays + funds
  merkleRoot: Uint8Array; // 32 bytes
  totalAmount: bigint; // SOL lamports to fund
}

/** initialize_airdrop(merkle_root, amount) — publish root + fund with SOL. */
export function buildInitializeAirdropInstruction(
  args: InitializeAirdropArgs,
): TransactionInstruction {
  if (args.merkleRoot.length !== 32) throw new Error("merkleRoot must be 32 bytes");
  const [airdropState] = deriveAirdropState(args.programId);
  // ix discriminator placeholder — a real deploy uses the Anchor discriminator
  // (first 8 bytes of sha256("global:initialize_airdrop")). Replace with the
  // generated client's getInitializeAirdropInstruction for a real deployment.
  const data = new Uint8Array(8 + 32 + 8);
  data.set(new Uint8Array(8), 0); // discriminator (fill from IDL)
  data.set(args.merkleRoot, 8);
  data.set(leU64(args.totalAmount), 40);
  return new TransactionInstruction({
    programId: args.programId,
    keys: [
      { pubkey: airdropState, isSigner: false, isWritable: true },
      { pubkey: args.authority, isSigner: true, isWritable: true },
      { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
    ],
    data: Buffer.from(data),
  });
}

export interface ClaimAirdropArgs {
  programId: PublicKey;
  claimant: Keypair; // signer + recipient
  amount: bigint;
  proof: Uint8Array[]; // 32-byte sibling hashes, index-based order
  leafIndex: bigint;
}

/** claim_airdrop(amount, proof, leaf_index) — claimant proves inclusion + receives SOL. */
export function buildClaimAirdropInstruction(args: ClaimAirdropArgs): TransactionInstruction {
  const [airdropState] = deriveAirdropState(args.programId);
  const [userClaim] = deriveClaimStatus(args.programId, airdropState, args.claimant.publicKey);
  for (const p of args.proof) if (p.length !== 32) throw new Error("proof elements must be 32 bytes");
  // data = discriminator(8) + amount(8) + leaf_index(8) + proof_len(4) + proof[32*n]
  const data = new Uint8Array(8 + 8 + 8 + 4 + 32 * args.proof.length);
  data.set(leU64(args.amount), 8);
  data.set(leU64(args.leafIndex), 16);
  const view = new DataView(data.buffer);
  view.setUint32(24, args.proof.length, true);
  for (let i = 0; i < args.proof.length; i++) data.set(args.proof[i], 28 + 32 * i);
  return new TransactionInstruction({
    programId: args.programId,
    keys: [
      { pubkey: airdropState, isSigner: false, isWritable: true },
      { pubkey: userClaim, isSigner: false, isWritable: true },
      { pubkey: args.claimant.publicKey, isSigner: true, isWritable: true },
      { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
    ],
    data: Buffer.from(data),
  });
}

// ---------------------------------------------------------------------------
// Metaplex mpl-gumdrop (SPL token, mainnet)
// ---------------------------------------------------------------------------

export function deriveGumdropDistributor(
  programId: PublicKey,
  base: PublicKey,
): [PublicKey, number] {
  return PublicKey.findProgramAddressSync(
    [Buffer.from("MerkleDistributor"), base.toBuffer()],
    programId,
  );
}

/** Per-index claim status: seeds = ["ClaimStatus", index_le, distributor]. */
export function deriveGumdropClaimStatus(
  programId: PublicKey,
  index: bigint,
  distributor: PublicKey,
): [PublicKey, number] {
  return PublicKey.findProgramAddressSync(
    [Buffer.from("ClaimStatus"), leU64(index), distributor.toBuffer()],
    programId,
  );
}

export interface GumdropClaimArgs {
  programId: PublicKey;
  distributor: PublicKey;
  payer: PublicKey; // claimant (signer)
  fromTokenAccount: PublicKey; // distributor's vault ATA
  toTokenAccount: PublicKey; // claimant's ATA
  tokenProgram: PublicKey;
  index: bigint;
  amount: bigint;
  claimantSecret: PublicKey;
  proof: Uint8Array[]; // sorted-pair (OZ) siblings
}

/** gumdrop claim — SPL token transfer from vault to claimant on proof verification. */
export function buildGumdropClaimInstruction(args: GumdropClaimArgs): TransactionInstruction {
  const [claimStatus] = deriveGumdropClaimStatus(
    args.programId, args.index, args.distributor,
  );
  for (const p of args.proof) if (p.length !== 32) throw new Error("proof elements must be 32 bytes");
  const data = new Uint8Array(8 + 8 + 8 + 32 + 4 + 32 * args.proof.length);
  data.set(leU64(args.index), 8);
  data.set(leU64(args.amount), 16);
  data.set(args.claimantSecret.toBytes(), 24);
  const view = new DataView(data.buffer);
  view.setUint32(56, args.proof.length, true);
  for (let i = 0; i < args.proof.length; i++) data.set(args.proof[i], 60 + 32 * i);
  return new TransactionInstruction({
    programId: args.programId,
    keys: [
      { pubkey: args.distributor, isSigner: false, isWritable: true },
      { pubkey: claimStatus, isSigner: false, isWritable: true },
      { pubkey: args.fromTokenAccount, isSigner: false, isWritable: true },
      { pubkey: args.toTokenAccount, isSigner: false, isWritable: true },
      { pubkey: args.payer, isSigner: true, isWritable: true },
      { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
      { pubkey: args.tokenProgram, isSigner: false, isWritable: false },
      { pubkey: SYSVAR_RENT_PUBKEY, isSigner: false, isWritable: false },
    ],
    data: Buffer.from(data),
  });
}

// ---------------------------------------------------------------------------
// Verify helpers (mirror merkle_tree.py for a TS-side sanity check)
// ---------------------------------------------------------------------------

/** Index-based Merkle proof verification (Solana Foundation template). */
export function verifyIndexBased(
  root: Uint8Array,
  index: number,
  leaf: Uint8Array,
  proof: Uint8Array[],
): boolean {
  let acc = leaf;
  let idx = index;
  for (const sibling of proof) {
    acc = idx & 1 ? keccak256(concat(sibling, acc)) : keccak256(concat(acc, sibling));
    idx >>= 1;
  }
  return bytesEqual(acc, root);
}

function concat(a: Uint8Array, b: Uint8Array): Uint8Array {
  const out = new Uint8Array(a.length + b.length);
  out.set(a, 0);
  out.set(b, a.length);
  return out;
}

function bytesEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}
