#!/usr/bin/env python3
#   make_test_packs.py - Shimeji-ee packs in odd shapes, to test mascot import
#
#   Copyright (C) 2026  Xedoc91
#
#   This program is free software; you can redistribute it and/or
#   modify it under the terms of the GNU General Public License
#   as published by the Free Software Foundation; either version 2
#   of the License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, see <https://www.gnu.org/licenses/>.
"""Builds zip files from the bundled Shimeji's images, each the way some packs
on the internet come:

  Testy Shimeji v1.2.zip  images alone (shime1.png ...) at the top: a mascot
                          named "Testy", with the bundled Shimeji's actions
  Twins.zip               Twins/Alpha/ and Twins/Beta/, images alone: two mascots
  Nested Pack.zip         Nested Pack/Shimeji-ee/img/Blue/ with its conf/ inside
                          it, images in another letter case than the actions
                          name them (Shime3.PNG) and two missing (shime40/41)
  Shimeji.zip             a mascot called Shimeji, like the bundled one

Usage: scripts/make_test_packs.py <output directory>
"""

import io
import json
import os
import sys
import zipfile

from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SHIMEJI = os.path.join(ROOT, "prototypes", "Shimeji.Shimeji")


def images():
    """{"shime1": png bytes, ...} from the bundled Shimeji's QOI assets"""
    out = {}
    assets = os.path.join(SHIMEJI, "assets")
    for name in sorted(os.listdir(assets)):
        if name.endswith(".qoi"):
            png = io.BytesIO()
            Image.open(os.path.join(assets, name)).save(png, "PNG")
            out[name.removesuffix(".qoi")] = png.getvalue()
    return out


def actions_xml(pngs):
    """A small Shimeji-ee actions.xml/behaviors.xml pair over these images"""
    ns = 'xmlns="http://www.group-finity.com/Mascot"'

    def pose(n):
        return f'<Pose Image="/shime{n}.png" ImageAnchor="64,128" Velocity="0,0" Duration="250" />'

    actions = f"""<?xml version="1.0" encoding="UTF-8"?>
<Mascot {ns}><ActionList>
  <Action Name="Stand" Type="Stay" BorderType="Floor"><Animation>{pose(1)}</Animation></Action>
  <Action Name="Walk" Type="Move" BorderType="Floor"><Animation>
    <Pose Image="/shime1.png" ImageAnchor="64,128" Velocity="-2,0" Duration="6" />
    <Pose Image="/shime2.png" ImageAnchor="64,128" Velocity="-2,0" Duration="6" />
  </Animation></Action>
  <Action Name="Sit" Type="Stay" BorderType="Floor"><Animation>{pose(11)}</Animation></Action>
  <Action Name="Sprawl" Type="Stay" BorderType="Floor"><Animation>{pose(21)}</Animation></Action>
  <Action Name="Wave" Type="Animate" BorderType="Floor"><Animation>{pose(40)}{pose(41)}</Animation></Action>
  <Action Name="Falling" Type="Embedded" Class="com.group_finity.mascot.action.Fall"><Animation>{pose(4)}</Animation></Action>
  <Action Name="Bouncing" Type="Animate" BorderType="Floor"><Animation>{pose(18)}{pose(19)}</Animation></Action>
  <Action Name="Pinched" Type="Embedded" Class="com.group_finity.mascot.action.Dragged"><Animation>{pose(1)}</Animation></Action>
  <Action Name="Thrown" Type="Embedded" Class="com.group_finity.mascot.action.Fall"><Animation>{pose(4)}</Animation></Action>
  <Action Name="Fall" Type="Sequence"><ActionReference Name="Falling" /><ActionReference Name="Bouncing" /></Action>
  <Action Name="Dragged" Type="Sequence"><ActionReference Name="Pinched" /></Action>
  <Action Name="ThrownSequence" Type="Sequence"><ActionReference Name="Thrown" /><ActionReference Name="Bouncing" /></Action>
  <Action Name="SitDown" Type="Sequence"><ActionReference Name="Sit" Duration="200" /></Action>
  <Action Name="Sleep" Type="Sequence"><ActionReference Name="Sprawl" Duration="300" /></Action>
  <Action Name="WaveHello" Type="Sequence"><ActionReference Name="Wave" Duration="50" /></Action>
</ActionList></Mascot>
"""
    behaviors = f"""<?xml version="1.0" encoding="UTF-8"?>
<Mascot {ns}><BehaviorList>
  <Behavior Name="Fall" Frequency="0" Hidden="true" />
  <Behavior Name="Dragged" Frequency="0" Hidden="true" />
  <Behavior Name="Thrown" Action="ThrownSequence" Frequency="0" Hidden="true" />
  <Behavior Name="StandUp" Action="Stand" Frequency="100" />
  <Behavior Name="WalkAlong" Action="Walk" Frequency="100" />
  <Behavior Name="SitDown" Frequency="100" />
  <Behavior Name="Sleep" Frequency="20" />
  <Behavior Name="WaveHello" Frequency="20" />
</BehaviorList></Mascot>
"""
    return actions, behaviors


def main():
    if len(sys.argv) != 2:
        print(__doc__.split("Usage: ")[1].strip())
        sys.exit(1)
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    pngs = images()

    with zipfile.ZipFile(os.path.join(out, "Testy Shimeji v1.2.zip"), "w") as z:
        for name, data in pngs.items():
            z.writestr(f"{name}.png", data)
        z.writestr("readme.txt", "Test pack: images alone.\n")

    with zipfile.ZipFile(os.path.join(out, "Twins.zip"), "w") as z:
        for twin in ("Alpha", "Beta"):
            for name, data in pngs.items():
                z.writestr(f"Twins/{twin}/{name}.png", data)

    actions, behaviors = actions_xml(pngs)
    with zipfile.ZipFile(os.path.join(out, "Nested Pack.zip"), "w") as z:
        base = "Nested Pack/Shimeji-ee/img/Blue"
        for name, data in pngs.items():
            if name in ("shime40", "shime41"):
                continue  # missing: Wave, WaveHello and its behavior go
            # Another letter case than actions.xml says, as on Windows
            z.writestr(f"{base}/{name.capitalize()}.PNG" if name == "shime3" else f"{base}/{name}.png", data)
        z.writestr(f"{base}/conf/actions.xml", actions)
        z.writestr(f"{base}/conf/behaviors.xml", behaviors)
        z.writestr(f"{base}/conf/info.xml", """<?xml version="1.0" encoding="UTF-8"?>
<Mascot xmlns="http://www.group-finity.com/Mascot"><Information>
<Artist Name="Test Artist" /></Information></Mascot>
""")

    with zipfile.ZipFile(os.path.join(out, "Shimeji.zip"), "w") as z:
        for name, data in pngs.items():
            z.writestr(f"Shimeji/{name}.png", data)

    print(f"Wrote {', '.join(sorted(f for f in os.listdir(out) if f.endswith('.zip')))} to {out}")


if __name__ == "__main__":
    main()
