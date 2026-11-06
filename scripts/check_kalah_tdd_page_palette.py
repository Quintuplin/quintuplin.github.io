#!/usr/bin/env python3
"""Check the Kalah TDD series palette (#113): --s1 and --s2 sit in the OKLCH lightness band of each mode and above
the chroma floor, so each series reads as a distinct hue in both modes. check_contrast.py checks contrast.

Usage: check_kalah_tdd_page_palette.py
"""
import importlib.util
import math
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
CSS = SCRIPTS.parent / "studies/kalah-tdd-study/study.css"
SERIES = ("s1", "s2")
LIGHT_BAND, DARK_BAND, CHROMA_FLOOR = (0.43, 0.77), (0.48, 0.67), 0.10


def contrast():
    spec = importlib.util.spec_from_file_location("check_contrast", SCRIPTS / "check_contrast.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def modes():
    """{mode: tokens} for light, the dark media block and the forced dark theme."""
    c, text = contrast(), CSS.read_text(encoding="utf-8")
    return {"light": c.block(text, c.LIGHT), "dark": c.block(text, c.DARK), "forced dark": c.block(text, c.FORCED_DARK)}


def oklch(hex):
    """(L, C) of a #rrggbb colour in OKLCH."""
    lin = [(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
           for c in (int(hex[i:i + 2], 16) / 255 for i in (1, 3, 5))]
    r, g, b = lin
    l, m, s = (x ** (1 / 3) for x in (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b,
                                      0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b,
                                      0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b))
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s, math.hypot(a, bb)


class Palette(unittest.TestCase):
    def test_oklch_known_colours(self):
        self.assertAlmostEqual(oklch("#ffffff")[0], 1, places=3)
        self.assertAlmostEqual(oklch("#808080")[1], 0, places=3)
        self.assertAlmostEqual(oklch("#ff0000")[1], 0.2577, places=3)

    def band(self, mode, low, high):
        for name in SERIES:
            with self.subTest(mode=mode, token=name):
                lightness = oklch(modes()[mode][name])[0]
                self.assertTrue(low <= lightness <= high, f"--{name} L {lightness:.3f} outside {low} to {high}")

    def test_seriesInDarkBand(self):
        self.band("dark", *DARK_BAND)
        self.band("forced dark", *DARK_BAND)

    def test_seriesInLightBand(self):
        self.band("light", *LIGHT_BAND)

    def test_seriesAboveChromaFloor(self):
        for mode, tokens in modes().items():
            for name in SERIES:
                with self.subTest(mode=mode, token=name):
                    self.assertGreaterEqual(oklch(tokens[name])[1], CHROMA_FLOOR, tokens[name])


if __name__ == "__main__":
    unittest.main()
