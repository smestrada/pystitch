# Inspecting a design

`inspect_pattern` reports stored design data without editing it. It does not
normalize commands, generate filler threads, resize, center, repair, or predict
sew quality. This API is available in this fork; installing the upstream PyPI
package does not imply it includes these additions.

```python
import json
from pystitch import EmbPattern, STITCH, inspect_pattern

pattern = EmbPattern()
pattern.add_stitch_absolute(STITCH, 30, 40)  # native tenths of a millimeter
report = inspect_pattern(pattern, short_stitch_mm=None, long_stitch_mm=6.0)
print(json.dumps(report, indent=2, allow_nan=False))
assert report["lengths_mm"]["stitch"]["total"] == 5.0
assert report["bounds_mm"]["movement"]["width"] == 3.0
assert report["bounds_mm"]["movement"]["height"] == 4.0
```

For an existing design, load it with the existing `read` API and pass the
resulting `EmbPattern` to the same function. The original pattern, metadata,
commands and thread objects are unchanged. No filename or user metadata is
copied into the report.

## Interface and schema version 1

```python
inspect_pattern(pattern, *, short_stitch_mm=0.3,
                long_stitch_mm=4.0, long_jump_mm=12.0) -> dict
```

Each threshold must be a finite nonnegative real number or `None` to disable
it. If both stitch thresholds are enabled, short must not exceed long. Invalid
arguments raise `ValueError`. Values equal to a threshold do not warn.
These defaults are adjustable inspection heuristics, not machine limits or
reasons to reject an otherwise valid file. A long jump can be intentional.

The example above produces:

```json
{
  "schema_version": 1,
  "units": "mm",
  "counts": {
    "records": 1, "needle_down": 1, "movements": 1, "threads": 0,
    "color_blocks": 1, "color_changes": 0, "needle_sets": 0,
    "jumps": 0, "trims": 0, "stops": 0
  },
  "commands": {"STITCH": 1},
  "bounds_mm": {
    "needle_down": {
      "min_x": 3.0, "min_y": 4.0, "max_x": 3.0, "max_y": 4.0,
      "width": 0.0, "height": 0.0, "complete": true
    },
    "movement": {
      "min_x": 0.0, "min_y": 0.0, "max_x": 3.0, "max_y": 4.0,
      "width": 3.0, "height": 4.0, "complete": true
    }
  },
  "lengths_mm": {
    "stitch": {
      "count": 1, "excluded": 0, "total": 5.0, "min": 5.0,
      "max": 5.0, "mean": 5.0, "complete": true
    },
    "jump": {
      "count": 0, "excluded": 0, "total": 0.0, "min": null,
      "max": null, "mean": null, "complete": true
    }
  },
  "thresholds_mm": {"short_stitch": null, "long_stitch": 6.0, "long_jump": 12.0},
  "diagnostics": [],
  "geometry_complete": true
}
```

The report consists only of JSON objects, arrays, strings, finite numbers,
booleans and nulls. Consumers should check `schema_version` before interpreting
fields; future incompatible changes require a new schema version. Command
counts contain only IDs actually encountered. Thread/color encodings in higher
bits are masked; an unknown low-byte ID is named `UNKNOWN_<decimal ID>`.

