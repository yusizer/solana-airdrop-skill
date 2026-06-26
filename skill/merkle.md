# Merkle trees for Solana airdrops — leaves, proofs, verification

This is the cryptography that makes Merkle airdrops work — and the part that
bricks them when done wrong. Read it before generating any leaf or proof.
The executable reference is `../examples/merkle_tree.py` (zero-dep, pure-Python
Keccak-256); the tests are `../tests/test_merkle.py`.

## Why Merkle for airdrops

Distributing tokens to N recipients naively costs O(N) on-chain storage (one
account per recipient). A Merkle tree compresses the recipient set into a
single 32-byte **root** published on-chain; each recipient proves inclusion
with a O(log N) **proof** of sibling hashes at claim time. Storage is O(1);
verification is O(log N). The trade: correctness is **convention-fragile**.

## The leaf — the one thing you must get exactly right

A leaf is a hash of a recipient's claim data. Three real Solana programs use
three different leaf layouts (primary sources in `resources.md`):

| Program | Leaf |
|---|---|
| Solana Foundation template (SOL) | `keccak256(pubkey_32 ‖ amount_le_u64 ‖ 0x00)` |
| Metaplex mpl-gumdrop (SPL, mainnet) | `keccak256(0x00 ‖ index_le_u64 ‖ claimant_32 ‖ mint_32 ‖ amount_le_u64)` |
| SPL-token vault pattern | `keccak256(index_le_u32 ‖ pubkey_32 ‖ amount_le_u64)` |

Four things every leaf must match the on-chain verifier on — get ANY wrong and
100% of claims fail:

1. **Hash function = keccak256.** Not sha256, not SHA3-256 (different padding).
   Solana BPF's keccak syscall is keccak-256. `examples/merkle_tree.py` ships a
   pure-Python keccak-256 (verified against the NIST KAT: `keccak256("") ==
   c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470`).
2. **Little-endian amounts.** Solana is LE. `amount.to_bytes(8, "little")`.
3. **All fields the on-chain `claim` includes.** The official template appends a
   `0x00` isClaimed byte; omitting it changes every leaf.
4. **Field order + domain separators.** Gumdrop prefixes `0x00` and binds the
   index + mint; the official template does not.

## The tree

Binary, leaves right-padded with a zero-hash to a power of two (index-based
mode). Parent = `H(left ‖ right)` (index-based) or `H(0x01 ‖ sorted(left,right))`
(sorted-pair / OpenZeppelin, used by gumdrop). The root is the single top hash.

- **index-based** (official template, spl-vault): sibling side is decided by
  the leaf index's bits at each level. Proof = ordered sibling hashes + the
  index. `MerkleTree.verify(root, index, leaf, proof)`.
- **sorted-pair** (gumdrop / OpenZeppelin): siblings are sorted by hash value
  at each level, with `0x00` leaf / `0x01` node domain separators. Proof does
  not need an index. `mode="sorted-pair"`.

## Proof generation + verification

```python
from merkle_tree import AirdropDistribution, MerkleTree, leaf_hash

# build
dist = AirdropDistribution.build(recipients, encoding="solana-official")
print(dist.root_hex)                    # publish this on-chain
proof = dist.proofs[i]                  # give recipient i this list of 32-byte hashes

# verify (recipient side, or your pre-launch gate)
MerkleTree.verify(dist.tree.root, i, dist.tree.leaves[i], proof)  # -> True
dist.verify_all()                       # -> N (the pre-launch gate)
```

Proof length = ⌈log2(N)⌉. For 1,000,000 recipients that's 20 hashes — 640 bytes
per claim, regardless of the recipient count.

## The four failure modes (each bricks 100% of claims)

These are the baselines in `../tests/test_eval.py` — each is a real, observed
mistake, and each scores 0/N claimable against a correctly-published root:

1. **sha256 instead of keccak256** — the stdlib default; produces a completely
   different hash chain.
2. **big-endian amount** — Solana is little-endian; one wrong byte per leaf.
3. **missing isClaimed `0x00` byte** (official template) — changes every leaf.
4. **convention mismatch** — sorted-pair proofs against an index-based verifier
   (the JS-helper bug flagged in the official template's `verifyGillProof`).

## Reproducibility

`merkle_tree.py` is deterministic: the same recipient list + encoding always
yields the same root. The build + verify round-trip is unit-tested in
`../tests/test_merkle.py` (19 tests), and the claimable-rate eval is
`../tests/test_eval.py` (see `../docs/EVAL.md`).
