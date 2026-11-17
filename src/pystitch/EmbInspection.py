"""Non-mutating observations of stored commands, in millimeters.

This is not an encoder or machine simulation. See docs/inspection.md for the
versioned report schema, completeness flags and measurement conventions.
"""

import math
from numbers import Integral, Real

from . import EmbConstant as C
from .EmbFunctions import get_common_name_dictionary


_NAMES = get_common_name_dictionary()
_NAMES.update({
    C.CONTINGENCY_SEQUIN_UTILIZE: "CONTINGENCY_SEQUIN_UTILIZE",
    C.CONTINGENCY_SEQUIN_JUMP: "CONTINGENCY_SEQUIN_JUMP",
    C.CONTINGENCY_SEQUIN_STITCH: "CONTINGENCY_SEQUIN_STITCH",
    C.CONTINGENCY_SEQUIN_REMOVE: "CONTINGENCY_SEQUIN_REMOVE",
})
_ORDINARY = {
    C.STITCH, C.JUMP, C.TRIM, C.STOP, C.END, C.COLOR_CHANGE,
    C.NEEDLE_SET, C.SEQUIN_MODE, C.SEQUIN_EJECT, C.SLOW, C.FAST,
}
_NEEDLE_DOWN = {C.STITCH, C.SEQUIN_EJECT}


