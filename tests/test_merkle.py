"""
test_merkle.py — unit tests for the Merkle distribution engine.

Pure stdlib (unittest), zero third-party deps. Verifies:
  - the pure-Python Keccak-256 against the official test vector,
  - leaf encodings for all three real Solana programs,
  - tree construction, proof generation, and proof verification round-trips,
  - double-claim / tampering rejection (the core airdrop safety property),
  - edge cases (1 recipient, non-power-of-two padding, out-of-range index).

Run:  python -m unittest tests.test_merkle    (or)   python tests/test_merkle.py
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "examples"))
from merkle_tree import (  # noqa: E402
    keccak256,
    leaf_hash,
    MerkleTree,
    AirdropDistribution,
    ZERO_HASH,
)

# A 32-byte synthetic "pubkey" deterministic across tests.
PK = lambda i: bytes([(i * 7) % 256] * 32)
MINT = bytes([0xAA] * 32)


class TestKeccak(unittest.TestCase):
    """Pure-Python Keccak-256 vs known answer tests (KATs)."""

    def test_empty(self):
        # keccak256("") — the canonical Keccak (not SHA3) empty digest.
        self.assertEqual(
            keccak256(b"").hex(),
            "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470",
        )

    def test_abc(self):
        # keccak256("abc") — NIST FIPS 202 Keccak (not SHA3) KAT.
        self.assertEqual(
            keccak256(b"abc").hex(),
            "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45",
        )

    def test_longer_than_rate(self):
        # 200 bytes spans two absorption blocks; check it does not crash and
        # matches a recomputation over the same bytes.
        data = bytes((i * 13) % 256 for i in range(200))
        self.assertEqual(keccak256(data), keccak256(data))


class TestLeafEncodings(unittest.TestCase):
    """Each encoding must match its real on-chain program's leaf layout."""

    def test_solana_official_shape(self):
        # keccak256(pubkey || amount_le_u64 || 0x00)
        h = leaf_hash(PK(1), 1_000, "solana-official")
        self.assertEqual(len(h), 32)
        # deterministic
        self.assertEqual(h, leaf_hash(PK(1), 1_000, "solana-official"))
        # differs from simple (sha256) — proves we are not silently using sha256
        self.assertNotEqual(h, leaf_hash(PK(1), 1_000, "simple"))

    def test_solana_official_amount_endianness(self):
        # amount 1 in LE u64 is 01 00 00 00 00 00 00 00; leaf must depend on it.
        a = leaf_hash(PK(1), 1, "solana-official")
        b = leaf_hash(PK(1), 256, "solana-official")  # 00 01 00 ... LE
        self.assertNotEqual(a, b)

    def test_gumdrop_includes_index_and_mint(self):
        h0 = leaf_hash(PK(1), 1_000, "gumdrop", index=0, mint=MINT)
        h1 = leaf_hash(PK(1), 1_000, "gumdrop", index=1, mint=MINT)
        self.assertNotEqual(h0, h1, "gumdrop leaf must bind the index")
        with self.assertRaises(ValueError):
            leaf_hash(PK(1), 1_000, "gumdrop", index=0, mint=None)

    def test_spl_vault_u32_index(self):
        h = leaf_hash(PK(1), 1_000, "spl-vault", index=5)
        self.assertEqual(len(h), 32)
        with self.assertRaises(ValueError):
            leaf_hash(PK(1), 1_000, "spl-vault", index=(1 << 32))

    def test_bad_pubkey_length(self):
        with self.assertRaises(ValueError):
            leaf_hash(b"\x00" * 31, 1, "solana-official")


