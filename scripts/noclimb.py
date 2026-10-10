#!/usr/bin/env python3
"""mascot-noclimb - slaa vaeg- og loftsadfaerd fra i konverterede prototyper.

    mascot-noclimb report <proto-dir> [...]
    mascot-noclimb apply  <proto-dir> [...]

Skriver .bak foer aendringer. Idempotent.
"""
from __future__ import annotations
import collections, json, pathlib, re, shutil, sys

# Adfaerdsnavne der betyder vaeg eller loft.
DISABLE = re.compile(r"wall|ceiling|climb|hang", re.I)
# Maa aldrig slaas fra, ogsaa hvis de matcher ovenstaaende.
# Fall* bringer mascotten NED igen - den skal bevares.
KEEP = re.compile(r"^(fall|thrown|dragged|dismiss)", re.I)


def entry_name(e):
    if isinstance(e, str): return e
    if isinstance(e, dict): return e.get("name") or e.get("behavior") or ""
    return ""


def load(p): return json.loads(p.read_text(encoding="utf-8"))


def hits(name): return bool(DISABLE.search(name)) and not KEEP.search(name)


def prune_list(lst, dis):
    """Fjern deaktiverede poster rekursivt. Returnerer (ny_liste, antal_fjernet)."""
    if not isinstance(lst, list):
        return lst, 0
    out, n = [], 0
    for e in lst:
        if entry_name(e) in dis:
            n += 1
            continue
        if isinstance(e, dict):
            for k in ("next_behavior_list", "behaviors", "list"):
                if isinstance(e.get(k), list):
                    e[k], sub = prune_list(e[k], dis)
                    n += sub
                    if f"{k}_count" in e:
                        e[f"{k}_count"] = len(e[k])
        out.append(e)
    return out, n


def report(d: pathlib.Path):
    beh = load(d / "behaviors.json")
    print(f"\n######## {d.name} ########")
    print("behaviors.json top-level noegler:", list(beh.keys()))
    defs = beh.get("definitions", [])
    bad = {id(x) for x in defs if hits(x.get("name", ""))}
    print(f"\n-- {len(defs)} behaviors, {len(bad)} matcher vaeg/loft (markeret X) --")
    print(f"{'X':<2}{'freq':>6} {'hidden':>7}  {'navn':<34} {'action':<16} next")
    for x in defs:
        n = len(x.get("next_behavior_list") or [])
        print(f"{'X' if id(x) in bad else ' ':<2}{x.get('frequency',0):>6} "
              f"{str(x.get('hidden')):>7}  {x.get('name',''):<34} "
              f"{str(x.get('action')):<16} {n}")
    dis = {x["name"] for x in defs if hits(x.get("name", ""))}
    refs = [(x["name"], entry_name(e)) for x in defs
            for e in (x.get("next_behavior_list") or []) if entry_name(e) in dis]
    print(f"\n-- {len(refs)} kaeder peger paa en deaktiveret adfaerd (prunes) --")
    for a, b in refs: print(f"   {a} -> {b}")
    for key in ("root_behavior_list", "root_behaviors"):
        if isinstance(beh.get(key), list):
            names = [entry_name(e) for e in beh[key]]
            kill = [n for n in names if n in dis]
            print(f"\n-- {key}: {len(names)} poster, {len(kill)} prunes --")
            for n in names:
                print(f"   {'X' if n in dis else ' '} {n}")
    bt = collections.Counter()
    def walk(o):
        if isinstance(o, dict):
            if "border_type" in o: bt[o["border_type"]] += 1
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(load(d / "actions.json"))
    print("\n-- border_type i actions.json --", dict(bt))


def apply(d: pathlib.Path):
    p = d / "behaviors.json"
    bak = d / "behaviors.json.bak"
    if not bak.exists(): shutil.copy2(p, bak)
    beh = load(p)
    defs = beh.get("definitions", [])

    dis = set()
    for x in defs:
        if hits(x.get("name", "")):
            x["frequency"] = 0
            dis.add(x["name"])

    pruned = stuck = 0
    for x in defs:
        nl = x.get("next_behavior_list") or []
        keep, n = prune_list(nl, dis)
        if n:
            pruned += n
            x["next_behavior_list"] = keep
            if "next_behavior_list_count" in x:
                x["next_behavior_list_count"] = len(keep)
            # Tom kaede + add=false = mascot uden next behavior. Fald tilbage
            # til den normale pulje i stedet for at risikere en doed mascot.
            if not keep and not x.get("next_behavior_list_add", False):
                x["next_behavior_list_add"] = True
                stuck += 1

    # root_behavior_list er rodpuljen adfaerd vaelges fra. Uden den her kan
    # klatring stadig vaelges, uanset frequency i 'definitions'.
    root_pruned = 0
    for key in ("root_behavior_list", "root_behaviors"):
        if isinstance(beh.get(key), list):
            before = len(beh[key])
            beh[key], root_pruned = prune_list(beh[key], dis)
            if f"{key}_count" in beh:
                beh[f"{key}_count"] = len(beh[key])
            print(f"   {key}: {before} -> {len(beh[key])} poster")

    p.write_text(json.dumps(beh, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{d.name}: {len(dis)} behaviors -> frequency 0, "
          f"{pruned} kaede-ref. fjernet, {root_pruned} rod-poster fjernet, "
          f"{stuck} tomme kaeder faar add=true")
    if dis: print("   " + ", ".join(sorted(dis)))


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("report", "apply"):
        print(__doc__); sys.exit(2)
    fn = report if sys.argv[1] == "report" else apply
    for a in sys.argv[2:]: fn(pathlib.Path(a))
