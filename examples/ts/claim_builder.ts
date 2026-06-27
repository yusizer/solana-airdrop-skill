/**
 * claim_builder.ts — on-chain instruction builders for Solana Merkle airdrops.
 *
 * Builds the `initialize` (publish root + fund) and `claim` (recipient proves
 * inclusion + receives tokens) instructions for the REAL Solana program
 * patterns documented in ../../skill/resources.md. Typed, `tsc --noEmit` clean,
 * and using a REAL Keccak-256 + SHA-256 implementation (`@noble/hashes`).
 *
 * Two verified program patterns are covered:
 *   1. Solana Foundation merkle-airdrop template (SOL):
 *        leaf = keccak256(pubkey || amount_le_u64 || 0x00), index-based verify,
 *        claim-status PDA = ["claim", airdrop_state, claimant].
 *        ix: initialize_airdrop(merkle_root, amount); claim_airdrop(amount, proof, leaf_index).
 *   2. Metaplex mpl-gumdrop (SPL token, mainnet gdrpGjVffourzkdDRrQmySw4aTHr8a3xmQzzxSwFD1a):
 *        leaf = keccak256(0x00 || index_le_u64 || claimant || mint || amount_le_u64),
 *        OpenZeppelin sorted-pair verify, per-index claim PDA.
 *        ix: claim(claim_bump, index, amount, claimant_secret, proof).
 *
 * Anchor serialization order = the on-chain argument declaration order, so the
 * byte layouts below mirror `lib.rs` exactly (verified 2026-06-27). Instruction
 * discriminators are the first 8 bytes of sha256("global:<ix_name>") (Anchor).
 *
 * Uses @solana/web3.js (1.98.x). A modern @solana/kit + Codama-codegen variant
 * for the official template is shown in ../../skill/resources.md.
 *
 * This module builds instructions; it does NOT sign or send. The user signs.
 */
import {
  PublicKey,
  TransactionInstruction,
  SystemProgram,
  Keypair,
} from "@solana/web3.js";
import { keccak_256 } from "@noble/hashes/sha3.js";
import { sha256 } from "@noble/hashes/sha2.js";

/** Keccak-256 (Solana BPF keccak; the on-chain hash for every verified program). */
export function keccak256(data: Uint8Array): Uint8Array {
  return keccak_256(data);
}

/** Anchor instruction discriminator = first 8 bytes of sha256("global:<ix_name>"). */
function discriminator(ixName: string): Uint8Array {
  return sha256(new TextEncoder().encode(`global:${ixName}`)).slice(0, 8);
}

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
  // Anchor: initialize_airdrop(merkle_root: [u8;32], amount: u64)
  //   disc(8) + merkle_root(32) + amount_le_u64(8)
  const data = new Uint8Array(8 + 32 + 8);
  data.set(discriminator("initialize_airdrop"), 0);
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
  // Anchor: claim_airdrop(amount: u64, proof: Vec<[u8;32]>, leaf_index: u64)
  //   disc(8) + amount_le_u64(8) + proof_len_u32(4) + proof(32*n) + leaf_index_le_u64(8)
  const data = new Uint8Array(8 + 8 + 4 + 32 * args.proof.length + 8);
  data.set(discriminator("claim_airdrop"), 0);
  data.set(leU64(args.amount), 8);
  const view = new DataView(data.buffer);
  view.setUint32(16, args.proof.length, true);
  for (let i = 0; i < args.proof.length; i++) data.set(args.proof[i], 20 + 32 * i);
  data.set(leU64(args.leafIndex), 20 + 32 * args.proof.length);
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
  payer: PublicKey; // claimant (signer, writable)
  temporal: PublicKey; // OTP signer (REQUIRED on-chain signer)
  fromTokenAccount: PublicKey; // distributor's vault ATA
  toTokenAccount: PublicKey; // claimant's ATA
  tokenProgram: PublicKey;
  claimBump: number; // u8 — bump of the distributor PDA
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
  if (args.claimBump < 0 || args.claimBump > 255) throw new Error("claimBump must be a u8");
  // Anchor: claim(claim_bump: u8, index: u64, amount: u64, claimant_secret: Pubkey, proof: Vec<[u8;32]>)
  //   disc(8) + claim_bump(1) + index_le_u64(8) + amount_le_u64(8) + claimant_secret(32)
  //         + proof_len_u32(4) + proof(32*n)
  const data = new Uint8Array(8 + 1 + 8 + 8 + 32 + 4 + 32 * args.proof.length);
  data.set(discriminator("claim"), 0);
  data[8] = args.claimBump;
  data.set(leU64(args.index), 9);
  data.set(leU64(args.amount), 17);
  data.set(args.claimantSecret.toBytes(), 25);
  const view = new DataView(data.buffer);
  view.setUint32(57, args.proof.length, true);
  for (let i = 0; i < args.proof.length; i++) data.set(args.proof[i], 61 + 32 * i);
  // On-chain Claim accounts (exact order, verified from lib.rs):
  //   distributor(w) claim_status(w) from(w) to(w) temporal(signer) payer(signer,w)
  //   system_program token_program   (8 accounts; NO rent)
  return new TransactionInstruction({
    programId: args.programId,
    keys: [
      { pubkey: args.distributor, isSigner: false, isWritable: true },
      { pubkey: claimStatus, isSigner: false, isWritable: true },
      { pubkey: args.fromTokenAccount, isSigner: false, isWritable: true },
      { pubkey: args.toTokenAccount, isSigner: false, isWritable: true },
      { pubkey: args.temporal, isSigner: true, isWritable: false },
      { pubkey: args.payer, isSigner: true, isWritable: true },
      { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
      { pubkey: args.tokenProgram, isSigner: false, isWritable: false },
    ],
    data: Buffer.from(data),
  });
}

// ---------------------------------------------------------------------------
// Verify helpers (mirror merkle_tree.py for a TS-side sanity check)
// ---------------------------------------------------------------------------

/** Index-based Merkle proof verification (Solana Foundation template).
 *  Rejects out-of-range indices (the on-chain official template shares this
 *  gap, but as a standalone primitive this must be safe). */
export function verifyIndexBased(
  root: Uint8Array,
  index: number,
  leaf: Uint8Array,
  proof: Uint8Array[],
): boolean {
  if (!Number.isInteger(index) || index < 0) return false;
  // index must fit in `proof.length` bits — no high bits allowed
  if (BigInt(index) >> BigInt(proof.length) !== 0n) return false;
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