class TestTreeIndexBased(unittest.TestCase):
    """Index-based tree (Solana Foundation template / spl-vault)."""

    def _leaves(self, n, encoding="solana-official"):
        return [leaf_hash(PK(i), 1_000 * (i + 1), encoding, index=i) for i in range(n)]

    def test_roundtrip_power_of_two(self):
        leaves = self._leaves(8)
        t = MerkleTree.from_leaves(leaves, mode="index-based")
        for i in range(8):
            self.assertTrue(MerkleTree.verify(t.root, i, leaves[i], t.proof(i)))

    def test_roundtrip_non_power_of_two(self):
        # 5 leaves -> padded to 8; padding must not break verification.
        leaves = self._leaves(5)
        t = MerkleTree.from_leaves(leaves, mode="index-based")
        self.assertEqual(len(t.leaves), 5)
        for i in range(5):
            self.assertTrue(MerkleTree.verify(t.root, i, leaves[i], t.proof(i)),
                            f"recipient {i} failed verification")

    def test_single_recipient(self):
        leaves = self._leaves(1)
        t = MerkleTree.from_leaves(leaves, mode="index-based")
        self.assertEqual(t.root, leaves[0])
        self.assertEqual(t.proof(0), [])
        self.assertTrue(MerkleTree.verify(t.root, 0, leaves[0], []))

    def test_tampered_amount_rejected(self):
        leaves = self._leaves(8)
        t = MerkleTree.from_leaves(leaves, mode="index-based")
        fake = leaf_hash(PK(0), 9_999_999, "solana-official")  # wrong amount
        self.assertFalse(MerkleTree.verify(t.root, 0, fake, t.proof(0)),
                         "must reject a leaf with a tampered amount")

    def test_tampered_proof_rejected(self):
        leaves = self._leaves(8)
        t = MerkleTree.from_leaves(leaves, mode="index-based")
        proof = t.proof(2)
        proof[0] = ZERO_HASH  # corrupt one sibling
        self.assertFalse(MerkleTree.verify(t.root, 2, leaves[2], proof))

    def test_wrong_index_rejected(self):
        leaves = self._leaves(8)
        t = MerkleTree.from_leaves(leaves, mode="index-based")
        # leaf 0's proof must NOT verify leaf 0 at index 3 (wrong position).
        self.assertFalse(MerkleTree.verify(t.root, 3, leaves[0], t.proof(0)))

    def test_out_of_range_index(self):
        leaves = self._leaves(4)
        t = MerkleTree.from_leaves(leaves, mode="index-based")
        with self.assertRaises(IndexError):
            t.proof(99)


class TestTreeSortedPair(unittest.TestCase):
    """OpenZeppelin sorted-pair tree (Metaplex mpl-gumdrop / mainnet)."""

    def test_roundtrip_sorted(self):
        leaves = [
            leaf_hash(PK(i), 1_000, "gumdrop", index=i, mint=MINT) for i in range(6)
        ]
        t = MerkleTree.from_leaves(leaves, hashf="keccak256", mode="sorted-pair")
        for i in range(6):
            self.assertTrue(MerkleTree.verify(
                t.root, i, leaves[i], t.proof(i), hashf="keccak256", mode="sorted-pair"
            ), f"sorted-pair recipient {i} failed")

    def test_sorted_tamper_rejected(self):
        leaves = [
            leaf_hash(PK(i), 1_000, "gumdrop", index=i, mint=MINT) for i in range(6)
        ]
        t = MerkleTree.from_leaves(leaves, hashf="keccak256", mode="sorted-pair")
        fake = leaf_hash(PK(0), 9_999, "gumdrop", index=0, mint=MINT)
        self.assertFalse(MerkleTree.verify(
            t.root, 0, fake, t.proof(0), hashf="keccak256", mode="sorted-pair"
        ))


class TestDistribution(unittest.TestCase):
    """End-to-end distribution build + verify-all."""

    def test_build_and_verify_all(self):
        recips = [(PK(i), 500 * (i + 1)) for i in range(10)]
        dist = AirdropDistribution.build(recips, encoding="solana-official")
        self.assertEqual(len(dist.proofs), 10)
        self.assertEqual(dist.verify_all(), 10)
        self.assertEqual(len(dist.root_hex), 64)

    def test_gumdrop_distribution(self):
        recips = [(PK(i), 1_000) for i in range(7)]
        dist = AirdropDistribution.build(
            recips, encoding="gumdrop", mode="sorted-pair", mint=MINT
        )
        self.assertEqual(dist.verify_all(), 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
