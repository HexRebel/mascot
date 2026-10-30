#!/usr/bin/env python3
"""Writes src/display_name_tables.h: the Unicode ranges display_name_safe() (src/mascot_config_parser.c) checks a
pack's display name against, from Python's unicodedata. Run it again for a newer Unicode:

    python3 -I scripts/unicode_tables.py
"""
import os
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ranges(categories):
    found, start = [], None
    for point in range(0x110001):
        inside = point < 0x110000 and unicodedata.category(chr(point)) in categories
        if inside and start is None:
            start = point
        elif not inside and start is not None:
            found.append((start, point - 1))
            start = None
    return found


def table(name, found):
    lines, line = [], "   "
    for a, b in found:
        item = f" {{0x{a:X}, 0x{b:X}}},"
        if len(line) + len(item) > 118:
            lines.append(line)
            line = "   "
        line += item
    lines.append(line)
    return f"static const uint32_t {name}[][2] = {{\n" + "\n".join(lines) + "\n};\n"


def main():
    text = (f"// Made by scripts/unicode_tables.py from Python's unicodedata (Unicode {unicodedata.unidata_version}), for\n"
            "// display_name_safe() in mascot_config_parser.c. Do not edit; run the script again\n"
            "#ifndef DISPLAY_NAME_TABLES_H\n#define DISPLAY_NAME_TABLES_H\n\n#include <stdint.h>\n\n"
            "// Format characters (Cf): they do not show, and some change how the text around them reads\n"
            + table("display_name_format", ranges({"Cf"}))
            + "\n// Combining marks (Mn, Me): drawn on the character before them\n"
            + table("display_name_marks", ranges({"Mn", "Me"}))
            + "\n#endif\n")
    with open(os.path.join(ROOT, "src", "display_name_tables.h"), "w") as f:
        f.write(text)


if __name__ == "__main__":
    main()
