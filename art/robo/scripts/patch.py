"""Adds Chatter (talk: thinking), Snooze (sleep) and NewMessage (answered) to a converted Robo .wlshm,
seven things it does now and then on the floor (Hologram, Tinker, Notepad, OpenChest, Giggle, Wink, Laugh), what it
does while a tool runs (Todo, Reminder, Weather, Files, Image, Search, Shell, Sleepy, System), Unsure (a system
tool found nothing to go on) and Alarm (a reminder that is due),
makes it hover (Walk/Run/Dash lean in the glide, bobbing 1, 2, 3, 2), Quiet (switched off)
look straight ahead when it stands still (60), dangle whenever it is held up, and its personality (prompt.md)"""
import io
import json
import os
import sys
import tarfile

src, dst = sys.argv[1], sys.argv[2]


def frame(n, duration, readable=False):
    """readable: also facing right it shows this image as it is, not mirrored (text: NEW, the "z")"""
    return {"type": "Frame", "image": f"shime{n}.qoi", "image_right": f"shime{n}.qoi" if readable else None,
            "image_anchor_x": 64,
            "image_anchor_y": 128, "velocity_x": 0, "velocity_y": 0, "duration": duration}


def action(name, kind, frames):
    return {"type": kind, "name": name,
            "content": [{"type": "Animation", "condition": None, "frames": frames, "hotspots": [],
                         "frame_count": len(frames), "hotspots_count": 0}],
            "content_count": 1, "local_variables": {}, "local_variables_count": 0, "embedded_type": None,
            "loop": False, "condition": None, "border_type": "Floor"}


with open(src, "rb") as f:
    header = f.read(512)
    source = tarfile.open(fileobj=io.BytesIO(f.read()), mode="r:*")

actions = json.load(source.extractfile("actions.json"))
actions += [
    # While it answers: thinks, bobbing slowly, and now and then another way of thinking
    action("Chatter", "Animate", [frame(63, 20), frame(68, 20), frame(63, 20), frame(68, 20),
                                  frame(70, 40), frame(63, 20), frame(68, 20), frame(79, 40)]),
    # Breathing: the "z" rises and sinks
    action("Snooze", "Stay", [frame(47, 40, True), frame(56, 40, True)]),
    action("NewMessage", "Animate", [frame(48, 10, True), frame(57, 10, True)]),
    # A reminder is due: the "!" bulb, standing still (see "alarm" in mascot_chat_doing())
    action("Alarm", "Animate", [frame(88, 100)]),
    # Asleep for a while (Quiet): switched off, grey (see mascot_sleep())
    action("SwitchedOff", "Stay", [frame(86, 250)]),
]
bob = {"Walk": [1, 2, 3, 2], "Run": [1, 2, 3, 2], "Dash": [1, 2, 3, 2]}  # it leans in the glide, bobbing
for a in actions:
    if a["name"] == "Stand" and a["content"] and "frames" in a["content"][0]:
        for f in a["content"][0]["frames"]:
            if f["image"] == "shime1.qoi":
                f["image"] = "shime60.qoi"  # standing still: looking straight ahead
    # Held up: always dangling (held still too), never the standing image
    if a["name"] in ("Pinched", "Resisting"):
        for part in a["content"] or []:
            for f in part.get("frames", []):
                if f["image"] in ("shime1.qoi", "shime60.qoi"):
                    f["image"] = "shime90.qoi"  # hanging straight down; 5-10 swing
    if a["name"] in bob and a["content"] and "frames" in a["content"][0]:
        for i, f in enumerate(a["content"][0]["frames"]):
            f["image"] = f"shime{bob[a['name']][i % 4]}.qoi"
# Things it does now and then on the floor
FUN = {"Hologram": 64, "Tinker": 65, "Notepad": 66, "OpenChest": 67, "Giggle": 74, "Wink": 81, "Laugh": 82}
# Singing (73) only while music plays: experimental, not yet (Mascot has to see that music plays, MPRIS)
# Poses only for a tool
POSES = {"Globe": 69, "Gears": 71, "Meditate": 72, "Salute": 80, "Puzzled": 89}  # the magnifying glass (78): kept for later
actions += [action(name, "Animate", [frame(n, 100)]) for name, n in {**FUN, **POSES}.items()]
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
# While a tool runs for its answer, it shows what it does (see mascot_chat_doing())
TOOLS = {"Todo": "Notepad", "Reminder": "Salute", "Weather": "Globe", "Files": "Hologram", "Image": "Hologram",
         "Search": "Hologram", "Shell": "Gears", "Sleepy": "Meditate", "System": "OpenChest",
         "Unsure": "Puzzled", "Alarm": "Alarm", "Quiet": "SwitchedOff"}
for name, act in TOOLS.items():
    behavior(name, act, 0, True)
manifest = json.load(source.extractfile("manifest.json"))
manifest["description"] = "Robo, Mascot's own mascot: a small hovering robot. Made with Google Gemini from a text prompt; CC0."
manifest["artist"] = "HexRebel (made with Google Gemini)"
patched = {"actions.json": json.dumps(actions).encode(), "manifest.json": json.dumps(manifest).encode(),
           "behaviors.json": json.dumps(behaviors).encode()}
# Robo's personality (the bubble uses it unless a role is chosen): the one in the repository's bundled copy
PROMPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../prototypes/Shimeji.Robo/prompt.md")
with open(PROMPT, "rb") as f:
    prompt = f.read()

with open(dst, "wb") as out:
    out.write(header)
    with tarfile.open(fileobj=out, mode="w") as tar:
        info = tarfile.TarInfo("prompt.md")
        info.size, info.mode = len(prompt), 0o644
        tar.addfile(info, io.BytesIO(prompt))
        for member in source.getmembers():
            if member.name in patched:
                member.size = len(patched[member.name])
                tar.addfile(member, io.BytesIO(patched[member.name]))
            else:
                tar.addfile(member, source.extractfile(member) if member.isfile() else None)
