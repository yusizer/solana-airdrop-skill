"""
merkle_tree.py — Solana airdrop Merkle distribution engine.

Pure-Python, ZERO third-party dependencies. Builds a Merkle tree over
airdrop leaves, generates per-recipient inclusion proofs, and verifies them
against a root. This is the deterministic core referenced by
../skill/merkle.md and exercised by ../tests/test_merkle.py + ../tests/test_eval.py.

Why a hand-rolled Keccak-256: every real Solana Merkle airdrop program on
mainnet hashes leaves with keccak256 (Solana BPF keccak syscall), NOT sha256.
`hashlib` ships SHA3-256 but NOT Keccak-256 (different padding), and requiring
pycryptodome would break the "zero-dep, runs in CI" promise. So Keccak-256 is
implemented here in pure Python (verified against the NIST/official test
vectors in ../tests/test_merkle.py — keccak256(b"") ==
c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470).

Supported leaf encodings — each matches a REAL, verified Solana program
(see ../skill/resources.md for primary-source links):
  - "solana-official" : keccak256(pubkey_32 || amount_le_u64 || 0x00)
        -> Solana Foundation merkle-airdrop template (SOL). Index-based verify.
  - "gumdrop"         : keccak256(0x00 || index_le_u64 || claimant_32 || mint_32 || amount_le_u64)
        -> Metaplex mpl-gumdrop, MAINNET gdrpGjVffourzkdDRrQmySw4aTHr8a3xmQzzxSwFD1a.
           OpenZeppelin sorted-pair verify with 0x00/0x01 domain separators.
  - "spl-vault"       : keccak256(index_le_u32 || pubkey_32 || amount_le_u64)
        -> SPL-token vault ATA pattern. Index-based verify.
  - "simple"          : sha256(pubkey_32 || amount_le_u64)
        -> teaching / custom-program path (stdlib sha256).

The tree shape and verification MUST match the target on-chain verifier:
  - index-based  : sibling side decided by the leaf index's bits (official
                   template, spl-vault). Proof = ordered sibling hashes + index.
  - sorted-pair  : siblings sorted by hash value at each level, with 0x00 leaf
                   / 0x01 node domain separators (Metaplex gumdrop / OpenZeppelin).

Claim accounts + double-claim PDA derivations for each program are documented
in ../skill/claim.md; the off-chain JS instruction builder is
../examples/claim_builder.ts.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Pure-Python Keccak-256 (Keccak[1088,512], NOT SHA3-256).
# ---------------------------------------------------------------------------

_KECCAK_RC = (
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
)
_KECCAK_RHO = (
    (0, 36, 3, 41, 18),
    (1, 44, 10, 45, 2),
    (62, 6, 43, 15, 61),
    (28, 55, 25, 21, 56),
    (27, 20, 39, 8, 14),
)
_MASK64 = (1 << 64) - 1


def _rotl64(x: int, n: int) -> int:
    return ((x << n) | (x >> (64 - n))) & _MASK64


def _keccak_f1600(lanes: list[list[int]]) -> list[list[int]]:
    """Keccak-f[1600] permutation on a 5x5 grid of 64-bit lanes (lane[x][y])."""
    for rnd in range(24):
        # theta
        C = [lanes[x][0] ^ lanes[x][1] ^ lanes[x][2] ^ lanes[x][3] ^ lanes[x][4]
             for x in range(5)]
        D = [C[(x - 1) % 5] ^ _rotl64(C[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                lanes[x][y] ^= D[x]
        # rho + pi
        B = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                B[y][(2 * x + 3 * y) % 5] = _rotl64(lanes[x][y], _KECCAK_RHO[x][y])
        # chi
        for x in range(5):
            for y in range(5):
                lanes[x][y] = B[x][y] ^ ((~B[(x + 1) % 5][y] & _MASK64) & B[(x + 2) % 5][y])
        # iota
        lanes[0][0] ^= _KECCAK_RC[rnd]
    return lanes


def keccak256(data: bytes) -> bytes:
    """Pure-Python Keccak-256 (rate=136B, capacity=64B, output=32B).

    Verified: keccak256(b"") == c5d2460186f7233c927e7db2dcc703c0e500b653
              ca82273b7bfad8045d85a470  (see tests/test_merkle.py).
    """
    rate = 136
    lanes = [[0] * 5 for _ in range(5)]  # lanes[x][y]

    # pad10*1 with Keccak domain (0x01 ... 0x80), NOT SHA3 (0x06 ... 0x80).
    msg = bytearray(data)
    msg.append(0x01)
    while len(msg) % rate != 0:
        msg.append(0x00)
    msg[-1] ^= 0x80

    for off in range(0, len(msg), rate):
        block = msg[off:off + rate]
        for i in range(rate // 8):  # 17 lanes per block
            lane = int.from_bytes(block[i * 8:(i + 1) * 8], "little")
            lanes[i % 5][i // 5] ^= lane
        lanes = _keccak_f1600(lanes)

    out = bytearray()
    for i in range(4):  # 32-byte digest = 4 lanes
        out += lanes[i % 5][i // 5].to_bytes(8, "little")
    return bytes(out)


def _h(data: bytes, hashf: str) -> bytes:
    if hashf == "keccak256":
        return keccak256(data)
    if hashf == "sha256":
        return hashlib.sha256(data).digest()
    raise ValueError(f"unknown hash function: {hashf}")


# ---------------------------------------------------------------------------
# Leaf encodings — each maps to a real Solana program.
# ---------------------------------------------------------------------------

LEAF_ENCODINGS = ("solana-official", "gumdrop", "spl-vault", "simple")

# Each encoding is bound to exactly ONE on-chain verify mode. Mixing them
# silently bricks 100% of claims (non-negotiable #2). Enforced in
# AirdropDistribution.build and build_drop.py.
ENCODING_MODE = {
    "solana-official": "index-based",
    "gumdrop": "sorted-pair",
    "spl-vault": "index-based",
    "simple": "index-based",
}


def leaf_hash(
    pubkey: bytes,
    amount: int,
    encoding: str = "solana-official",
    *,
    index: int = 0,
    mint: bytes | None = None,
) -> bytes:
    """Compute a leaf hash for the chosen real-program encoding.

    Args:
        pubkey:  32-byte decoded Solana address (the claimant).
        amount:  non-negative raw token amount (u64).
        encoding: one of LEAF_ENCODINGS.
        index:   recipient index (required by "gumdrop" and "spl-vault").
        mint:    32-byte mint address (required by "gumdrop").
    """
    if len(pubkey) != 32:
        raise ValueError("pubkey must be 32 bytes (decoded base58)")
    if amount < 0 or amount >= (1 << 64):
        raise ValueError("amount must fit in u64")
    if encoding == "solana-official":
        # keccak256(pubkey || amount_le_u64 || 0x00) — Solana Foundation template.
        return keccak256(pubkey + amount.to_bytes(8, "little") + b"\x00")
    if encoding == "simple":
        # sha256(pubkey || amount_le_u64) — teaching / custom-program path.
        return hashlib.sha256(pubkey + amount.to_bytes(8, "little")).digest()
    if encoding == "gumdrop":
        # keccak256(0x00 || index_le_u64 || claimant || mint || amount_le_u64)
        # — Metaplex mpl-gumdrop (mainnet).
        if mint is None or len(mint) != 32:
            raise ValueError("gumdrop leaf requires a 32-byte mint")
        if index < 0 or index >= (1 << 64):
            raise ValueError("index must fit in u64")
        return keccak256(
            b"\x00"
            + index.to_bytes(8, "little")
            + pubkey
            + mint
            + amount.to_bytes(8, "little")
        )
    if encoding == "spl-vault":
        # keccak256(index_le_u32 || pubkey || amount_le_u64) — SPL-token vault.
        if index < 0 or index >= (1 << 32):
            raise ValueError("index must fit in u32")
        return keccak256(index.to_bytes(4, "little") + pubkey + amount.to_bytes(8, "little"))
    raise ValueError(f"unknown encoding: {encoding} (choose from {LEAF_ENCODINGS})")


# ---------------------------------------------------------------------------
# Merkle tree — index-based (official template, spl-vault) by default.
# ---------------------------------------------------------------------------

ZERO_HASH = b"\x00" * 32


def _pair(left: bytes, right: bytes, hashf: str, mode: str) -> bytes:
    """Parent hash. sorted-pair mode adds the 0x01 domain separator and
    orders children by hash value (OpenZeppelin / Metaplex gumdrop)."""
    if mode == "sorted-pair":
        if left <= right:
            return _h(b"\x01" + left + right, hashf)
        return _h(b"\x01" + right + left, hashf)
    return _h(left + right, hashf)


@dataclass
class MerkleTree:
    """A Merkle tree over airdrop leaves.

    Two verification modes:
      - "index-based" (default): sibling side decided by the leaf index's
        bits — matches the Solana Foundation template and the spl-vault
        pattern. Proof = ordered sibling hashes; verifier needs the index.
      - "sorted-pair": OpenZeppelin-style sorted pairs with 0x00 leaf /
        0x01 node domain separators — matches Metaplex mpl-gumdrop (mainnet).
    """

    leaves: list[bytes]
    levels: list[list[bytes]]  # levels[0] = leaves, levels[-1] = [root]
    hashf: str = "keccak256"
    mode: str = "index-based"
    root: bytes = b""

    @classmethod
    def from_leaves(
        cls,
        leaves: list[bytes],
        hashf: str = "keccak256",
        mode: str = "index-based",
    ) -> "MerkleTree":
        if not leaves:
            raise ValueError("need at least one leaf")
        if mode not in ("index-based", "sorted-pair"):
            raise ValueError(f"unknown mode: {mode}")
        levels = [list(leaves)]
        # Right-pad with a zero-hash to a power of two (index-based) — safe
        # because the verifier re-derives the same padding from the index.
        n = len(leaves)
        if n & (n - 1):
            pad = (1 << n.bit_length()) - n
            levels[0].extend([ZERO_HASH] * pad)
        while len(levels[-1]) > 1:
            cur = levels[-1]
            nxt = [_pair(cur[i], cur[i + 1], hashf, mode) for i in range(0, len(cur), 2)]
            levels.append(nxt)
        root = levels[-1][0] if levels[-1] else b""
        return cls(leaves=leaves, levels=levels, hashf=hashf, mode=mode, root=root)

    def proof(self, index: int) -> list[bytes]:
        """Ordered sibling hashes for leaf `index` (index-based mode)."""
        if not 0 <= index < len(self.leaves):
            raise IndexError("leaf index out of range")
        siblings: list[bytes] = []
        idx = index
        for level in self.levels[:-1]:
            siblings.append(level[idx ^ 1])
            idx >>= 1
        return siblings

    @staticmethod
    def verify(
        root: bytes,
        index: int,
        leaf: bytes,
        proof: list[bytes],
        hashf: str = "keccak256",
        mode: str = "index-based",
    ) -> bool:
        """Verify `leaf` at `index` commits to `root` via `proof`."""
        acc = leaf
        if mode == "sorted-pair":
            for sibling in proof:
                acc = _pair(acc, sibling, hashf, mode)
            return acc == root
        idx = index
        # Reject out-of-range indices: a proof of length L only authenticates
        # indices in [0, 2^L). Indices with bits above the proof depth must not
        # verify (without this, index i + 2^L reuses i's proof). The official
        # on-chain template shares this gap (mitigated there by per-claimant
        # PDA + claimant-bound leaf); as a standalone primitive we close it.
        if idx < 0 or idx >= (1 << len(proof)):
            return False
        for sibling in proof:
            if idx & 1:
                acc = _h(sibling + acc, hashf)
            else:
                acc = _h(acc + sibling, hashf)
            idx >>= 1
        return acc == root


@dataclass
class AirdropDistribution:
    """A prepared airdrop: recipients, tree, per-recipient proofs, root."""

    recipients: list[tuple[bytes, int]]
    tree: MerkleTree
    proofs: list[list[bytes]] = field(default_factory=list)
    root_hex: str = ""

    @classmethod
    def build(
        cls,
        recipients: list[tuple[bytes, int]],
        encoding: str = "solana-official",
        mode: str = "index-based",
        mint: bytes | None = None,
    ) -> "AirdropDistribution":
        if encoding not in ENCODING_MODE:
            raise ValueError(f"unknown encoding: {encoding} (choose from {LEAF_ENCODINGS})")
        required_mode = ENCODING_MODE[encoding]
        if mode != required_mode:
            raise ValueError(
                f"encoding '{encoding}' requires mode '{required_mode}' (got '{mode}'). "
                f"A mismatch silently bricks 100% of claims on-chain. "
                f"({ENCODING_MODE})"
            )
        hashf = "sha256" if encoding == "simple" else "keccak256"
        leaves = [
            leaf_hash(pk, amt, encoding, index=i, mint=mint)
            for i, (pk, amt) in enumerate(recipients)
        ]
        tree = MerkleTree.from_leaves(leaves, hashf=hashf, mode=mode)
        proofs = [tree.proof(i) for i in range(len(recipients))]
        return cls(
            recipients=recipients,
            tree=tree,
            proofs=proofs,
            root_hex=tree.root.hex(),
        )

    def verify_all(self) -> int:
        """Count of recipients whose proof verifies against the root."""
        ok = 0
        for i in range(len(self.recipients)):
            leaf = self.tree.leaves[i]  # already encoded with the tree's convention
            if self.tree.verify(
                self.tree.root, i, leaf, self.proofs[i], self.tree.hashf, self.tree.mode
            ):
                ok += 1
        return ok


if __name__ == "__main__":
    # Self-check: Keccak-256 test vector + a 4-recipient round-trip.
    assert keccak256(b"") == bytes.fromhex(
        "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    ), "keccak256 empty-vector mismatch"
    pk = lambda i: bytes([i]) * 32  # synthetic 32-byte addresses
    recips = [(pk(i), 1_000 * (i + 1)) for i in range(4)]
    dist = AirdropDistribution.build(recips, encoding="solana-official")
    assert dist.verify_all() == 4, "round-trip failed"
    print(f"OK — root={dist.root_hex}, 4/4 proofs verify")
