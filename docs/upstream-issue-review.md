# Upstream issue review

Reviewed 2026-11-16 against upstream main `0593ccd8271fa565548ed38774ea9a27d598b9f3`.
Scope: all 21 open issues and both open pull requests in `inkstitch/pystitch`.
Changes belong to `smestrada/pystitch`, not to the original repository or the installed Ink/Stitch executable.

## Repairs included

- CI: retain Python 3.9 testing on Ubuntu 24.04; remove a whole-interpreter cache whose version output and dependency filename were incorrect.
- PES/PEC colors: replace greedy palette allocation with a global minimum-cost assignment, adapted from [emerzn's PR #139](https://github.com/inkstitch/pystitch/pull/139). Preserve the reserved-entry exclusion introduced by upstream #140. Repeated identical threads retain a shared index; excess threads reuse available assignments. The global optimality guarantee applies when the distinct requested threads fit the available palette.
- DAT: [#128](https://github.com/inkstitch/pystitch/issues/128), runtime portion only. Replace the nonexistent `needle_out` call with the established `needle_change` API, preserving the needle number and following movement.
- DST: [#98](https://github.com/inkstitch/pystitch/issues/98). Encode trim movements towards the interior and return to the starting location, so intermediate jump records stay within design bounds. Degenerate dimensions use zero movement on that axis. Verified on raw records as well as decoded trim commands; physical trim behavior is not machine-verified.

The assignment algorithm and palette strategy are adapted from PR #139 by GitHub contributor `emerzn`, under the repository's MIT license. Input validation, reserved-entry handling and additional regression checks were added for this fork. This does not claim authorship of the upstream proposal or that it resolves every Ink/Stitch color-management issue.

## All open issues

| Issue | Assessment and decision |
|---|---|
| [#143 DSB writer proposal](https://github.com/inkstitch/pystitch/issues/143) | New export format, not a confirmed regression. Defer until we have independently verified reference files and a use for DSB. |
| [#137 format plugins](https://github.com/inkstitch/pystitch/issues/137) | Architectural enhancement; no need to change the format-registration system for SE700/PES work. |
| [#134 convert command](https://github.com/inkstitch/pystitch/issues/134) | Usage confusion: Python code entered in Bash, then missing `import pystitch`. No library fix indicated. Run conversion inside Python after importing pystitch. |
| [#128 type errors / DAT crash](https://github.com/inkstitch/pystitch/issues/128) | Fixed and reproduced the DAT crash. Broad typing cleanup remains separate; retain float-capable stitch coordinates. |
| [#104 PCS dimensions](https://github.com/inkstitch/pystitch/issues/104) | Format decoding/scale claim with proposed implementations but no independently checked fixtures here. Defer rather than change coordinate scaling speculatively. |
| [#103 JEF centering](https://github.com/inkstitch/pystitch/issues/103) | Requires known-good JEF and hoop metadata comparison. Outside the current Brother/PES path. |
| [#98 DST trim bounds](https://github.com/inkstitch/pystitch/issues/98) | Reproduced and fixed with raw-record boundary and trim round-trip tests. |
| [#92 DST UTF-8 decoding](https://github.com/inkstitch/pystitch/issues/92) | Current reader already catches UnicodeDecodeError and skips the offending metadata. Added a regression proving stitch data is still read. Metadata may be omitted; arbitrary legacy encodings are not reconstructed. |
| [#86 PCS writer](https://github.com/inkstitch/pystitch/issues/86) | New format support. Needs fixtures and trusted reader or machine comparison before adoption. |
| [#75 VP3 trims](https://github.com/inkstitch/pystitch/issues/75) | Genuine machine-facing report, but software round-trips alone cannot establish machine trimming. Needs comparative fixtures and affected-machine verification. Do not guess a binary-format change. |
| [#67 stream modes](https://github.com/inkstitch/pystitch/issues/67) | API/error-message enhancement: binary formats need binary streams. Defer changes to shared IO behavior; never silently reopen a caller's stream. |
| [#64 tie-on/off contingencies](https://github.com/inkstitch/pystitch/issues/64) | Stitch-policy work affecting short/zero-length stitches. Needs focused tests and physical sew-outs; separate from file-IO repairs. |
| [#63 JEF front-loaded jumps](https://github.com/inkstitch/pystitch/issues/63) | Alternative jump splitting; the report itself leaves utility unresolved. No change without demonstrated benefit. |
| [#61 PMV/PMU/PMX](https://github.com/inkstitch/pystitch/issues/61) | Partially historical: PMV reader/writer exist, and a commenter reports PMV working on a Brother F560. This does not establish PMU/PMX support or SE700 compatibility for custom stitches. No speculative format additions. |
| [#56 U01 sequins](https://github.com/inkstitch/pystitch/issues/56) | Extended hardware-specific format investigation. Requires a compatible sequin attachment and machine-verified files, outside SE700 scope. |
| [#54 SHV colors](https://github.com/inkstitch/pystitch/issues/54) | Empty report without a reproduction file. Cannot establish current behavior from the issue alone. |
| [#51 MIT trim/color changes](https://github.com/inkstitch/pystitch/issues/51) | Sparse report without a reference file. Need format fixtures before changing command interpretation. |
| [#46 JEF hoop limits](https://github.com/inkstitch/pystitch/issues/46) | Machine-specific export validation is useful, but JEF needs separate hoop rules and fixtures. Does not resolve our separate need for SE700/PES size checks. |
| [#45 needle metadata on color changes](https://github.com/inkstitch/pystitch/issues/45) | API/command-semantics change that can break consumers comparing raw commands. Defer until a concrete multi-needle use case and compatibility tests exist. |
| [#38 stabilizer behavior](https://github.com/inkstitch/pystitch/issues/38) | Design discussion about interpreting raw commands. Broad normalization could lose stops or sequins; preserve existing behavior for now. |
| [#22 contextual stops](https://github.com/inkstitch/pystitch/issues/22) | Heuristic enhancement, not a demonstrated decoder bug. Explicit stops should not be inferred or removed without a defined policy. |

## Both open pull requests

| Pull request | Decision |
|---|---|
| [#139 minimum-cost palette assignment](https://github.com/inkstitch/pystitch/pull/139) | Adopted the strategy and helper with attribution, reserved-color exclusion, brute-force optimum checks and PEC export regression coverage. |
| [#144 ZHS delta correction](https://github.com/inkstitch/pystitch/pull/144) | Promising, includes a source DST and EZDesign-generated ZHS comparison. Defer to a separate change; not relevant to current PES use. It has not been independently reproduced in this review. |

## Validation and limits

New regression tests cover palette optimality against exhaustive small assignments, thread order, duplicate/overflow palettes, reserved entries, PEC export, DAT needle commands, non-UTF-8 DST metadata, trim decoding and intermediate trim movements at edges, corners and degenerate bounds.

The tests were run against the original implementations to confirm the three repaired bugs, then against the fixes. The full suite is required before push, followed by the hosted OS/Python matrix. A green software suite does not replace physical sew-outs or guarantee every supported format.