def _finite_real(value):
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    try:
        converted = float(value)
    except (OverflowError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def _threshold(name, value):
    if value is None:
        return None
    result = _finite_real(value)
    if result is None or result < 0:
        raise ValueError("%s must be a finite nonnegative number or None" % name)
    return result


class _Bounds:
    def __init__(self):
        self.min_x = self.min_y = self.max_x = self.max_y = None

    def add(self, x, y):
        if self.min_x is None:
            self.min_x = self.max_x = x
            self.min_y = self.max_y = y
        else:
            self.min_x = min(self.min_x, x)
            self.min_y = min(self.min_y, y)
            self.max_x = max(self.max_x, x)
            self.max_y = max(self.max_y, y)

    def report(self, complete):
        return {
            "min_x": self.min_x, "min_y": self.min_y,
            "max_x": self.max_x, "max_y": self.max_y,
            "width": None if self.min_x is None else self.max_x - self.min_x,
            "height": None if self.min_y is None else self.max_y - self.min_y,
            "complete": complete,
        }


def _length_report(values, excluded, complete):
    try:
        total = math.fsum(values)
    except OverflowError:
        total = None
    count = len(values)
    return {
        "count": count, "excluded": excluded, "total": total,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
        # Summing divided terms avoids overflow in an otherwise finite mean.
        "mean": math.fsum(v / count for v in values) if values else None,
        "complete": complete and excluded == 0 and total is not None,
    }


def inspect_pattern(pattern, *, short_stitch_mm=0.3, long_stitch_mm=4.0,
                    long_jump_mm=12.0):
    """Return a schema-version-1 JSON-serializable report without editing pattern.

    Thresholds are advisory, strict inequalities, and disabled with None.
    Measurements describe stored ordinary endpoints, with an assumed origin of
    (0, 0). A false completeness flag means partial observed measurements must
    not be used as a complete movement envelope or a machine-fit decision.
    """
    thresholds = {
        "short_stitch": _threshold("short_stitch_mm", short_stitch_mm),
        "long_stitch": _threshold("long_stitch_mm", long_stitch_mm),
        "long_jump": _threshold("long_jump_mm", long_jump_mm),
    }
    short, long = thresholds["short_stitch"], thresholds["long_stitch"]
    if short is not None and long is not None and short > long:
        raise ValueError("short_stitch_mm must not exceed long_stitch_mm")

    counts = dict.fromkeys(("records", "needle_down", "movements", "threads",
                           "color_blocks", "color_changes", "needle_sets",
                           "jumps", "trims", "stops"), 0)
    counts["records"] = len(pattern.stitches)
    counts["threads"] = len(pattern.threadlist)
    commands = {}
    diagnostics = []
    needle_bounds, movement_bounds = _Bounds(), _Bounds()
    lengths = {"stitch": [], "jump": []}
    excluded = {"stitch": 0, "jump": 0}
    complete = True
    previous = (0.0, 0.0)
    colorblock_start = 0
    ended = False
    count_fields = {C.COLOR_CHANGE: "color_changes", C.NEEDLE_SET: "needle_sets",
                    C.JUMP: "jumps", C.TRIM: "trims", C.STOP: "stops"}

    def diagnose(code, severity, message, index=None):
        diagnostics.append({"code": code, "severity": severity,
                            "index": index, "message": message})

    for index, record in enumerate(pattern.stitches):
        if ended:
            diagnose("records_after_end", "warning",
                     "Stored record follows END; counts include it, execution may not.", index)
            complete = False
        if not isinstance(record, (list, tuple)) or len(record) != 3:
            diagnose("invalid_record", "error", "Expected an (x, y, command) record.", index)
            complete, previous = False, None
            continue
        x, y, encoded = record
        if (isinstance(encoded, bool) or not isinstance(encoded, Integral)
                or encoded < -1 or encoded > 0xFFFFFFFF):
            diagnose("invalid_command", "error", "Expected a 32-bit command integer or NO_COMMAND.", index)
            complete, previous = False, None
            continue
        command = C.NO_COMMAND if encoded == C.NO_COMMAND else int(encoded) & C.COMMAND_MASK
        name = _NAMES.get(command, "UNKNOWN_%d" % command)
        commands[name] = commands.get(name, 0) + 1
        if command in _NEEDLE_DOWN:
            counts["needle_down"] += 1
        if command in count_fields:
            counts[count_fields[command]] += 1
        # Same boundaries as EmbPattern.get_as_colorblocks, without threads or fillers.
        if command == C.COLOR_BREAK:
            counts["color_blocks"] += colorblock_start != index
            colorblock_start = index + 1
        elif command == C.COLOR_CHANGE:
            counts["color_blocks"] += 1
            colorblock_start = index + 1
        elif command == C.NEEDLE_SET and colorblock_start != index:
            counts["color_blocks"] += 1
            colorblock_start = index

        if command == C.NO_COMMAND:
            continue
        if command not in _ORDINARY:
            if command not in _NAMES:
                diagnose("unknown_command", "error", "Unknown command ID %d." % command, index)
            else:
                diagnose("unresolved_command", "warning",
                         name + " requires encoding; its payload is not measured as a position.", index)
            complete, previous = False, None
            continue
        ended = ended or command == C.END
        kind = "stitch" if command in _NEEDLE_DOWN else "jump" if command == C.JUMP else None
        x, y = _finite_real(x), _finite_real(y)
        if x is None or y is None:
            diagnose("invalid_coordinates", "error", "Coordinates must be finite real numbers.", index)
            if kind:
                excluded[kind] += 1
            complete, previous = False, None
            continue
        # Divide before subtraction: native input is in tenths of millimeters.
        point = (x / 10.0, y / 10.0)
        movement_bounds.add(0.0, 0.0)
        movement_bounds.add(*point)
        if command in _NEEDLE_DOWN:
            needle_bounds.add(*point)
        if previous is not None:
            distance = math.hypot(point[0] - previous[0], point[1] - previous[1])
            counts["movements"] += point != previous
            if kind:
                lengths[kind].append(distance)
                checks = (("short_stitch", short, distance < short if short is not None else False),
                          ("long_stitch", long, distance > long if long is not None else False)) if kind == "stitch" else (
                              ("long_jump", thresholds["long_jump"],
                               distance > thresholds["long_jump"] if thresholds["long_jump"] is not None else False),)
                for code, threshold, triggered in checks:
                    if triggered:
                        diagnose(code, "warning", "Observed %s length %.6g mm crosses the %.6g mm heuristic."
                                 % (kind, distance, threshold), index)
        elif kind:
            excluded[kind] += 1
        previous = point

    if colorblock_start != len(pattern.stitches):
        counts["color_blocks"] += 1
    if counts["needle_down"] == 0:
        diagnose("empty_design", "warning", "No stored needle-down records.")
    summaries = {kind: _length_report(values, excluded[kind], complete)
                 for kind, values in lengths.items()}
    if any(summary["total"] is None for summary in summaries.values()):
        diagnose("measurement_overflow", "error", "A length total exceeds finite floating-point range.")
        complete = False
        for summary in summaries.values():
            summary["complete"] = False
    return {
        "schema_version": 1, "units": "mm", "counts": counts,
        "commands": commands,
        "bounds_mm": {"needle_down": needle_bounds.report(complete),
                      "movement": movement_bounds.report(complete)},
        "lengths_mm": summaries, "thresholds_mm": thresholds,
        "diagnostics": diagnostics, "geometry_complete": complete,
    }
