import copy
import json
import unittest
from unittest.mock import patch

import pystitch as ps


class TestInspection(unittest.TestCase):
    def inspect(self, records=(), threads=(), **kwargs):
        pattern = ps.EmbPattern()
        pattern.stitches = list(records)
        pattern.threadlist = list(threads)
        return ps.inspect_pattern(pattern, **kwargs)

    def test_public_api_is_available(self):
        self.assertTrue(callable(getattr(ps, "inspect_pattern", None)))

    def test_known_mm_lengths_counts_and_distinct_envelopes(self):
        r = self.inspect([
            [-30, -40, ps.STITCH], [0, 0, ps.STITCH],
            [100, 0, ps.JUMP], [100, 0, ps.STITCH],
            [200, 0, ps.TRIM], [200, 0, ps.STOP],
            [200, 0, ps.COLOR_CHANGE], [200, 0, ps.END],
        ], [ps.EmbThread(), ps.EmbThread()])
        self.assertEqual(r["schema_version"], 1)
        self.assertEqual(r["units"], "mm")
        self.assertTrue(r["geometry_complete"])
        c = r["counts"]
        self.assertEqual(c["records"], 8)
        self.assertEqual(c["needle_down"], 3)
        self.assertEqual(c["movements"], 4)
        self.assertEqual(c["threads"], 2)
        self.assertEqual(c["color_blocks"], 2)
        self.assertEqual((c["jumps"], c["trims"], c["stops"], c["color_changes"]), (1, 1, 1, 1))
        self.assertEqual(r["commands"]["STITCH"], 3)
        needle = r["bounds_mm"]["needle_down"]
        envelope = r["bounds_mm"]["movement"]
        self.assertEqual((needle["min_x"], needle["min_y"], needle["max_x"], needle["max_y"]), (-3, -4, 10, 0))
        self.assertEqual((needle["width"], needle["height"]), (13, 4))
        self.assertEqual(envelope["max_x"], 20)  # trim movement matters
        self.assertEqual(r["lengths_mm"]["stitch"], {
            "count": 3, "excluded": 0, "total": 10.0, "min": 0.0,
            "max": 5.0, "mean": 10.0 / 3, "complete": True,
        })
        self.assertEqual(r["lengths_mm"]["jump"]["total"], 10)
        self.assertEqual(r["thresholds_mm"], {"short_stitch": 0.3, "long_stitch": 4.0, "long_jump": 12.0})

    def test_origin_in_envelope_but_not_needle_bounds(self):
        r = self.inspect([[100, 200, ps.STITCH]])
        self.assertEqual(r["bounds_mm"]["needle_down"]["width"], 0)
        self.assertEqual(r["bounds_mm"]["movement"]["width"], 10)
        self.assertEqual(r["bounds_mm"]["movement"]["height"], 20)
        self.assertAlmostEqual(r["lengths_mm"]["stitch"]["total"], 22.360679774997898)

    def test_thresholds_are_heuristics_and_can_be_disabled(self):
        records = [[0, 0, ps.STITCH], [10, 0, ps.STITCH], [510, 0, ps.JUMP]]
        r = self.inspect(records, short_stitch_mm=0.5, long_stitch_mm=0.8, long_jump_mm=20)
        warnings = [d for d in r["diagnostics"] if d["code"] in ("short_stitch", "long_stitch", "long_jump")]
        self.assertEqual([(d["code"], d["index"], d["severity"]) for d in warnings], [
            ("short_stitch", 0, "warning"), ("long_stitch", 1, "warning"), ("long_jump", 2, "warning")])
        self.assertTrue(r["geometry_complete"])
        disabled = self.inspect(records, short_stitch_mm=None, long_stitch_mm=None, long_jump_mm=None)
        self.assertFalse(disabled["diagnostics"])
        self.assertIsNone(disabled["thresholds_mm"]["long_jump"])
        equal = self.inspect([[10, 0, ps.STITCH]], short_stitch_mm=1, long_stitch_mm=1)
        self.assertFalse(equal["diagnostics"])

    def test_invalid_thresholds_fail_clearly(self):
        for value in (-1, float("nan"), float("inf"), "4", True, 10 ** 1000):
            with self.subTest(value=str(value)[:30]), self.assertRaises(ValueError):
                self.inspect(long_jump_mm=value)
        with self.assertRaises(ValueError):
            self.inspect(short_stitch_mm=5, long_stitch_mm=4)

    def test_empty_and_control_only_have_no_fake_needle_dimensions(self):
        for records in ([], [[0, 0, ps.END]], [[50, 0, ps.JUMP]]):
            r = self.inspect(records)
            self.assertIn("empty_design", [d["code"] for d in r["diagnostics"]])
            self.assertIsNone(r["bounds_mm"]["needle_down"]["width"])
            self.assertIsNone(r["lengths_mm"]["stitch"]["min"])
            json.dumps(r, allow_nan=False)
        self.assertIsNone(self.inspect()["bounds_mm"]["movement"]["width"])

    def test_invalid_coordinates_break_distance_continuity(self):
        for bad in (float("nan"), float("inf"), float("-inf"), None, "bad", True, 10 ** 1000):
            with self.subTest(value=str(bad)[:30]):
                r = self.inspect([[0, 0, ps.STITCH], [bad, 0, ps.STITCH],
                                  [30, 40, ps.STITCH], [60, 80, ps.STITCH]])
                self.assertEqual(r["counts"]["needle_down"], 4)
                self.assertFalse(r["geometry_complete"])
                self.assertFalse(r["bounds_mm"]["needle_down"]["complete"])
                self.assertFalse(r["bounds_mm"]["movement"]["complete"])
                self.assertEqual(r["lengths_mm"]["stitch"]["count"], 2)
                self.assertEqual(r["lengths_mm"]["stitch"]["excluded"], 2)
                self.assertEqual(r["lengths_mm"]["stitch"]["total"], 5)
                self.assertIn("invalid_coordinates", [d["code"] for d in r["diagnostics"]])
                json.dumps(r, allow_nan=False)

    def test_malformed_records_and_unknown_commands_are_reported(self):
        r = self.inspect([None, [], [1, 2], [0, 0, "STITCH"], [0, 0, True],
                          [1000, 1000, 0xAB], [30, 40, ps.STITCH]])
        codes = [d["code"] for d in r["diagnostics"]]
        self.assertEqual(codes.count("invalid_record"), 3)
        self.assertEqual(codes.count("invalid_command"), 2)
        self.assertIn("unknown_command", codes)
        self.assertFalse(r["geometry_complete"])
        self.assertEqual(r["commands"]["UNKNOWN_171"], 1)
        self.assertEqual(r["lengths_mm"]["stitch"]["excluded"], 1)
        self.assertEqual(r["bounds_mm"]["movement"]["max_x"], 3)
        json.dumps(r, allow_nan=False)

    def test_encoder_payloads_are_not_positions(self):
        r = self.inspect([[10, 20, ps.STITCH], [100000, 100000, ps.MATRIX_SCALE],
                          [100000, 0, ps.OPTION_MAX_STITCH_LENGTH],
                          [100000, 0, ps.SEW_TO], [20, 30, ps.STITCH]])
        self.assertFalse(r["geometry_complete"])
        self.assertEqual(r["bounds_mm"]["movement"]["max_x"], 2)
        self.assertEqual(r["counts"]["needle_down"], 2)
        self.assertEqual(r["commands"]["SEW_TO"], 1)
        self.assertEqual(r["lengths_mm"]["stitch"]["excluded"], 1)
        self.assertEqual(sum(d["code"] == "unresolved_command" for d in r["diagnostics"]), 3)

    def test_flags_sequins_and_color_blocks_without_filler(self):
        p = ps.EmbPattern()
        p.stitches = [[0, 0, ps.COLOR_BREAK], [0, 0, ps.NEEDLE_SET],
                      [0, 0, ps.SEQUIN_EJECT], [0, 0, ps.COLOR_BREAK],
                      [0, 0, ps.encode_thread_change(ps.COLOR_CHANGE, thread=7)],
                      [0, 0, ps.NEEDLE_SET], [0, 0, ps.END]]
        expected_blocks = len(list(p.get_as_colorblocks()))
        with patch.object(p, "get_thread_or_filler", side_effect=AssertionError("no filler")):
            r = ps.inspect_pattern(p)
        self.assertEqual(r["counts"]["color_blocks"], expected_blocks)
        self.assertEqual(r["counts"]["threads"], 0)
        self.assertEqual(r["counts"]["needle_down"], 1)
        self.assertEqual(r["counts"]["color_changes"], 1)
        self.assertEqual(r["counts"]["needle_sets"], 2)

    def test_after_end_is_counted_but_marked_incomplete(self):
        r = self.inspect([[0, 0, ps.END], [100, 100, ps.STITCH]])
        self.assertEqual(r["counts"]["needle_down"], 1)
        self.assertIn("records_after_end", [d["code"] for d in r["diagnostics"]])
        self.assertFalse(r["geometry_complete"])
        self.assertFalse(r["bounds_mm"]["movement"]["complete"])

    def test_overflow_never_leaks_nonfinite_json_or_complete_claims(self):
        r = self.inspect([[(-1 if i % 2 else 1) * 1e308, 0, ps.STITCH] for i in range(20)])
        self.assertFalse(r["geometry_complete"])
        self.assertIsNone(r["lengths_mm"]["stitch"]["total"])
        self.assertFalse(r["lengths_mm"]["stitch"]["complete"])
        self.assertFalse(r["lengths_mm"]["jump"]["complete"])
        self.assertIn("measurement_overflow", [d["code"] for d in r["diagnostics"]])
        json.dumps(r, allow_nan=False)

    def test_invalid_command_range_and_no_command(self):
        r = self.inspect([[0, 0, -2], [0, 0, 1 << 32], [9999, 9999, ps.NO_COMMAND], [0, 0, ps.STITCH]])
        self.assertEqual(sum(d["code"] == "invalid_command" for d in r["diagnostics"]), 2)
        self.assertEqual(r["commands"]["NO_COMMAND"], 1)
        self.assertEqual(r["bounds_mm"]["movement"]["max_x"], 0)

    def test_pattern_is_unchanged_and_report_is_detached(self):
        p = ps.EmbPattern()
        p.stitches = [[-30, -40, ps.STITCH], [0, 0, ps.END]]
        p.add_thread("red")
        p.extras["nested"] = {"key": [1, 2]}
        before = copy.deepcopy(p.__dict__)
        r = ps.inspect_pattern(p)
        self.assertEqual(p.__dict__, before)
        r["counts"]["threads"] = 100
        r["commands"]["STITCH"] = 100
        self.assertEqual(p.__dict__, before)


if __name__ == "__main__":
    unittest.main()
