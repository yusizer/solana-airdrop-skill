# Rule — verify before launch

**No Merkle root is published on-chain until every recipient's proof verifies against it (`verify_all() == N`).**

## Why

A root computed with a wrong leaf encoding, wrong endianness, or a mismatched verify convention is **unrecoverable after launch**. Claimants will submit proofs that the on-chain verifier rejects; the allocated tokens are stranded with no on-chain remediation short of re-initializing a new drop. This is the single most expensive mistake in airdrop engineering, and it is binary — one wrong byte bricks 100% of claims.

## How to apply

1. Build the tree with the target program's exact encoding (`skill/resources.md`).
2. Run `AirdropDistribution.verify_all()` (or `/verify-drop`). It MUST return N.
3. Only then hand the root to `initialize_airdrop` / the publish step.
4. If `verify_all()` < N: the encoding is wrong. Stop. Re-confirm the target on-chain verifier's leaf layout and proof mode. Do not "fix" by patching the root.

## What this rule prevents

Publishing a root that no recipient can claim against. Related: [[freshness-before-publish]].