| Field | Meaning |
|---|---|
| `counts.records` | All stored records, including controls and malformed records. This differs from needle punctures and from encoded stitch totals. |
| `counts.needle_down` | Stored STITCH and SEQUIN_EJECT records, even when coordinates are invalid. SEW_TO/NEEDLE_AT are encoder instructions, not final stitch counts. |
| `counts.movements` | Ordinary records with a finite endpoint different from a known previous endpoint. Incomplete geometry makes this an observed lower bound. Zero-length records are not movements. |
| `counts.threads` | Stored thread-list entries, including unused or duplicate entries; not inferred colors or unique thread colors. No missing thread is invented. |
| `counts.color_blocks` | Same boundaries as `get_as_colorblocks`: COLOR_BREAK is omitted, COLOR_CHANGE ends a block, NEEDLE_SET starts a new block. Nonsewing/END-only blocks count; an empty pattern has zero blocks. |
| Other `counts` | Literal masked COLOR_CHANGE, NEEDLE_SET, JUMP, TRIM and STOP counts, separately from block and movement counts. |
| `commands` | Named counts of all well-formed command integers, including unknown IDs and NO_COMMAND. |
| `bounds_mm` | Separate needle-down and movement rectangles; min/max/width/height are null when no applicable finite point exists. Single-point needle bounds have zero width and height. |
| `lengths_mm` | Incoming needle-down and jump segment summaries. `count` counts measured segments, `excluded` counts known relevant records lacking an incoming measurement. Empty summaries have total 0 and null min/max/mean. Overflowing totals are null with an error. |
| `thresholds_mm` | The actual enabled/disabled threshold values used in this report. |
| `diagnostics` | Objects with stable `code`, `severity`, zero-based record `index` (or null for whole-design diagnostics), and human-readable `message`. Match codes rather than message text. |
| `geometry_complete` | Whether all stored records can be measured by this raw-coordinate convention. Each bounds/length group also carries `complete`; false means the values are partial observations. True does not certify machine compatibility. |

## Measurement conventions and limits

Every reported coordinate or length is in millimeters (native input divided by
10). Bounds are axis-aligned; width/height do not encode position or rotation.
The assumed starting position is (0,0). The movement envelope includes that
origin whenever an ordinary finite endpoint exists. Needle bounds include only
actual stored needle-down endpoints, so an off-origin first stitch can have
zero-sized needle bounds but a large incoming movement.

Ordinary coordinates on STITCH, JUMP, TRIM, STOP, END, COLOR_CHANGE, NEEDLE_SET,
SEQUIN_MODE, SEQUIN_EJECT, SLOW and FAST all contribute to the stored movement
envelope. Thus outlying jump and trim coordinates cannot disappear behind
needle-only bounds. This is deliberately conservative: a particular writer or
machine may encode a control differently or ignore its stored coordinates.
`complete` means complete **under this convention**, not simulated execution.

Stitch lengths include STITCH and SEQUIN_EJECT incoming Euclidean segments;
jump lengths include JUMP incoming segments. Both start at the last ordinary
endpoint, initially origin. Controls update the previous endpoint but their
distances are not classified as stitch or jump lengths. Zero-length needle
records remain in length statistics and may trigger the short-stitch heuristic.

Unknown IDs, malformed records/commands and invalid coordinates produce errors,
mark geometry incomplete and break position continuity. The next valid
ordinary endpoint restores a known raw position; its incoming length is
excluded. Its endpoint still contributes to observed bounds. Any observed
rectangle is only a subset when incomplete, not a proven overall size.

Matrix, option, sequence, tie and other encoder instructions produce
`unresolved_command` warnings and incomplete geometry. Their payloads are not
treated as positions, and final stitch counts/transformations are not inferred.
For machine checking, first obtain a deliberate encoded/normalized design with
known settings, then inspect that separately; this function never does so
silently. NO_COMMAND is ignored for geometry and does not change position.

All stored records are counted, including records following END. Such trailing
records produce `records_after_end` warnings and incomplete geometry because
execution may stop before them. An empty/control-only design receives
`empty_design` when there are no needle-down records. Nonfinite/nonnumeric
coordinates receive `invalid_coordinates`, not apparently successful dimensions.

Diagnostics also include `invalid_record`, `invalid_command`, `unknown_command`,
`measurement_overflow`, `short_stitch`, `long_stitch`, and `long_jump`.
Heuristic warnings leave otherwise complete geometry complete. This report
does not establish fabric/thread suitability, density, tension, hoop placement,
machine support, or successful physical sewing.
