# Architecture Decision Records

This directory contains architecture decision records for `clarify-engine-ai`.

## Numbering Convention

ADR numbers are stable identifiers, not a strict global sequence. Documents with
the same number may coexist when they describe **orthogonal decision areas** and
the filename keeps the topic unambiguous. Current orthogonal pairs:

| Number | A — file | B — file |
|--------|----------|----------|
| 004 | [`004-prompt-management.md`](004-prompt-management.md) → **ADR-004A (Prompt Management)** | [`004-ui-operation-modes.md`](004-ui-operation-modes.md) → **ADR-004B (UI Operation Modes)** |
| 007 | [`007-error-handling.md`](007-error-handling.md) → **ADR-007A (Error Handling)** (Accepted) | [`007-canonical-cache-draft.md`](007-canonical-cache-draft.md) → **ADR-007B (Canonical Cache / Pivot)** (Draft) |

### Rules

1. **Same number, disjoint scope.** Two `NNN-*` files coexist only when the
   subjects are orthogonal (e.g. UI modes vs. prompt storage). They must not
   contradict each other; if they do, supersede one and update the status of
   both.
2. **Disambiguation notation.** In discussions, PR descriptions, logs, and
   commit messages refer to such ADRs as **«ADR-NNNA (Topic)»** and
   **«ADR-NNNB (Topic)»**. Each file must contain a top-level «Numbering Note»
   blockquote pointing at its sibling and linking back to this README.
3. **Renumbering only on promotion.** Draft/Concept ADRs sharing a number with
   an Accepted ADR are renumbered **only** when (and if) their status moves
   beyond Draft. Accepted ADRs keep their number forever.
4. **Supersession is by status + cross-link, not by number.** When a new ADR
   supersedes an existing decision in the same area, update **Status** and
   cross-links in both documents instead of relying on the number alone.

## Status Glossary

| Status | Meaning |
|--------|---------|
| `Accepted` | Architectural contract is in effect; production code must conform. |
| `Concept` / `Draft` | Decision sketch; **not** part of the deployed architecture. May still influence backlog planning but cannot be cited as a binding contract. |
| `Pivot` | Decision was investigated and intentionally *not* promoted to Accepted; the document remains as evidence of the pivot. |
| `Superseded by ADR-X` | Replaced by a later ADR; kept for history. |

## BL-40 Alignment Note (2026-05-19)

The BL-40 ADR-sync (issue [#166](https://github.com/G-Ivan-A/clarify-engine-ai/issues/166))
reaffirmed every Accepted ADR (`001, 002, 004A, 004B, 005, 006, 007A, 008, 009`)
against [`docs/CONCEPT.md`](../CONCEPT.md) v2.5 and the
[BL-34 architecture-consistency audit](../audit/2026-05-19_bl-34_architecture-consistency-audit_v1.md).
Draft ADRs (`003`, `007B`) remain Draft/Pivot and are **explicitly excluded**
from the Pilot architecture per CONCEPT.md §2.3 pre-deploy invariants. See each
ADR's §History v1.1 entry for the diff.
