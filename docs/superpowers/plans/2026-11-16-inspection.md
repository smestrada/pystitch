# Inspection API Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task-by-task. Continuous execution and routine design choices are authorized by the active goal.

**Goal:** Complete [issue #2](https://github.com/smestrada/pystitch/issues/2): a reusable, non-mutating JSON inspection report with explicit mm units.

**Architecture:** Add a standard-library-only `EmbInspection` module and public `inspect_pattern` function. Analyze stored commands directly; do not invoke normalization, writers, filler threads or the encoder. Counts describe stored records; geometry is a conservative observation of ordinary command coordinates, with completeness flags and explicit diagnostics for malformed/unresolved instructions.

**Tech Stack:** Python >=3.9, unittest, existing EmbPattern/constants, JSON.

**Spec:** Issue #2; `docs/goal-progress.md` records the overall authorized milestone.

## Global Constraints

- No mutation, reordering, automatic repair, digitizing or physical sew-quality claims.
- Native coordinates are tenths of mm; divide by 10 for reported mm.
- Preserve public compatibility and add no runtime dependencies.
- Keep counts distinct: stored records, needle-down records, movement records, thread entries, color changes and color blocks.
- Heuristic thresholds are configurable, reported, optional via None, and never machine-limit errors.

## Design decisions

- Public interface: `inspect_pattern(pattern, *, short_stitch_mm=0.3, long_stitch_mm=4.0, long_jump_mm=12.0) -> dict`. Thresholds must be finite nonnegative real numbers or None; short must not exceed long when both enabled.
- Schema version 1; JSON uses finite numbers or null, never NaN/Infinity. Do not include user metadata or arbitrary thread objects.
- Needle-down records are STITCH and SEQUIN_EJECT. SEW_TO/NEEDLE_AT and other encoder instructions are counted by name but cannot predict final stitch count or geometry without normalization; mark geometry incomplete. No normalization occurs here.
- Ordinary commands below 0x10 (except undefined values) carry stored endpoints, including TRIM/STOP/END/speed/color commands. Movement count includes ordinary records whose endpoint differs from the previous known endpoint; origin is (0,0). Envelope includes origin and all finite ordinary endpoints, even coordinate-bearing trims. Needle bounds include only needle-down endpoints, not origin unless actually punctured.
- Lengths measure incoming STITCH/SEQUIN_EJECT and JUMP segments from the preceding known ordinary endpoint, starting at origin. Invalid/unknown/unresolved records break position continuity; the next finite ordinary endpoint restores it but its incoming length is excluded. Distances for controls are included in the envelope and movement count but not stitch/jump summaries.
- Color-block count matches existing get_as_colorblocks boundaries (including nonsewing blocks) without generating filler threads. Thread count means stored thread entries, not inferred colors.
- Bounds and lengths each carry `complete`; partial observed measurements remain explicit. Overall geometry completeness also becomes false on records after END. Counts cover all stored records and include an after-END diagnostic; this report is not an executed/encoded simulation.
- Empty needle-down designs receive an empty-design warning even if control/jump records exist. Unknown/nonfinite records produce errors; unresolved encoder instructions produce warnings and incomplete geometry. Threshold warnings are informational heuristics.

## Review Focus

- Encoded thread-change flags must be masked without misclassifying command IDs.
- Missing/nonfinite/overflowing coordinates must not crash, poison JSON, or bridge unknown distances.
- Matrix/option payloads must not be interpreted as positions; incomplete geometry cannot imply hoop fit.
- Empty, control-only, trailing-after-END and zero-length patterns must have explicit meanings.
- Report generation must not call random filler generation or change pattern/extras/thread objects.

### Task 1: Report API with measured regression cases

**Files:** create `src/pystitch/EmbInspection.py`, `test/test_inspection.py`; modify `src/pystitch/__init__.py`.

**Interfaces:** `inspect_pattern(pattern, *, short_stitch_mm=0.3, long_stitch_mm=4.0, long_jump_mm=12.0) -> dict`; schema keys `schema_version`, `units`, `counts`, `commands`, `bounds_mm`, `lengths_mm`, `thresholds_mm`, `diagnostics`, `geometry_complete`.

- [x] Test a 3-4-5 segment, negative/off-origin points, outlying jump and trim endpoints, independent counts and color block boundaries; verify exact mm expectations.
- [x] Test zero-length/disabled/configurable thresholds and strict JSON serialization.
- [x] Test invalid coordinates/records/commands, unknown commands, matrix/option payloads, END trailing records, empty/control-only patterns, encoded flags and input nonmutation.
- [x] Run focused tests; expect failure because public API is absent.
- [x] Implement the report and public export without changing existing methods.
- [x] Run focused tests, full library suite and infrastructure tests; expect all pass. Run graphify update . after code edits.
- [x] Commit API and regressions with recorded red/green evidence.

### Task 2: Documentation, review and integration

**Files:** create `docs/inspection.md`; modify `docs/goal-progress.md`, README.md and plan checkboxes.

**Interfaces:** documented API/schema matches Task 1. Later #3/#8 consume report fields without independently redefining units or counts.

- [ ] Document the JSON example, thresholds, raw-vs-encoded semantics, incomplete measurements, color blocks and limits.
- [ ] Execute the documented example and strict-JSON check; build/check wheel and sdist and run both installed suites outside checkout.
- [ ] Obtain one fresh-context whole-branch review; fix important findings with regression evidence.
- [ ] Push focused PR, inspect exact-head full CI and CodeQL, merge normally only when green, sync local main and verify main checks.
- [ ] Close #2 and update #9 with demonstrated evidence; retain #7/#9 open. Update checkpoint with #5 completion and #2 outcome.
