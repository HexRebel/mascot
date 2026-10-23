#   noclimb.py - strip wall and ceiling behaviours from a prototype
#
#   Copyright (C) 2026  HexRebel
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

# Used by `mascot import --no-climb`. Same rules as scripts/noclimb.py.
# py-compose puts every module in one namespace, hence the noclimb_ prefix.
import re

# Behaviour names that mean a wall or the ceiling...
NOCLIMB_DISABLE = re.compile(r"wall|ceiling|climb|hang", re.I)
# ...except these, which bring the mascot back down and must stay.
NOCLIMB_KEEP = re.compile(r"^(fall|thrown|dragged|dismiss)", re.I)


def noclimb_entry_name(entry) -> str:
    if isinstance(entry, str): return entry
    if isinstance(entry, dict): return entry.get("name") or entry.get("behavior") or ""
    return ""


def noclimb_prune(entries, disabled: set[str]):
    """Drop references to disabled behaviours, recursively."""
    if not isinstance(entries, list):
        return entries
    kept = []
    for entry in entries:
        if noclimb_entry_name(entry) in disabled:
            continue
        if isinstance(entry, dict):
            for key in ("next_behavior_list", "behaviors", "list"):
                if isinstance(entry.get(key), list):
                    entry[key] = noclimb_prune(entry[key], disabled)
                    if f"{key}_count" in entry:
                        entry[f"{key}_count"] = len(entry[key])
        kept.append(entry)
    return kept


def strip_climbing(behaviors: dict) -> list[str]:
    """Never pick a climbing behaviour, in place. Returns the names disabled."""
    definitions = behaviors.get("definitions", [])
    disabled = {d["name"] for d in definitions
                if NOCLIMB_DISABLE.search(d.get("name", "")) and not NOCLIMB_KEEP.search(d["name"])}

    for definition in definitions:
        if definition["name"] in disabled:
            definition["frequency"] = 0
        chain = definition.get("next_behavior_list")
        if not chain:
            continue
        pruned = noclimb_prune(chain, disabled)
        if len(pruned) == len(chain):
            continue
        definition["next_behavior_list"] = pruned
        if "next_behavior_list_count" in definition:
            definition["next_behavior_list_count"] = len(pruned)
        # An empty chain without add would leave the mascot with nothing to do next
        if not pruned:
            definition["next_behavior_list_add"] = True

    # The root list is what behaviours are picked from; frequency alone is not enough
    for key in ("root_behavior_list", "root_behaviors"):
        if isinstance(behaviors.get(key), list):
            behaviors[key] = noclimb_prune(behaviors[key], disabled)
            if f"{key}_count" in behaviors:
                behaviors[f"{key}_count"] = len(behaviors[key])

    return sorted(disabled)
