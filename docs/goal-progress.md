# Software milestone checkpoints

Objective: deliver the software milestone of [roadmap #9](https://github.com/smestrada/pystitch/issues/9) in smestrada/pystitch. Repository: `C:\Users\sally\Projects\Personal\pystitch`. Baseline: `dbdc82c`.

## Requirements and order

| Issue | Deliverable | State | Evidence |
|---|---|---|---|
| #5 | Python 3.14, wheel/sdist CI, complete required merge gate | In progress | Plan: `docs/superpowers/plans/2026-11-16-distribution-ci.md` |
| #2 | Non-mutating inspection API and explicit units | Pending | Depends on measurable generated patterns |
| #4 | Atomic path writes and clear IO errors | Pending | Failure-injection coverage required |
| #3 | Generic preflight and opt-in SE700 profile | Pending | Builds on #2; official machine references required |
| #8 | Installed inspect/preview/validate/convert CLI | Pending | Builds on #2/#3/#4, artifact verification |
| #6 | Fork identity, build, pinning and rollback | Pending | Release gates depend on #5 |
| #7 | Corpus schema/harness/collection preparation | Pending | Independent exports and physical sew-outs remain manual |

## Invariants

- Target only this fork. No upstream changes, global installs, installed Python changes, or bundled Ink/Stitch replacement.
- Preserve user changes. PRs merge only with required CI and CodeQL passing; never bypass protection.
- No PyPI publication or public rename. Preserve original attribution and MIT license.
- Do not close #7 or #9 or claim machine verification before independent files and physical evidence exist.
- Inspection is non-mutating; validation does not silently resize, center or repair.

## Decisions

- Ruling: reuse the user-designated checkout on focused branches instead of creating another worktree â€” consistent with the requested location and prior workflow; cost if wrong is interference with concurrent local work, mitigated by checking the working tree before edits and switches.
- Ruling: CI uses a full Python 3.9â€“3.14 OS matrix plus wheel/sdist verification on Python 3.14 across all three OSes â€” source installation still exercises packaging on every supported interpreter; cost if wrong is artifact-only behavior differing on an older interpreter, which the installed-package smoke checks and future fixtures should expose.
- Ruling: replace fragile per-matrix required names with a stable aggregate only after the new jobs and gate pass, retaining existing requirements throughout the transition â€” equivalent coverage must be demonstrated before removing obsolete names; cost if wrong is a blocked merge or missed failure, so the gate explicitly rejects failed/cancelled/skipped dependencies.

## Current checkpoint

Goal created and issue scope revalidated. Existing main is clean at `dbdc82c`. First implementation branch will address #5. Physical evidence is deliberately pending, not a blocker for the software work.

### Issue #5: artifact verifier

Branch: feat/python314-distribution-ci. Baseline: 245 tests OK (2 skips). Verifier availability test failed before implementation; all 9 infrastructure tests then passed. Actual wheel and sdist metadata checks passed; separately installed copies each ran 245 tests OK (2 skips), with import and metadata origins inside their fresh environments. Evidence: .superpowers/sdd/2026-11-16-distribution-ci/distribution-report.json and installed-check-1 logs. No global packages were installed.

Pre-flight: Task 1 produces the verifier CLI consumed by Task 2; argument names and report fields agree. Task 3 integrates only after hosted evidence.
