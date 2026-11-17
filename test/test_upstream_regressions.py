"""Focused reproductions of upstream pystitch reports #98, #128 and PR #139."""
import io
import itertools
import random
import unittest

import pystitch as emb
from pystitch import DatReader, DstReader, DstWriter
from pystitch.EmbFunctions import decode_embroidery_command
from pystitch.EmbThread import build_unique_palette, color_distance_red_mean
from pystitch.EmbThreadPec import get_thread_set


def distance(a, b):
    return color_distance_red_mean(a.get_red(), a.get_green(), a.get_blue(),
                                   b.get_red(), b.get_green(), b.get_blue())


class TestPaletteRegressions(unittest.TestCase):
    def test_global_color_cost_matches_brute_force(self):
        rng = random.Random(139)
        for _ in range(20):
            palette = [emb.EmbThread(rng.randrange(0x1000000)) for _ in range(4)]
            threads = [emb.EmbThread(rng.randrange(0x1000000)) for _ in range(3)]
            expected = min(sum(distance(t, palette[i]) for t, i in zip(threads, indices))
                           for indices in itertools.permutations(range(4), 3))
            indices = build_unique_palette(palette[:], threads)
            self.assertEqual(len(set(indices)), 3)
            self.assertEqual(sum(distance(t, palette[i]) for t, i in zip(threads, indices)), expected)

    def test_white_remains_white_in_both_thread_orders(self):
        cream = emb.EmbThread('#fffff5')
        white = emb.EmbThread('#ffffff')
        for threads in ([cream, white], [white, cream]):
            palette = [emb.EmbThread('#000000'), emb.EmbThread('#ffffff')]
            indices = build_unique_palette(palette, threads)
            self.assertEqual(indices[threads.index(white)], 1)

    def test_reserved_entries_are_never_assigned(self):
        palette = get_thread_set()
        threads = [emb.EmbThread(t) for t in palette
                   if t is not None and not getattr(t, 'reserved', False)]
        indices = build_unique_palette(palette[:], threads)
        self.assertEqual(len(set(indices)), len(threads))
        self.assertTrue(all(not palette[i].reserved for i in indices))

    def test_duplicate_threads_share_slot_and_empty_palette_returns_none(self):
        red = emb.EmbThread('red')
        self.assertEqual(build_unique_palette([emb.EmbThread('red')], [red, emb.EmbThread(red)]), [0, 0])
        self.assertEqual(build_unique_palette([None], [red]), [None])
        self.assertEqual(build_unique_palette([], []), [])

    def test_overfull_palette_still_returns_valid_indices(self):
        palette = [emb.EmbThread('black'), emb.EmbThread('white')]
        indices = build_unique_palette(palette, [emb.EmbThread(c) for c in ('black', 'white', 'red')])
        self.assertEqual(len(indices), 3)
        self.assertTrue(all(i in (0, 1) for i in indices))

    def test_pec_export_preserves_white_block(self):
        pattern = emb.EmbPattern()
        for color in ('#fffff5', '#ffffff'):
            pattern.add_block([(0, 0), (0, 20), (20, 20)], color)
        stream = io.BytesIO()
        emb.write_pec(pattern, stream)
        stream.seek(0)
        result = emb.read_pec(stream)
        self.assertEqual(result.threadlist[1].description, 'White')
        self.assertNotEqual(result.threadlist[0].description, 'White')


class TestDatNeedleRegressions(unittest.TestCase):
    def test_barudan_needle_changes_preserve_numbers_and_movement(self):
        for needle in (1, 3, 15):
            with self.subTest(needle=needle):
                source = bytes((0x88 + needle, 6, 4, 0x80, 0, 2, 0x98, 0, 0))
                pattern = emb.EmbPattern()
                DatReader.read(io.BytesIO(source), pattern)
                needle_commands = [s for s in pattern.stitches if s[2] & emb.COMMAND_MASK == emb.NEEDLE_SET]
                self.assertEqual(len(needle_commands), 1)
                self.assertEqual(decode_embroidery_command(needle_commands[0][2])[2], needle)
                stitches = [s for s in pattern.stitches if s[2] & emb.COMMAND_MASK == emb.STITCH]
                self.assertEqual(stitches[0][:2], [6, -6])


class TestDstTrimBounds(unittest.TestCase):
    def test_non_utf8_header_does_not_prevent_reading_stitches(self):
        # Issue #92 is already handled: ignore undecodable metadata, not stitches.
        header = b'LA:Bad\xd0name\r'.ljust(512, b' ')
        records = DstWriter.encode_record(10, 20, emb.STITCH) + DstWriter.encode_record(0, 0, emb.END)
        pattern = emb.read_dst(io.BytesIO(header + records))
        self.assertEqual(pattern.count_stitch_commands(emb.STITCH), 1)
        self.assertEqual(pattern.stitches[0][:2], [10, 20])

    def test_raw_trim_jumps_stay_within_bounds(self):
        # Test raw records, before the reader hides trim-encoding movements.
        for width, height in ((100, 100), (1, 1), (0, 100), (100, 0), (0, 0)):
            for origin in ((0, 0), (-100, -100)):
                for corner in ((0, 0), (width, 0), (0, height), (width, height)):
                    for trim_at in (3, 4, 5):
                        with self.subTest(size=(width, height), origin=origin, corner=corner, trim_at=trim_at):
                            x0, y0 = origin
                            p = emb.EmbPattern()
                            p.stitch_abs(x0, y0)
                            p.stitch_abs(x0 + width, y0 + height)
                            p.stitch_abs(x0 + corner[0], y0 + corner[1])
                            p.trim()
                            p.end()
                            stream = io.BytesIO()
                            DstWriter.write(p, stream, {'trim_at': trim_at})
                            records = stream.getvalue()[512:]
                            # Initial records are synthetic stitches. Check only trim records.
                            x, y = p.stitches[2][:2]
                            for offset in range(9, 9 + trim_at * 3, 3):
                                b0, b1, b2 = records[offset:offset + 3]
                                x += DstReader.decode_dx(b0, b1, b2)
                                y += DstReader.decode_dy(b0, b1, b2)
                                self.assertTrue(x0 <= x <= x0 + width, (x, y))
                                self.assertTrue(y0 <= y <= y0 + height, (x, y))
                            self.assertEqual((x, y), tuple(p.stitches[2][:2]))

    def test_trim_still_decodes_as_trim(self):
        p = emb.EmbPattern()
        p.stitch_abs(0, 0)
        p.stitch_abs(100, 100)
        p.trim()
        p.stitch_abs(90, 90)
        p.end()
        for count in (3, 4, 5):
            stream = io.BytesIO()
            DstWriter.write(p, stream, {'trim_at': count})
            stream.seek(0)
            result = emb.read_dst(stream, {'trim_at': count})
            self.assertEqual(result.count_stitch_commands(emb.TRIM), 1)


if __name__ == '__main__':
    unittest.main()
