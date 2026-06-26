---
name: verify-drop
description: Verify every proof in a proofs.json against its root — the gate before publishing the root on-chain.
---

# /verify-drop

The non-negotiable gate before launch. Loads `proofs.json`, re-derives each leaf with the target encoding, and verifies each proof against the published root. Reports `N/N` or the first failure.

## Usage

```
/verify-drop <proofs.json>
```

## Rule

A root may only be published on-chain once this command reports `N/N`. A root built with a wrong encoding is unrecoverable after launch. See `../rules/verify-before-launch.md`.
