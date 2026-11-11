"""Adds the owl's own actions and behaviours to a converted Owl .wlshm (built like Robo's, art/robo/scripts/patch.py
in Mascot's repo):

- it never moves on the floor without flying: walking, creeping, running, dashing, carrying a window and
  stumbling all beat the wings (61-68, 94)
- Chatter (talk: head tilted, a wing on its chin, a light bulb), Snooze (asleep), NewMessage (holding up a scroll)
- seven things it does now and then on the floor (Whistle, Wave, Gem, Stones, Read, Graduate, Happy)
- what it does while a tool runs and for events (see mascot_chat_doing() in src/mascot.c); the ones it has no
  image for (FullPower, Appear) are left out, and mascotd falls back to Talk or SitDown
- dangles whenever it is held up, never pulls itself up
- on its branch in the screen's side it chats, sleeps and shows the tools there (the *OnWall behaviors)

    patch.py <converted .wlshm> <out .wlshm>
"""
import io
import json
import sys
import tarfile

src, dst = sys.argv[1], sys.argv[2]


def frame(n, duration, readable=False, right=None):
    right = right or (n if readable else None)
    return {"type": "Frame", "image": f"shime{n}.qoi", "image_right": f"shime{right}.qoi" if right else None,
            "image_anchor_x": 64, "image_anchor_y": 128, "velocity_x": 0, "velocity_y": 0, "duration": duration}


def action(name, kind, frames, border="Floor"):
    return {"type": kind, "name": name,
            "content": [{"type": "Animation", "condition": None, "frames": frames, "hotspots": [],
                         "frame_count": len(frames), "hotspots_count": 0}],
            "content_count": 1, "local_variables": {}, "local_variables_count": 0, "embedded_type": None,
            "loop": False, "condition": None, "border_type": border}


with open(src, "rb") as f:
    header = f.read(512)
    source = tarfile.open(fileobj=io.BytesIO(f.read()), mode="r:*")

actions = json.load(source.extractfile("actions.json"))
actions += [
    # While it answers: head tilted, a wing on its chin, now and then a light bulb
    action("Chatter", "Animate", [frame(70, 40), frame(71, 40), frame(70, 40), frame(72, 40)]),
    action("Snooze", "Stay", [frame(47, 80, True)]),  # the zzz: not mirrored facing right
    action("NewMessage", "Animate", [frame(48, 10), frame(57, 10)]),
    action("Alarm", "Animate", [frame(89, 100)]),
    action("SwitchedOff", "Stay", [frame(47, 250, True)]),
]
# It never moves on the floor without flying (the user's choice, 6 Nov): walking, creeping, running, dashing and
# carrying a window all beat the wings, each at its own speed; stumbling after a dash too
moves = {}
FLYING = ("Walk", "Creep", "Run", "Dash", "WalkWithIe", "RunWithIe")
# The wing beat (ticks; about 25 a second)
BEAT = [(61, 2), (62, 2), (63, 2), (64, 2), (65, 2), (66, 3), (67, 3), (68, 3), (94, 3)]  # down quickly, up slower, a loop
for a in actions:
    if a["name"] in ("Pinched", "Resisting"):  # held up: always dangling, never standing
        for part in a["content"] or []:
            for f in part.get("frames", []):
                if f["image"] in ("shime1.qoi", "shime60.qoi"):
                    f["image"] = "shime90.qoi"
    for part in a["content"] or []:
        if not part.get("frames"):
            continue
        if a["name"] in FLYING:
            # its speed: the first frame that moves (Creep's first stands still)
            first = next((f for f in part["frames"] if f["velocity_x"] or f["velocity_y"]), part["frames"][0])
            part["frames"] = [dict(first, image=f"shime{n}.qoi", duration=d) for n, d in BEAT]
            part["frame_count"] = len(BEAT)
        elif a["name"] == "Tripping":  # its own speeds and lengths, the wing beat's images
            for i, f in enumerate(part["frames"]):
                f["image"] = f"shime{BEAT[i % len(BEAT)][0]}.qoi"
    if a["name"] in moves and a["content"] and "frames" in a["content"][0]:
        for i, f in enumerate(a["content"][0]["frames"]):
            f["image"] = f"shime{moves[a['name']][i % 4]}.qoi"
    # Landed: wings out as its feet touch down, then standing (about 0.3 s and 0.5 s)
    if a["name"] == "Bouncing" and a["content"] and "frames" in a["content"][0]:
        for f in a["content"][0]["frames"]:
            f["duration"] = {"shime18.qoi": 8, "shime19.qoi": 12}.get(f["image"], f["duration"])
