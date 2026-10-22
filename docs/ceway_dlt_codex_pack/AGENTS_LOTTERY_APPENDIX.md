# Suggested AGENTS.md Appendix — Lottery/DLT

Apply only if compatible with the repository's existing AGENTS.md; do not overwrite stronger repo rules.

## DLT module invariants
- Domain collision/statistics code must be pure and deterministic for fixed inputs.
- No network/database access from collision engine.
- Every model run requires `target_issue` and `history_cutoff_issue`.
- Queries must not include draws after cutoff.
- Frozen runs are immutable; create a new version instead of editing.
- Keep model-source (model/random/package) separate from bet-expression (single/compound/dantuo/addon/multiplier).
- Never replace complete-combination collision analysis with single-number frequency/omission.
- For every candidate ticket persist/return both `N_ab` and `N_k`.
- Batch analytics must include both `M_k` (pair counts) and `U_k` (unique candidate counts with >=1 occurrence).
- Production randomness uses a secure system random source; seeded randomness is test/research only.
- No automatic purchasing or payment integration in this module.
