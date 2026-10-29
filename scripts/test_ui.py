#!/usr/bin/env python3
"""Checks on the bubble's QML (ui/) that need no running Quickshell.

Run: python3 -I scripts/test_ui.py
"""

import glob
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def blocks(source: str, element: str):
    """(line number, body) of each `element {` block, the body without its nested blocks"""
    for m in re.finditer(rf"^\s*{element}\s*{{", source, re.M):
        depth, i, own = 1, m.end(), []
        while depth:
            c = source[i]
            depth += {"{": 1, "}": -1}.get(c, 0)
            if depth == 1 and c not in "{}":
                own.append(c)
            i += 1
        yield source.count("\n", 0, m.end()) + 1, "".join(own)


class Text(unittest.TestCase):
    def test_every_text_says_its_format(self):
        # Qt's default (AutoText) shows text that looks like HTML as markup, and StyledText fetches <img src>
        # from the net: names from mascot packs, tool arguments and errors must never be read that way
        missing = []
        for path in sorted(glob.glob(os.path.join(ROOT, "ui", "*.qml"))):
            with open(path) as f:
                source = f.read()
            for line, body in blocks(source, "Text"):
                if not re.search(r"^\s*textFormat:", body, re.M):
                    missing.append(f"{os.path.relpath(path, ROOT)}:{line}")
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
