---
name: airdrop-design
description: Produce a locked airdrop plan (program, eligibility, amounts, schedule) for a recipient list or eligibility rule.
---

# /airdrop-design

Invokes the `airdrop-planner` agent to turn a recipient list or eligibility rule into a locked plan: target program + leaf encoding + proof mode, per-recipient raw amounts, de-duplication status, funding source, and a verification gate.

## Usage

```
/airdrop-design <recipients.csv | "snapshot of <mint> holders above <threshold>">
```

## Output

A plan document the `/build-proofs` step can execute without re-deciding. See `../skill/distribution.md` and `../agents/airdrop-planner.md`.