# All images are on one canvas wider than 128 (the flying owl's wings, see compose.py): each frame's anchor is the
# canvas's bottom middle, as 64, 128 is for a 128x128 one
size = {}
for member in source.getmembers():
    if member.name.startswith("assets/") and member.name.endswith(".qoi"):
        head = source.extractfile(member).read(12)  # "qoif", width, height (big-endian)
        size[member.name[len("assets/"):]] = (int.from_bytes(head[4:8], "big"), int.from_bytes(head[8:12], "big"))


def anchored(node):
    if isinstance(node, dict):
        if node.get("type") == "Frame" and size.get(node.get("image")) not in (None, (128, 128)):
            w, h = size[node["image"]]
            # 13 and 101-120, on its branch in the screen's side: the branch's cut end, at the canvas's left edge
            on_branch = node["image"] == "shime13.qoi" or 101 <= int(node["image"][5:-4]) <= 131
            node["image_anchor_x"], node["image_anchor_y"] = (0 if on_branch else w // 2), h
        for v in node.values():
            anchored(v)
    elif isinstance(node, list):
        for v in node:
            anchored(v)


FUN = {"Whistle": 73, "Wave": 74, "Gem": 75, "Stones": 76, "Read": 77, "Graduate": 79, "Happy": 80, "Dizzy": 100}
POSES = {"Laurel": 78, "Glasses": 81, "Scroll": 82, "Watch": 83, "Magnify": 84, "Hearts": 85, "Cheer": 86,
         "Knocked": 87, "Puzzled": 88, "Wand": 91, "Drowsy": 92,
         "Umbrella": 96, "Globe": 133, "Thermometer": 134, "Snowcap": 135, "Shiver": 97, "Shy": 98,  # owl6.png (the user's "sidste.png", 6 Nov)
         "Startled": 99,  # owl2.png row 2 column 1: the answer failed
         "Pilot": 132}  # owl2.png row 2 column 5: a pilot's cap and goggles, the CPU on full power
LONGER = {"Stones": 200, "Read": 200}  # ticks (a pose is 100, about 4 s)
actions += [action(name, "Animate", [frame(n, LONGER.get(name, 100))]) for name, n in {**FUN, **POSES}.items()]
# On its branch in the screen's (or a window's) side, 101-120 (owl-branch*.png): mascotd plays "<behavior>OnWall"
# there instead of waiting until it lands (mascot_behavior_here() in src/mascot.c), so it chats, sleeps and shows
# the tools sitting on its branch (the user's idea, 6 Nov)
ON_WALL = {
    "SitDownOnWall": [(101, 250)],
    "TalkOnWall": [(102, 40), (103, 40), (102, 40), (104, 40)],  # like Chatter: head tilted, chin, an idea
    "AnsweredOnWall": [(105, 250)],
    "AsleepOnWall": [(106, 250)], "QuietOnWall": [(106, 250)],
    "TodoOnWall": [(107, 100)], "ReminderOnWall": [(108, 100)], "FilesOnWall": [(109, 100)],
    "ImageOnWall": [(109, 100)], "SearchOnWall": [(109, 100)], "WeatherOnWall": [(110, 100)],
    "SleepyOnWall": [(111, 100)], "SystemOnWall": [(112, 100)], "MachineOnWall": [(112, 100)],
    "PowerOnWall": [(112, 100)], "LoveOnWall": [(114, 100)], "DoneOnWall": [(115, 100)],
    "FailedOnWall": [(116, 100)], "UnsureOnWall": [(117, 100)], "AlarmOnWall": [(118, 100)],
    "ColdOnWall": [(119, 100)], "ShellOnWall": [(120, 100)],
    "FullPowerOnWall": [(131, 100)],
}
# Just sitting on its branch, now and then a small movement (owl-gren*.png, the user's idea, 6 Nov: like it does
# things on the floor; no other mascot does anything on a wall yet). Not named *Wall*: --no-climb turns those off
ON_BRANCH = {  # (ticks: 25 is about a second; the user, 6 Nov: not so fast, it held each image a second or two)
    "BranchSit": [(101, 500)],
    "BranchLook": [(101, 75), (122, 100), (101, 75)],
    "BranchTilt": [(101, 75), (124, 100), (101, 75)], "BranchTiltOther": [(101, 75), (125, 100), (101, 75)],
    "BranchContent": [(101, 75), (128, 100), (101, 75)],
    "BranchFluff": [(101, 75), (127, 100), (101, 75)],
    "BranchStretch": [(101, 75), (129, 75), (101, 75)],
    "BranchLookUp": [(101, 75), (130, 125), (101, 75)],
    "BranchLookDown": [(101, 75), (126, 100), (101, 75)],  # (owl-gren3.png, the user, 6 Nov)
}
BRANCH_OFTEN = {"BranchSit": 100}  # (the rest 25 each)
actions += [action(name, "Animate", [frame(n, d) for n, d in fs], "Wall")
            for name, fs in {**ON_WALL, **ON_BRANCH}.items()]
anchored(actions)
behaviors = json.load(source.extractfile("behaviors.json"))
defs = behaviors["definitions"]
floor = next(d for d in defs if d["name"] == "___CONDITION_0")  # on the floor: StandUp, SitDown...
at = defs.index(floor)


def behavior(name, action, frequency, hidden):
    defs.insert(at, {"name": name, "action": action, "next_behavior_list": [], "next_behavior_list_count": 0,
                     "hidden": hidden, "condition": None, "is_conditioner": False,
                     "next_behavior_list_add": True, "frequency": frequency})


for name in FUN:
    behavior(name, name, 25, False)
    floor["next_behavior_list"].append({"name": name, "frequency": 25})
floor["next_behavior_list_count"] = len(floor["next_behavior_list"])
TOOLS = {"Todo": "Scroll", "Reminder": "Watch", "Files": "Magnify", "Image": "Magnify", "Search": "Magnify",
         "Shell": "Wand", "Sleepy": "Drowsy", "System": "Glasses", "Machine": "Glasses", "Power": "Glasses",
         "Love": "Shy", "Weather": "Globe", "Rain": "Umbrella", "Snow": "Snowcap", "Warm": "Thermometer", "Cold": "Shiver", "Unsure": "Puzzled", "Done": "Cheer", "Failed": "Startled", "Alarm": "Alarm",
         "Quiet": "SwitchedOff", "EasterEgg": "Laurel", "FullPower": "Pilot"}
for name, act in TOOLS.items():
    behavior(name, act, 0, True)
for name in ON_WALL:
    behavior(name, name, 0, True)
on_wall = next(d for d in defs if d["name"] == "___CONDITION_1")  # on a wall: FallFromWall
for name in ON_BRANCH:
    behavior(name, name, BRANCH_OFTEN.get(name, 25), False)
    on_wall["next_behavior_list"].append({"name": name, "frequency": BRANCH_OFTEN.get(name, 25)})
on_wall["next_behavior_list_count"] = len(on_wall["next_behavior_list"])
# It stays on its branch until you take it down (the user, 6 Nov: without pressing Stay; only the owl): it never
# flies off by itself. (Off a window's side it still falls when the window moves or closes: no wall left)
for ref in on_wall["next_behavior_list"]:
    if ref["name"] == "FallFromWall":
        ref["frequency"] = 0
next(d for d in defs if d["name"] == "FallFromWall")["frequency"] = 0
# No images for pulling itself up or splitting in two (mascotd picks by the frequency in the list that names it).
# Splitting without its images, or with multiplication off, was only standing still, a small hop and landing on
# the floor (the user, 6 Nov: "a little hop while it stood still", with the landing's puff of dust)
NO_IMAGES = {"PullUpShimeji", "SplitIntoTwo"}
for d in defs:
    if d["name"] in NO_IMAGES:
        d["frequency"] = 0
    for ref in d["next_behavior_list"]:
        if ref["name"] in NO_IMAGES:
            ref["frequency"] = 0
manifest = json.load(source.extractfile("manifest.json"))
manifest["description"] = "Owl: a small brown owl that hops on the floor and flies when it hurries. Made with Google Gemini; CC0."
manifest["artist"] = "HexRebel (made with Google Gemini)"
patched = {"actions.json": json.dumps(actions).encode(), "manifest.json": json.dumps(manifest).encode(),
           "behaviors.json": json.dumps(behaviors).encode()}
with open(dst, "wb") as out:
    out.write(header)
    with tarfile.open(fileobj=out, mode="w") as tar:
        for member in source.getmembers():
            if member.name in patched:
                member.size = len(patched[member.name])
                tar.addfile(member, io.BytesIO(patched[member.name]))
            else:
                tar.addfile(member, source.extractfile(member) if member.isfile() else None)
