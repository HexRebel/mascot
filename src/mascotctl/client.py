# Modified for Mascot by HexRebel, 2026; see the git history for details.
from __future__ import annotations
import socket
import errno
import os
import sys
import re
import shutil
import struct
import random
from typing import Callable, Any
import argparse
import subprocess
import zipfile
import tempfile
from compiler import *
import xml.etree.ElementTree as ET
import tarfile
import io
import base64
import html
from PIL import Image
from qoi.src.qoi import encode_img
import time

from levenstein import lv_variant
from noclimb import strip_climbing
from chatsetup import *
import codecs
import termios

import random

import logging

from ipc_protocol import Packet,\
ServerHello, ClientHello, Notice, StartSession, EnvironmentAnnouncement, EnvironmentChanged, EnvironmentMascot, EnvironmentWithdrawn, StartPrototype, PrototypeName, PrototypeDisplayName, PrototypePath, PrototypeFD, PrototypeAddAction, PrototypeAddBehavior, PrototypeIcon, PrototypeAuthor, PrototypeVersion, CommitPrototypes, MascotMigrated, MascotDisposed, MascotInfo, MascotClicked, SelectionDone, SelectionCancelled, ImportFailed, ImportStarted, ImportFinished, ImportProgress, ExportFailed, ExportFinished, ConfigKey, ClickEventExpired, PrototypeWithdraw, ReloadPrototype, Spawn, MascotGetInfo, MascotInfo, ApplyBehavior, Stop, Sync, SyncDone, GetConfigKey, ListConfigKeys, SetConfigKey, ConfigKey, Disconnect,\
Prototype, Environment, Mascot, Selection, Import, Export, PluginRestoreWindows,\
objects, prototypes, environments, mascots, active_selection, imports, exports

logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)


class Client:
    deserializers: dict[int, type[Packet]] = {
        0x01: ServerHello,
        0x03: Notice,
        0x04: StartSession,
        0x05: EnvironmentAnnouncement,
        0x06: EnvironmentChanged,
        0x07: EnvironmentMascot,
        0x08: EnvironmentWithdrawn,
        0x09: StartPrototype,
        0x0A: PrototypeName,
        0x0B: PrototypeDisplayName,
        0x0C: PrototypePath,
        0x0D: PrototypeFD,
        0x0E: PrototypeAddAction,
        0x0F: PrototypeAddBehavior,
        0x10: PrototypeIcon,
        0x11: PrototypeAuthor,
        0x12: PrototypeVersion,
        0x13: CommitPrototypes,
        0x14: MascotMigrated,
        0x15: MascotDisposed,
        0x17: MascotInfo,
        0x18: MascotClicked,
        0x1F: SelectionDone,
        0x20: SelectionCancelled,
        0x23: ImportFailed,
        0x24: ImportStarted,
        0x25: ImportFinished,
        0x26: ImportProgress,
        0x28: ExportFailed,
        0x29: ExportFinished,
        0x54: ConfigKey,
        0x55: ClickEventExpired,
        0x57: PrototypeWithdraw,
        0x5B: SyncDone
    }

    prototypes_pending: dict[int, Prototype] = {}

    packet_callbacks: dict[type[Packet], Callable] = {}

    initialized: bool = False
    synced: bool = False

    def SyncDone(self, packet: SyncDone):
        self.synced = True

    def StartSession(self, packet: StartSession):
        self.initialized = True
        logger.debug(f"Session started with {len(environments)} environments")
        logger.debug(f"Session started with {len(prototypes)} prototypes")
        logger.debug(f"Session started with {len(mascots)} mascots")

    def StartPrototype(self, packet: StartPrototype):
        self.prototypes_pending[packet.prototype_id] = Prototype(packet.prototype_id, self.socket)
        objects[packet.prototype_id] = self.prototypes_pending[packet.prototype_id]

    def PrototypeName(self, packet: PrototypeName):
        prototype = self.prototypes_pending.get(packet.object_id)
        if prototype:
            prototype.name = packet.name

    def PrototypeDisplayName(self, packet: PrototypeDisplayName):
        prototype = self.prototypes_pending.get(packet.object_id)
        if prototype:
            prototype.display_name = packet.display_name

    def PrototypePath(self, packet: PrototypePath):
        prototype = self.prototypes_pending.get(packet.object_id)
        if prototype:
            prototype.path = packet.path

    def PrototypeFD(self, packet: PrototypeFD):
        prototype = self.prototypes_pending.get(packet.object_id)
        if prototype:
            prototype.fd = os.dup(packet.fd)

    def PrototypeAddAction(self, packet: PrototypeAddAction):
        prototype = self.prototypes_pending.get(packet.object_id)
        if prototype:
            prototype.actions.append(packet.action)

    def PrototypeAddBehavior(self, packet: PrototypeAddBehavior):
        prototype = self.prototypes_pending.get(packet.object_id)
        if prototype:
            prototype.behaviors.append(packet.behavior)

    def PrototypeIcon(self, packet: PrototypeIcon):
        prototype = self.prototypes_pending.get(packet.object_id)
        if prototype:
            prototype.icon_fd = os.dup(packet.iconfd)

    def PrototypeAuthor(self, packet: PrototypeAuthor):
        prototype = self.prototypes_pending.get(packet.object_id)
        if prototype:
            prototype.author = packet.author

    def PrototypeVersion(self, packet: PrototypeVersion):
        prototype = self.prototypes_pending.get(packet.object_id)
        if prototype:
            prototype.version = packet.version

    def CommitPrototypes(self, packet: CommitPrototypes):
        for prototype in self.prototypes_pending.values():
            prototypes[prototype.id] = prototype
        logger.debug(f"Commited {len(self.prototypes_pending)} prototypes")
        self.prototypes_pending.clear()

    def EnvironmentAnnouncement(self, packet: EnvironmentAnnouncement):
        environment = Environment(packet.new_id, self.socket, packet.name, packet.description, packet.x, packet.y, packet.width, packet.height, packet.scale)
        environments[environment.id] = environment
        objects[environment.id] = environment

    def EnvironmentChanged(self, packet: EnvironmentChanged):
        environment = environments.get(packet.object_id)
        if environment:
            environment.change(packet.name, packet.description, packet.x, packet.y, packet.width, packet.height, packet.scale)

    def EnvironmentWithdrawn(self, packet: EnvironmentWithdrawn):
        environment = environments.get(packet.object_id)
        if environment:
            environment.withdraw(packet)

    def EnvironmentMascot(self, packet: EnvironmentMascot):
        environment = environments.get(packet.object_id)
        if environment:
            environment.mascot_added(packet)

    def SelectionDone(self, packet: SelectionDone):
        selection = objects.get(packet.object_id)
        if selection:
            selection.selected(packet)

    def SelectionCancelled(self, packet: SelectionCancelled):
        selection = objects.get(packet.object_id)
        if selection:
            selection.cancelled(packet)

    def Disconnect(self, packet: Disconnect):
        logging.info("Disconnected by overlay.")
        self.socket.close()
        exit(0)

    def Notice(self, packet: Notice):

        strings = {
            "config.warning.get": "Config has no key named \"{}\"",
            "config.warning.set": "Config has no key named \"{}\"",
            "prototype.error.no_behavior": "Prototype has no behavior named \"{}\"",
            "apply_behavior.error.no_mascot": "Mascot not found"
        }

        if packet.message == "connector.error.initialization":
            # mascotd could not start: say why, and what to do when the desktop cannot show it
            text = "Mascot could not start:\n" + "\n".join(str(v).strip() for v in packet.formating_values)
            if "wlr_layer_shell" in text or "wl_subcompositor" in text:
                text += ("\n\nYour desktop does not support what Mascot needs to draw on the screen (wlr-layer-shell). "
                         "GNOME does not; Mascot works on Hyprland, Sway and other wlroots compositors, and KDE Plasma.")
            logger.error(text)
        else:
            [logger.info, logger.warning, logger.error][packet.severity](strings.get(packet.message, packet.message).format(*packet.formating_values))

        if packet.severity == 2:
            exit(1)

    def __init__(self, address: str, startup_options: dict[str, Any] | None = None):
        self.address = address
        self.startup_options = startup_options or {}
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)

        self.packet_callbacks = {
            StartSession: Client.StartSession,
            StartPrototype: Client.StartPrototype,
            CommitPrototypes: Client.CommitPrototypes,
            PrototypeName: Client.PrototypeName,
            PrototypeDisplayName: Client.PrototypeDisplayName,
            PrototypePath: Client.PrototypePath,
            PrototypeFD: Client.PrototypeFD,
            PrototypeAddAction: Client.PrototypeAddAction,
            PrototypeAddBehavior: Client.PrototypeAddBehavior,
            PrototypeAuthor: Client.PrototypeAuthor,
            PrototypeIcon: Client.PrototypeIcon,
            PrototypeVersion: Client.PrototypeVersion,
            EnvironmentMascot: Client.EnvironmentMascot,
            EnvironmentAnnouncement: Client.EnvironmentAnnouncement,
            EnvironmentChanged: Client.EnvironmentChanged,
            EnvironmentWithdrawn: Client.EnvironmentWithdrawn,
            SelectionDone: Client.SelectionDone,
            SelectionCancelled: Client.SelectionCancelled,
            Notice: Client.Notice,
            SyncDone: Client.SyncDone,
            Disconnect: Client.Disconnect,
        }

        logger.debug(f"Connecting to overlay at \"{self.address}\"")
        try:
            self.socket.connect(self.address)
            if self.startup_options.get("start", None):
                logger.info("Overlay is already running")
                raise SystemExit(1)
        except (ConnectionRefusedError, FileNotFoundError) as e:
            if not (self.startup_options.get("start", True)):
                if not self.startup_options.get("is_config_req", False):
                    logger.info("Overlay is not running")
                raise SystemExit(1)
            logger.debug(f"Failed to connect to overlay at \"{self.address}\": {e}")
            logger.debug(f"Starting overlay with args {self.startup_options.get('cmdline', [])}")
            self.socket, overlay_side = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            cmdline = ["mascotd"]
            cmdline.extend(self.startup_options.get('cmdline', []))
            cmdline.append('-cfd')
            cmdline.append(str(overlay_side.fileno()))
            proc_handle = subprocess.Popen(
                cmdline, close_fds=True, pass_fds=[overlay_side.fileno()], start_new_session=True,
                stdout=None if self.startup_options.get("verbose", False) else subprocess.DEVNULL,
                stderr=None if self.startup_options.get("verbose", False) else subprocess.DEVNULL,
            )
            overlay_side.close()
            out = None
            try:
                out = proc_handle.wait(timeout=1)
            except subprocess.TimeoutExpired:
                ...
            if out is not None:
                logger.error(f"Failed to start overlay: {out}")
                raise SystemExit(1)


        except Exception as e:
            logger.error(f"Failed to connect to overlay: {e}")
            raise SystemExit(1)

        logger.debug("Connected to overlay")

        self.queue_packet(ClientHello(0x200000))  # protocol 0.1.0
        self.dispatch_events(until=lambda: self.initialized)

    # Waits until the overlay has handled everything sent so far, so its notices
    # (e.g. an unknown behavior) are shown before a one-shot command exits.
    # Overlays without sync() never answer, hence the timeout
    def sync(self, timeout: float = 2.0):
        self.synced = False
        self.queue_packet(Sync())
        deadline = time.time() + timeout
        previous = self.socket.gettimeout()
        try:
            while not self.synced:
                remaining = deadline - time.time()
                if remaining <= 0:
                    logger.debug("Overlay did not answer sync()")
                    break
                self.socket.settimeout(remaining)
                try:
                    buffer, fds, _, _ = socket.recv_fds(self.socket, 4096, 10)
                except TimeoutError:
                    continue
                if not buffer:
                    break
                self.handle_packet(buffer, fds)
        except OSError:
            pass # the overlay went away (e.g. after stop)
        finally:
            self.socket.settimeout(previous)

    def queue_packet(self, packet: Packet):
        socket.send_fds(self.socket, [packet.encode()], packet.fds)
        # print(f"Sending packet {packet}, {packet.fds}, {packet.buffer}")

    def dispatch_events(self, until: Callable | None = None):
        if until is None:
            until = lambda: False
        while not until():
            buffer, fds, _, _ = socket.recv_fds(self.socket, 4096, 10)
            if buffer is None:
                continue
            try:
                self.handle_packet(buffer, fds)
            except Exception as e:
                logger.error(f"Failed to handle packet: {e}")
                raise e

    def handle_packet(self, buffer: bytes, fds: list[int]):
        if len(buffer) < 8:
            raise ValueError(f"Invalid header in packet (Expected at least 8 bytes, got {len(buffer)})")
        packet_id, flags, _, object_id = struct.unpack('bbHI', buffer[:8])
        packet_type = self.deserializers.get(packet_id)

        if packet_type is None:
            return

        packet: Packet = packet_type(packet_id, flags, object_id, buffer)
        packet.fds = fds
        packet.decode()

        packet_handler = self.packet_callbacks.get(packet_type)
        if packet_handler is not None:
            packet_handler(self, packet)

    def register_callback(self, packet_type: type[Packet], callback: Callable):
        self.packet_callbacks[packet_type] = callback

# Spawn packs coordinates as uint32, so they must be whole and non-negative
def coordinate(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a whole number")
    if number < 0:
        raise argparse.ArgumentTypeError(f"'{value}' is negative")
    return number

def position(value: str) -> tuple[int, int]:
    x, sep, y = value.partition(",")
    if not sep:
        raise argparse.ArgumentTypeError(f"'{value}' is not in the format x,y")
    return coordinate(x.strip()), coordinate(y.strip())

# Object ids carry their protocol type in the top byte (PROTOCOL_OBJECT_MASCOT = 2 in
# src/protocol/server.h); users give the number the daemon logs, "<Mascot:Shimeji:2>"
MASCOT_OBJECT_TYPE = 2

def mascot_by_id(value: str) -> Mascot | None:
    number = int(value)
    return mascots.get(number) or mascots.get(number | (MASCOT_OBJECT_TYPE << 24))

def prototype_find(name: str) -> Prototype | None:
    if name.isdigit():
        if int(name) in prototypes:
            return prototypes[int(name)]

    best_match = lv_variant([x.name for x in prototypes.values()] + [x.display_name for x in prototypes.values()], name)
    for proto in prototypes.values():
        if proto.name == best_match:
            return proto
        elif proto.display_name == best_match:
            return proto

    return None

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def asset_name(file: str) -> str:
    """What an image is called in the prototype's assets (any letter case of the suffix)"""
    base, suffix = os.path.splitext(file)
    return base + ".qoi" if suffix.lower() in IMAGE_SUFFIXES else file


def match_image_case(actions_json: str, image_dir: str) -> tuple[str, list[str]]:
    """Shimeji-ee packs come from Windows, where swag1.png finds Swag1.png: points
    each frame at the image it means, whatever the letter case. Returns the
    actions and the images not there at all"""
    assets = {}
    for path, dirs, files in os.walk(image_dir):
        rel = os.path.relpath(path, image_dir)
        for file in files:
            if file.lower().endswith(IMAGE_SUFFIXES):
                name = asset_name(file) if rel == "." else os.path.join(rel, asset_name(file))
                assets.setdefault(os.path.splitext(name)[0].lower(), name)

    missing = set()

    def fix(node):
        if isinstance(node, dict):
            if node.get("type") == "Frame":
                for key in ("image", "image_right"):
                    image = node.get(key)
                    if isinstance(image, str):
                        found = assets.get(os.path.splitext(image)[0].lower())
                        if found:
                            node[key] = found
                        else:
                            missing.add(image)
            for value in node.values():
                fix(value)
        elif isinstance(node, list):
            for value in node:
                fix(value)

    actions = json.loads(actions_json)
    fix(actions)
    return json.dumps(actions, indent=4), sorted(missing)


def pack_name(path: str) -> str:
    """A name for the mascot of a pack that does not name it: the file's,
    without "Shimeji(-ee)" and a version, e.g. "Testy" for "Testy Shimeji v1.2.zip" """
    name = os.path.splitext(os.path.basename(os.path.normpath(path)))[0] if os.path.isfile(path) \
        else os.path.basename(os.path.normpath(path))
    name = re.sub(r"(?i)[\s_-]*(shimeji(-?ee)?|pack)\b", " ", name)
    name = re.sub(r"(?i)\s+v?\d+(\.\d+)*\s*$", "", name)
    return " ".join(name.replace("_", " ").split()) or "Mascot"


def has_images(directory: str) -> bool:
    return any(f.lower().endswith(IMAGE_SUFFIXES) for f in os.listdir(directory)
               if os.path.isfile(os.path.join(directory, f)))


def is_shime_dir(directory: str) -> bool:
    """Whether a directory holds a Shimeji's images (shime1.png, ...)"""
    return any(re.fullmatch(r"shime1\.(png|gif|jpe?g|webp)", f, re.I) for f in os.listdir(directory))


def open_instance(path: str) -> tuple[list[dict], tempfile.TemporaryDirectory | None]:
    """The mascots in a pack (a directory or a zip file, unpacked into a
    temporary directory that is returned too); exits if there are none.

    A mascot is {"name", "images", "confs"}: its image directory and the conf
    directories that may have its actions.xml and behaviors.xml, its own first.
    Packs come as a Shimeji-ee instance (img/<name>/ and conf/, maybe a few
    directories down, conf/ maybe only inside img/<name>/), as img/ with the
    images right in it, or as images alone (shime1.png ...): no confs, so the
    bundled Shimeji's actions are used"""
    if not os.path.exists(path):
        print(f"Input file '{path}' does not exist.")
        exit(1)

    root = path
    unpacked = None
    if not os.path.isdir(root):
        try:
            zipf = zipfile.ZipFile(root, 'r')
        except Exception as e:
            print(f"Cannot open '{path}': not a zip file or a directory ({e})")
            exit(1)
        unpacked = tempfile.TemporaryDirectory()
        root = unpacked.name
        zipf.extractall(root)

    default_name = pack_name(path)
    figures = []
    for directory, dirs, files in os.walk(root):
        dirs.sort()
        depth = os.path.relpath(directory, root).count(os.sep) + (directory != root)
        if depth > 4 or os.path.basename(directory).lower() in ("unused", "__macosx"):
            dirs[:] = []
            continue
        img = next((os.path.join(directory, d) for d in dirs if d.lower() == "img"), None)
        if img:
            conf = next((os.path.join(directory, d) for d in dirs if d.lower() == "conf"), None)
            shared = [conf] if conf else []
            for entry in sorted(os.listdir(img)):
                images = os.path.join(img, entry)
                if os.path.isdir(images) and entry.lower() != "unused" and has_images(images):
                    own = os.path.join(images, "conf")
                    figures.append({"name": entry, "images": images,
                                    "confs": ([own] if os.path.isdir(own) else []) + shared})
            # Shimeji 1.0: img/shime1.png and conf/ next to it
            if is_shime_dir(img):
                figures.append({"name": default_name, "images": img, "confs": shared})
            dirs[:] = []
        elif is_shime_dir(directory):
            own = os.path.join(directory, "conf")
            name = default_name if directory == root else os.path.basename(directory)
            figures.append({"name": name, "images": directory, "confs": [own] if os.path.isdir(own) else []})
            dirs[:] = []

    # The same name twice (e.g. two copies of a pack in one zip): keep the first
    seen = set()
    figures = [f for f in figures if not (f["name"].lower() in seen or seen.add(f["name"].lower()))]
    if not figures:
        print(f"No mascots found in '{path}': it has neither a Shimeji-ee img directory nor shime1.png")
        exit(1)
    return figures, unpacked


def choose_prototypes(figures: list[dict], wanted: list[str] | None, everything: bool) -> list[dict]:
    """The mascots of a pack to convert: those named with --figure (any letter
    case), all with --all, the only one, or else the ones the user picks"""
    prototype_names = [f["name"] for f in figures]

    if wanted:
        selected = []
        for figure in wanted:
            match = next((f for f in figures if f["name"].lower() == figure.lower()), None)
            if not match:
                print(f"No mascot called '{figure}' in the pack. It has: {', '.join(prototype_names)}")
                exit(1)
            selected.append(match)
        return selected
    if everything or len(figures) == 1:
        return figures

    print("Prototypes available for conversion:")
    for i, prototype_name in enumerate(prototype_names):
        print(f"{i+1}. {prototype_name}")
    print("\nEnter prototypes index or name to convert (can be comma-separated or A to convert all)")
    user_input = input(">").rstrip().lstrip()

    if user_input.upper() == "A":
        return figures

    selected = []
    for index in user_input.split(","):
        index = index.strip()
        if not index.isnumeric():
            match = next((f for f in figures if f["name"].lower() == index.lower()), None)
            if match:
                selected.append(match)
        else:
            index = int(index)
            if index > 0 and index <= len(figures):
                selected.append(figures[index-1])

    if not selected:
        print("No prototypes selected")
        exit(1)
    return selected


def bundled_shimeji() -> str | None:
    """The bundled Shimeji (installed to share/mascot/prototypes next to bin/,
    or prototypes/ in the source tree), whose actions a pack of images alone uses"""
    here = os.path.dirname(os.path.realpath(sys.argv[0]))
    for candidate in (os.path.join(here, "..", "share", "mascot", "prototypes", "Shimeji.Shimeji"),
                      os.path.join(here, "..", "prototypes", "Shimeji.Shimeji")):
        if os.path.isfile(os.path.join(candidate, "actions.json")):
            return os.path.normpath(candidate)
    return None


def broken_actions(actions: dict, missing: set) -> tuple[set, set]:
    """The actions the overlay drops (by name), and the action names used but
    not defined: an animation whose image is missing drops the action it is
    part of, and that every action it is a part of, and so on up"""
    def frames(node):
        if isinstance(node, dict):
            if node.get("type") == "Frame":
                yield node
            for value in node.values():
                yield from frames(value)
        elif isinstance(node, list):
            for value in node:
                yield from frames(value)

    def references(node):
        if isinstance(node, dict):
            if node.get("type") == "ActionReference":
                yield node.get("action_name")
            for value in node.values():
                yield from references(value)
        elif isinstance(node, list):
            for value in node:
                yield from references(value)

    broken = {name for name, action in actions.items()
              if any(f.get("image") in missing or f.get("image_right") in missing for f in frames(action))}
    unknown = set()
    changed = True
    while changed:
        changed = False
        for name, action in actions.items():
            if name in broken:
                continue
            for ref in references(action):
                if ref not in actions:
                    unknown.add(ref)
                if ref not in actions or ref in broken:
                    broken.add(name)
                    changed = True
                    break
    return broken, unknown


def check_prototype(actions_json: str, behaviors_json: str, missing_images: list[str]) -> list[str]:
    """What will not work in a converted mascot, in words for its user (see
    broken_actions(); every behavior that uses a dropped action goes too)"""
    actions = {a["name"]: a for a in json.loads(actions_json)}
    behaviors = json.loads(behaviors_json).get("definitions", [])
    missing = set(missing_images)
    broken, unknown = broken_actions(actions, missing)

    problems = []
    if missing:
        problems.append(f"uses images that are not in the pack: {', '.join(sorted(missing))}")
    if unknown:
        problems.append(f"uses actions that are not defined: {', '.join(sorted(unknown))}")
    lost = sorted(b["name"] for b in behaviors
                  if b.get("action") and (b["action"] not in actions or b["action"] in broken))
    if lost:
        problems.append(f"goes without these behaviors because of that: {', '.join(lost)}")
    names = {b["name"] for b in behaviors if b.get("action") and b["action"] in actions and b["action"] not in broken}
    for needed, what in (("Fall", "falling"), ("Dragged", "being dragged"), ("Thrown", "being thrown"),
                         ("SitDown", "sitting while you chat")):
        if needed not in names:
            problems.append(f"has no working {needed} behavior, used for {what}")
    return problems


def convert_prototype(figure: dict, output: str, name: str | None = None) -> str | None:
    """Converts one mascot of a pack (see open_instance()) to a .wlshm at
    output, as name (else its own); returns output, or None if it failed (and
    says why)"""
    label = figure["name"]
    # Its own conf wins if it has both files (many packs keep only info.xml
    # there), else the pack's; with neither, the bundled Shimeji's actions
    conf = next((c for c in figure["confs"]
                 if all(os.path.isfile(os.path.join(c, xml)) for xml in ("actions.xml", "behaviors.xml"))), None)
    if conf:
        config_dirfd = os.open(conf, os.O_PATH)
        try:
            scripts, actions, behaviors = Compiler.compile_shimeji(figure["images"], config_dirfd)
        except Exception as e:
            print(f"Conversion failed for {label}: {e}")
            return None
        finally:
            os.close(config_dirfd)
    else:
        bundled = bundled_shimeji()
        if not bundled:
            print(f"Conversion failed for {label}: it has no actions.xml, and the bundled Shimeji's are not installed")
            return None
        print(f"{label} has no actions of its own: it uses the bundled Shimeji's")
        with open(os.path.join(bundled, "scripts.json")) as f:
            scripts = f.read()
        with open(os.path.join(bundled, "actions.json")) as f:
            actions = f.read()
        with open(os.path.join(bundled, "behaviors.json")) as f:
            behaviors = f.read()

    actions, missing = match_image_case(actions, figure["images"])
    for problem in check_prototype(actions, behaviors, missing):
        print(f"Warning: {label} {problem}")

    manifest = \
    {
        "name": f"Shimeji.{name or figure['name']}",
        "version": "0.0.1",
        "description": "",
        "display_name": name or figure["name"],
        "programs": "scripts.json",
        "actions": "actions.json",
        "behaviors": "behaviors.json",
        "assets": "assets",
        "icon": None,
        "artist": None,
        "scripter": None,
        "commissioner": None,
        "support": None
    }

    # info.xml sits next to actions.xml, or in the image directory or its conf
    info_path = None
    for candidate in figure["confs"] + [figure["images"]]:
        if os.path.isfile(os.path.join(candidate, "info.xml")):
            info_path = os.path.join(candidate, "info.xml")
            break

    root = None
    if info_path:
        try:
            root = ET.parse(info_path).getroot()
        except ET.ParseError as e:
            print(f"Ignoring {info_path}: {e}")

    if root is not None:
        # Shimeji-ee files use the http://www.group-finity.com/Mascot namespace
        for element in root.iter():
            element.tag = element.tag.rpartition("}")[2]

        # Credits are usually <Artist Name="…" URL="…"/>, but accept text too
        def info_text(tag):
            element = root.find(f"Information/{tag}")
            if element is None:
                return None
            text = (element.text or "").strip() or element.get("Name", "").strip()
            return text or None

        manifest["display_name"] = name or info_text("Name") or manifest["display_name"]
        for key, tag in (("artist", "Artist"), ("scripter", "Scripter"),
                         ("commissioner", "Commissioner"), ("support", "Support")):
            manifest[key] = info_text(tag)

        icon_name = info_text("PreviewImage")
        if icon_name is not None:
            manifest["icon"] = icon_name.removesuffix(".png")\
            .removesuffix(".jpg")\
            .removesuffix(".jpeg")\
            .removesuffix(".gif")\
            .removesuffix(".webp") + ".qoi"

    memfile = io.BytesIO()
    tar = tarfile.open(fileobj=memfile, mode="w")

    tarinfo = tarfile.TarInfo("manifest.json")
    tarinfo.size = len(json.dumps(manifest).encode("utf-8"))
    tar.addfile(tarinfo, io.BytesIO(json.dumps(manifest).encode("utf-8")))

    tarinfo = tarfile.TarInfo("scripts.json")
    tarinfo.size = len(scripts.encode("utf-8"))
    tar.addfile(tarinfo, io.BytesIO(scripts.encode("utf-8")))

    tarinfo = tarfile.TarInfo("actions.json")
    tarinfo.size = len(actions.encode("utf-8"))
    tar.addfile(tarinfo, io.BytesIO(actions.encode("utf-8")))

    tarinfo = tarfile.TarInfo("behaviors.json")
    tarinfo.size = len(behaviors.encode("utf-8"))
    tar.addfile(tarinfo, io.BytesIO(behaviors.encode("utf-8")))

    tarinfo = tarfile.TarInfo("assets/")
    tarinfo.type = tarfile.DIRTYPE
    tar.addfile(tarinfo)

    for path, dirs, files in os.walk(figure["images"]):
        # A figure's conf directory holds no images, nor does "unused"
        dirs[:] = [d for d in dirs if d.lower() not in ("conf", "unused")]
        if path != figure["images"]:
            tarinfo = tarfile.TarInfo("assets/" + path.removeprefix(figure["images"]))
            tarinfo.type = tarfile.DIRTYPE
            tar.addfile(tarinfo)

        for file in files:
            if file.lower().endswith(IMAGE_SUFFIXES):
                img = Image.open(os.path.join(path, file))
                tempf = tempfile.NamedTemporaryFile(delete=False)
                tempf.close()
                encode_img(img, False, tempf.name)
                tempf = open(tempf.name, "rb")
                tarinfo = tarfile.TarInfo("assets/" + os.path.join(path.removeprefix(figure["images"]), asset_name(file)))
                tarinfo.size = os.path.getsize(tempf.name)
                tar.addfile(tarinfo, tempf)
                tempf.close()
                os.remove(tempf.name)

    tar.close()

    wlpak_prefix = b"WLPK"
    wlpak_prefix += struct.pack(f"B{len(manifest['name'].encode('utf-8'))}s", len(manifest['name'].encode("utf-8")), manifest['name'].encode("utf-8"))
    wlpak_prefix += struct.pack(f"B{len(manifest['version'].encode('utf-8'))}s", len(manifest['version'].encode("utf-8")), manifest['version'].encode("utf-8"))
    wlpak_prefix += b"\x00" * (512 - len(wlpak_prefix))

    # Only create the file once conversion has succeeded
    with open(output, "wb") as wlpak:
        wlpak.write(wlpak_prefix)
        wlpak.write(memfile.getvalue())
    return output


def converter_handler(arguments: argparse.Namespace, parser):
    if not os.path.exists(arguments.output):
        os.makedirs(arguments.output, exist_ok=True)

    if not os.path.isdir(arguments.output):
        print("Output is not a directory.")
        exit(1)

    figures, unpacked = open_instance(arguments.input)
    selected = choose_prototypes(figures, arguments.figure, arguments.all)
    if arguments.name and len(selected) != 1:
        print("--name gives one mascot a name; pick one with --figure")
        exit(1)

    failed = 0
    for figure in selected:
        name = arguments.name or figure["name"]
        output = os.path.join(arguments.output, f"Shimeji.{name}.wlshm")
        if os.path.exists(output) and not arguments.force:
            print(f"File {output} already exists")
            failed += 1
            continue
        if convert_prototype(figure, output, arguments.name):
            print(f'Converted {figure["name"]} to {output}')
        else:
            failed += 1

    if failed:
        exit(1)


def converted_for_import(arguments: argparse.Namespace) -> list:
    """mascot import takes Shimeji-ee packs too: replaces each one in
    arguments.input with its mascots converted to .wlshm files, in temporary
    directories that are returned (keep them until the import is done)"""
    keep = []
    inputs = []
    for path in arguments.input:
        if os.path.isfile(path):
            with open(path, "rb") as f:
                if f.read(4) == b"WLPK":
                    inputs.append(path)
                    continue
        figures, unpacked = open_instance(path)
        keep.append(unpacked)
        selected = choose_prototypes(figures, arguments.figure, arguments.all)
        if arguments.name and len(selected) != 1:
            print("--name gives one mascot a name; pick one with --figure")
            exit(1)
        arguments.renamed = True
        out = tempfile.TemporaryDirectory()
        keep.append(out)
        for figure in selected:
            name = arguments.name or figure["name"]
            print(f"Converting {figure['name']}" + (f" as {name}" if name != figure["name"] else "") + "...")
            converted = convert_prototype(figure, os.path.join(out.name, f"Shimeji.{name}.wlshm"), arguments.name)
            if converted:
                inputs.append(converted)
    arguments.input = inputs
    return keep


# What a Talk behavior is picked from without --talk: the first hint some
# action's name has (petting, talking, waving...)
TALK_HINTS = ("pet", "talk", "speak", "wave", "spinhead", "lookup", "facemouse")


def guess_talk(actions: list[str]) -> str | None:
    for hint in TALK_HINTS:
        found = [a for a in actions if hint in a.lower()]
        if found:
            # "SitPetting" rather than its part "SitPettingAction"
            return sorted(found, key=lambda a: (a.lower().endswith("action"), len(a)))[0]
    return None


# What a sleeping pose must not have: a part that gets up or walks off (Shimeji-ee's
# Sleep often ends sitting or standing, or moves along the floor)
GETS_UP = re.compile(r"stand|sit|stretch|walk|run|dash|jump|wake|getup|climb|fall|chase", re.I)
SLEEP_HINTS = ("sleep", "nap", "doze", "sprawl", "lie", "lay", "rest")


def action_parts(actions: dict, name: str, depth: int = 0) -> list[tuple[str, str]]:
    """The (name, type) of what an action plays, its sequences flattened; a
    Move whose frames have no velocity stays put, so it is not one"""
    action = actions.get(name)
    if not action or depth > 8:
        return [(name, "")]
    if action.get("type") != "Sequence":
        kind = action.get("type", "")
        if kind == "Move" and not any(f.get("velocity_x") or f.get("velocity_y")
                                      for item in action.get("content", []) for f in item.get("frames", [])):
            kind = "Stay"
        return [(name, kind)]
    parts = []
    for item in action.get("content", []):
        if item.get("type") == "ActionReference":
            parts += action_parts(actions, item.get("action_name", ""), depth + 1)
    return parts


def stays_asleep(actions: dict, name: str) -> bool:
    parts = action_parts(actions, name)
    return bool(parts) and not any(GETS_UP.search(n) or t == "Move" for n, t in parts)


def guess_sleep(actions: dict, usable: list[str], sleep: str | None) -> str | None:
    """A pose to sleep in when the Sleep action (sleep) gets up or moves: its
    first part if that lies still, else an action named like sleeping that
    does, the plainest first"""
    if sleep:
        first = action_parts(actions, sleep)[0][0]
        if first in usable and stays_asleep(actions, first):
            return first
    for hint in SLEEP_HINTS:
        found = [a for a in usable if hint in a.lower() and stays_asleep(actions, a)]
        if found:
            return sorted(found, key=lambda a: (actions[a].get("type") == "Sequence", a.lower().endswith("action"), len(a)))[0]
    return None


# What an Answered behavior is picked from without --answered: the first hint
# some action's name has (looking at the user, waving...), one that stays on
# its spot and is not what it talks with
ANSWERED_HINTS = ("facemouse", "wave", "lookup", "watch", "hind", "phone", "cheer", "spinhead", "clean")
MOVES_OFF = re.compile(r"walk|run|dash|jump|climb|fall|chase|throw|drag", re.I)


def plays_frames(actions: dict, name: str) -> bool:
    """Whether an action is drawn: frame animations (Animate, Stay, a Move
    without velocity), and a Look among them at most - Look alone only turns
    the mascot and ends at once (no other Embedded action: they jump, fall...)"""
    parts = action_parts(actions, name)
    return any(t in ("Animate", "Stay") for _, t in parts) and all(
        t in ("Animate", "Stay") or (t == "Embedded" and actions.get(n, {}).get("embedded_type") == "Look")
        for n, t in parts)


def guess_answered(actions: dict, usable: list[str], talk: str | None) -> str | None:
    for hint in ANSWERED_HINTS:
        found = [a for a in usable if hint in a.lower() and a != talk and plays_frames(actions, a)
                 and not any(MOVES_OFF.search(n) for n, _ in action_parts(actions, a))]
        if found:
            return sorted(found, key=lambda a: (a.lower().endswith("action"), len(a)))[0]
    return None


def hidden_behavior(name: str, action: str) -> dict:
    """A behavior never picked at random (frequency 0): the daemon switches to Talk
    while a reply streams, repeats Answered while an answer waits to be read, and
    repeats Asleep while the mascot sleeps"""
    return {"name": name, "action": action, "next_behavior_list": [], "next_behavior_list_count": 0,
            "hidden": True, "condition": None, "is_conditioner": False,
            "next_behavior_list_add": True, "frequency": 0}


def set_talk_sleep(behaviors: dict, definitions: list, assets: set, talk: str | None, sleep: str | None,
                   guess: bool, answered: str | None = None) -> list[str]:
    """Gives behaviors a Talk, an Answered and an Asleep behavior: talk/answered/
    sleep name an action, "none" removes it, "auto" picks one (guess_talk(),
    guess_answered(), guess_sleep()); with guess, a missing one is picked too.
    Returns what it did, one line each"""
    referenced = set()

    def collect(node):
        if isinstance(node, dict):
            if node.get("type") == "Frame":
                referenced.update(i for i in (node.get("image"), node.get("image_right")) if i)
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)

    collect(definitions)
    by_name = {a["name"]: a for a in definitions}
    # Never one the overlay drops (an image missing, see broken_actions())
    broken, _ = broken_actions(by_name, referenced - assets)
    # Inlined actions are anonymous parts of other actions, not something to pick
    actions = [a["name"] for a in definitions if not a["name"].startswith("___") and a["name"] not in broken]
    own = behaviors.setdefault("definitions", [])
    defined = {d.get("name"): d for d in own}
    changes = []

    def named(action):
        found = next((a for a in actions if a.lower() == action.lower()), None)
        if not found:
            raise ValueError(f"no action called '{action}'. Actions: {', '.join(actions)}")
        return found

    def put(behavior, action):
        own[:] = [d for d in own if d.get("name") != behavior]
        if action:
            own.append(hidden_behavior(behavior, action))

    if talk and talk.lower() == "none":
        put("Talk", None)
        changes.append("talks with nothing (it sits)")
    elif talk and talk.lower() != "auto":
        put("Talk", named(talk))
        changes.append(f"talks with {named(talk)}")
    elif talk or (guess and "Talk" not in defined):
        match = guess_talk(actions)
        put("Talk", match)
        changes.append(f"talks with {match} (picked; --talk <action> for another, --talk none for none)" if match
                       else "no action to talk with (it sits); --talk <action> to pick one "
                            "('mascot prototypes poses <name>' shows them)")
    elif guess:
        changes.append("keeps its own Talk")

    talks_with = next((d.get("action") for d in own if d.get("name") == "Talk"), None)
    if answered and answered.lower() == "none":
        put("Answered", None)
        changes.append("waits with an answer sitting")
    elif answered and answered.lower() != "auto":
        put("Answered", named(answered))
        changes.append(f"waits with an answer playing {named(answered)}")
    elif answered or (guess and "Answered" not in defined):
        match = guess_answered(by_name, actions, talks_with)
        put("Answered", match)
        changes.append(f"waits with an answer playing {match} (picked; --answered <action> for another)" if match
                       else "has nothing to wait with an answer, so it sits (--answered <action> to pick one)")
    elif guess:
        changes.append(f"keeps its own Answered ({defined['Answered'].get('action')})")

    own_sleep = defined["Sleep"].get("action") if "Sleep" in defined else None
    if sleep and sleep.lower() == "none":
        put("Asleep", None)
        changes.append("sleeps with its own Sleep" if own_sleep else "has no pose of its own to sleep in")
    elif sleep and sleep.lower() != "auto":
        put("Asleep", named(sleep))
        changes.append(f"sleeps with {named(sleep)}")
    elif sleep or (guess and "Asleep" not in defined):
        lie_down = defined["LieDown"].get("action") if "LieDown" in defined else None
        if own_sleep and stays_asleep(by_name, own_sleep):
            put("Asleep", None)
            changes.append("sleeps with its own Sleep")
        elif not own_sleep and lie_down and stays_asleep(by_name, lie_down):
            put("Asleep", None)
            changes.append("lies down to sleep")
        else:
            match = guess_sleep(by_name, actions, own_sleep)
            put("Asleep", match)
            why = "its own Sleep gets up or moves" if own_sleep else "it has no Sleep"
            if match:
                changes.append(f"sleeps with {match} (picked, as {why}; --sleep <action> for another)")
            elif own_sleep:
                changes.append(f"sleeps with its own Sleep, which gets up or moves; --sleep <action> to pick another "
                               "('mascot prototypes poses <name>' shows them)")
            elif "LieDown" in defined:
                changes.append("lies down to sleep")
            else:
                changes.append("has nothing to sleep with, so it sits (--sleep <action> to pick one)")
    elif guess:
        changes.append(f"keeps its own Asleep ({defined['Asleep'].get('action')})")
    return changes


def wlshm_header(name: str, version: str) -> bytes:
    """A .wlshm's 512 bytes before its tar: WLPK, then the name and version, each a length byte and the text"""
    header = b"WLPK"
    # The name gets up to 255 bytes, the version what the daemon reads (127) and what is left of the 512
    for text, most in ((name, 255), (version, min(127, 512 - 6 - len(name.encode("utf-8")[:255])))):
        data = text.encode("utf-8")[:most]
        header += struct.pack(f"B{len(data)}s", len(data), data)
    return header + b"\x00" * (512 - len(header))


def wlshm_check(header: bytes, members: list) -> None:
    """ValueError unless the pack is safe to unpack, as the daemon checks it (src/protocol/wlshm.c): its name one
    directory name that is not hidden, and only plain files and directories inside it (no "..", no links)"""
    name = header[5:5 + header[4]].decode("utf-8", "replace")
    if not name or name.startswith(".") or "/" in name or "\0" in name:
        raise ValueError(f"the pack's name {name!r} is not a name for a directory")
    for member in members:
        if not (member.isfile() or member.isdir()):
            raise ValueError(f"{member.name} is a link or device; a mascot has only files")
        if not member.name or member.name.startswith("/") or ".." in member.name.split("/"):
            raise ValueError(f"{member.name} would be unpacked outside the mascot's directory")


def wlshm_manifest(path: str) -> dict:
    with open(path, "rb") as f:
        f.seek(512)
        with tarfile.open(fileobj=io.BytesIO(f.read()), mode="r:*") as source:
            return json.load(source.extractfile("manifest.json")) if "manifest.json" in source.getnames() else {}


def wlshm_adjusted(path: str, no_climb: bool, talk: str | None, sleep: str | None = None, name: str | None = None,
                  answered: str | None = None):
    """Copy of a .wlshm with --no-climb/--talk/--sleep/--name applied, as an
    unlinked temporary file. Without --talk/--sleep, a Talk and (when its own
    Sleep gets up or moves) an Asleep behavior are picked, unless it has them;
    "none" adds none (see set_talk_sleep()). The daemon prefers Asleep to Sleep.

    The daemon unpacks whatever fd it is given, so the original file is never touched.
    Returns the file, its manifest and what it does, one line each.
    """
    with open(path, "rb") as f:
        header = f.read(512)
        source = tarfile.open(fileobj=io.BytesIO(f.read()), mode="r:*")

    names = source.getnames()
    wlshm_check(header, source.getmembers())
    manifest = json.load(source.extractfile("manifest.json")) if "manifest.json" in names else {}
    behaviors_name = manifest.get("behaviors", "behaviors.json")
    actions_name = manifest.get("actions", "actions.json")
    for needed in (behaviors_name, actions_name):
        if needed not in names:
            raise ValueError(f"{needed} not found")
    behaviors = json.load(source.extractfile(behaviors_name))
    if name:
        manifest["name"] = f"Shimeji.{name}"
        manifest["display_name"] = name
        header = wlshm_header(manifest["name"], manifest.get("version", "0.0.1"))
        wlshm_check(header, [])

    definitions = json.load(source.extractfile(actions_name))
    assets = {n.removeprefix(manifest.get("assets", "assets") + "/") for n in names}
    changes = set_talk_sleep(behaviors, definitions, assets, talk, sleep, guess=True, answered=answered)

    if no_climb:
        disabled = strip_climbing(behaviors)
        changes.append(f"climbing removed ({len(disabled)} behaviors)" if disabled else "no climbing to remove")

    behaviors_data = json.dumps(behaviors).encode("utf-8")
    manifest_data = json.dumps(manifest).encode("utf-8")
    out = tempfile.TemporaryFile()
    out.write(header)
    # Someone else's pack does not choose the mascot's personality (the daemon leaves it out too)
    if any(m.name.lstrip("./") == "prompt.md" for m in source.getmembers()):
        changes.append("its own personality (prompt.md) left out: give it one with a role (mascot --help)")
    with tarfile.open(fileobj=out, mode="w") as tar:
        for member in source.getmembers():
            if member.name.lstrip("./") == "prompt.md":
                continue
            if member.name == behaviors_name:
                member.size = len(behaviors_data)
                tar.addfile(member, io.BytesIO(behaviors_data))
            elif member.name == "manifest.json" and name:
                member.size = len(manifest_data)
                tar.addfile(member, io.BytesIO(manifest_data))
            else:
                tar.addfile(member, source.extractfile(member) if member.isfile() else None)
    source.close()
    out.seek(0)
    return out, manifest, changes

def chat_is_set_up(config_root: str) -> bool:
    """Whether the bubble has something to chat with: CHAT_COMMAND, the user's own aichat config or Mascot's
    own. A small copy of tools/mascot-guide's status (the bubble's guide), whose path the CLI cannot know"""
    try:
        with open(os.path.join(config_root, "mascotd.conf")) as f:
            for line in f:
                key, _, value = line.partition("=")
                if key.strip() == "chat_command" and value.strip():
                    return True
    except OSError:
        pass
    own = os.environ.get("AICHAT_CONFIG_DIR") or os.path.join(
        os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "aichat")
    return (os.path.isfile(os.path.join(own, "config.yaml"))
            or os.path.isfile(os.path.join(config_root, "aichat", "config.yaml")))


SETUP_HINT = "Chat is not set up yet; run mascot setup (or tap the mascot)."


def roles_dir(config_root: str) -> str | None:
    """Where the bubble's aichat keeps its roles (aichat --info's roles_dir), run as the bubble runs it:
    CHAT_COMMAND, else aichat with the user's own config, else with Mascot's own (see chat_is_set_up())"""
    command = ""
    try:
        with open(os.path.join(config_root, "mascotd.conf")) as f:
            for line in f:
                key, _, value = line.partition("=")
                if key.strip() == "chat_command":
                    command = value.strip()
    except OSError:
        pass
    env = dict(os.environ)
    own = os.environ.get("AICHAT_CONFIG_DIR") or os.path.join(
        os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "aichat")
    if not command and not os.path.isfile(os.path.join(own, "config.yaml")):
        env["AICHAT_CONFIG_DIR"] = os.path.join(config_root, "aichat")
    try:
        info = subprocess.run(["sh", "-c", (command or "aichat") + " --info </dev/null"], env=env,
                              capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    found = re.search(r"^roles_dir\s+(.+)$", info, re.M)
    return found[1].strip() if found else None


def tilde(path: str) -> str:
    """A path as the user would write it, with ~ for the home directory"""
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path.startswith(home + os.sep) else path


def chat_help(config_root: str) -> str:
    """The end of mascot --help: how to start, and the chat's settings, which are otherwise only in the docs"""
    if chat_is_set_up(config_root):
        found = roles_dir(config_root)
        roles = f"a .md file in {tilde(found)}" if found else "a .md file in aichat's roles_dir (aichat --info)"
    else:
        roles = "once the chat is set up (tap a mascot), a .md file in aichat's roles directory"
    return f"""getting started:
  mascot setup              set up the chat (model, language, tools)
  mascot summon Robo        bring Robo onto the screen
  mascot chat               open the chat bubble (or just click a mascot)
  mascot config list        every setting and its value

chat settings (mascot config set KEY VALUE):
  CHAT_TOOLS      what the mascot may look up: time, weather, files, todo,
                  reminders, shell, sleep, system (.tools in the bubble says what each does)
                  e.g. mascot config set CHAT_TOOLS 'time,weather,files'
  CHAT_LANGUAGE   the language it answers in, e.g. Danish
  CHAT_DOTFILES   the hidden files the files tool may read, e.g. '~/.zshrc;~/.config/hypr'
  CHAT_REMARKS    a mascot says something by itself every N to 2N minutes; 0: never
  CHAT_ROLE       a role for every mascot (CHAT_ROLES: one per mascot, 'Robo=my-role;Shimeji=')

roles: {roles} (its name is the role's).
  A role takes the place of the mascot's own personality; .exit role in the bubble brings it back.
  A personality for the mascots without one of their own (Robo has one):
  {tilde(os.path.join(config_root, "prompt.md"))}

in the bubble: .help, .help all, .tools, .roles"""


def setup_handler(arguments: argparse.Namespace) -> int:
    """mascot setup in the terminal (see chatsetup.run_setup)"""
    if not sys.stdin.isatty():
        print("mascot setup asks questions; run it in a terminal.", file=sys.stderr)
        return 1
    root = os.path.expanduser(arguments.config_root or "~/.local/share/mascot")
    conf = arguments.config or os.path.join(root, "mascotd.conf")
    current = conf_options(conf)
    given = []
    for flag, value in (("-s", arguments.socket), ("-c", arguments.config), ("-cr", arguments.config_root)):
        if value:
            given += [flag, value]

    def set_option(key: str, value: str) -> None:
        # Right after installing there is no config yet; mascotd fills in the rest
        if not os.path.exists(conf):
            os.makedirs(os.path.dirname(conf), mode=0o700, exist_ok=True)
            open(conf, "a").close()
        done = subprocess.run([sys.executable, os.path.realpath(sys.argv[0]), *given, "config", "set", key, value],
                              capture_output=True, text=True)
        if done.returncode != 0:
            print(f"Could not set {key}: {(done.stderr or done.stdout).strip()}", file=sys.stderr)

    color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

    def out(line: str) -> None:
        label = line[:7].strip()
        if color and label and not label.startswith(("╭", "│", "╰")):
            line = f"\033[1;36m{line[:7]}\033[0m{line[7:]}"
        print(line, flush=True)

    try:
        import readline  # noqa: F401 - arrow keys edit the answer instead of adding ESC [ D to it
    except ImportError:
        pass
    return run_setup(root, input, read_secret, out, set_option, current, dict(os.environ))


def read_secret(prompt: str) -> str:
    """Like getpass, but one • per character, so a pasted key is seen to land (its length, never the key itself).
    Backspace takes one back, Ctrl+U all; Ctrl+C stops as anywhere else"""
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    mode = termios.tcgetattr(fd)
    mode[3] &= ~(termios.ECHO | termios.ICANON)  # ISIG stays: Ctrl+C is still KeyboardInterrupt
    mode[6][termios.VMIN], mode[6][termios.VTIME] = 1, 0
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    typed = []
    sys.stdout.write(prompt)
    sys.stdout.flush()
    try:
        termios.tcsetattr(fd, termios.TCSAFLUSH, mode)
        while True:
            chunk = os.read(fd, 1024)
            if not chunk:
                raise EOFError
            for ch in decoder.decode(chunk):
                if ch in "\r\n":
                    return "".join(typed)
                if ch in "\x7f\b":
                    if typed:
                        typed.pop()
                        sys.stdout.write("\b \b")
                elif ch == "\x15":
                    sys.stdout.write("\b \b" * len(typed))
                    typed.clear()
                elif ch == "\x04" and not typed:
                    raise EOFError
                elif ch >= " ":
                    typed.append(ch)
                    sys.stdout.write("•")
            sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, saved)
        sys.stdout.write("\n")
        sys.stdout.flush()


class MascotParser(argparse.ArgumentParser):
    """mascot's own parser: its help ends with chat_help(), made only when the help is shown,
    as it asks aichat"""

    def format_help(self) -> str:
        argv = sys.argv[1:]
        root = "~/.local/share/mascot"
        for i, arg in enumerate(argv):
            if arg in ("-cr", "--config-root") and i + 1 < len(argv):
                root = argv[i + 1]
            elif arg.startswith("--config-root="):
                root = arg.split("=", 1)[1]
        return super().format_help() + "\n" + chat_help(os.path.expanduser(root)) + "\n"


def prototype_dir(arguments: argparse.Namespace, path: str) -> tuple[str | None, bool]:
    """The directory of an installed prototype, which the daemon names relative
    to where it loaded it from: PROTOTYPES_LOCATION (<config root>/shimejis by
    default), or the bundled ones next to bin/ (see bundled_shimeji()). And
    whether it is in PROTOTYPES_LOCATION, the only place the daemon reloads from"""
    if os.path.isabs(path):
        return path, True
    root = os.path.expanduser(arguments.config_root or "~/.local/share/mascot")
    stores = [os.path.join(root, "shimejis")]
    try:
        with open(arguments.config or os.path.join(root, "mascotd.conf")) as f:
            for line in f:
                key, _, value = line.partition("=")
                if key.strip() == "prototypes_location" and value.strip():
                    stores.insert(0, os.path.expanduser(value.strip()))
    except OSError:
        pass
    here = os.path.dirname(os.path.realpath(sys.argv[0]))
    stores += [os.path.join(here, "..", "share", "mascot", "prototypes"), os.path.join(here, "..", "prototypes")]
    for i, store in enumerate(stores):
        candidate = os.path.normpath(os.path.join(store, path))
        if os.path.isfile(os.path.join(candidate, "manifest.json")):
            return candidate, i < len(stores) - 2
    return None, False


# The page `mascot prototypes poses` writes: each action as a moving picture,
# what the mascot talks and sleeps with marked, and the command to change it
POSES_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ poses</title>
<style>
:root { --bg: #f6f4f1; --card: #fff; --text: #222; --muted: #6b6560; --line: #e2ddd6; --accent: #b4562d; --good: #2f7d4f; --stage: #ece7e0; }
@media (prefers-color-scheme: dark) { :root { --bg: #1b1917; --card: #262320; --text: #ece7e0; --muted: #a39b92; --line: #3a3530; --accent: #e08a5f; --good: #6cc08f; --stage: #312d29; } }
* { box-sizing: border-box; }
body { margin: 0; padding: 24px 16px 48px; background: var(--bg); color: var(--text); font: 15px/1.45 system-ui, sans-serif; }
header { max-width: 1100px; margin: 0 auto 20px; }
h1 { margin: 0 0 6px; font-size: 24px; }
p { margin: 0 0 10px; color: var(--muted); max-width: 70ch; }
code { font-family: ui-monospace, monospace; font-size: 13px; }
input { width: 100%; max-width: 360px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--card); color: var(--text); font: inherit; }
main { max-width: 1100px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 14px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 10px; display: flex; flex-direction: column; gap: 6px; }
.card.used { border-color: var(--accent); }
.stage { position: relative; height: __H__px; background: var(--stage); border-radius: 8px; overflow: hidden; }
.stage img { position: absolute; image-rendering: auto; }
.name { font-weight: 600; word-break: break-word; }
.tags { display: flex; flex-wrap: wrap; gap: 4px; min-height: 20px; }
.tag { font-size: 12px; padding: 1px 7px; border-radius: 99px; border: 1px solid var(--line); color: var(--muted); }
.tag.use { border-color: var(--accent); color: var(--accent); }
.tag.still { border-color: var(--good); color: var(--good); }
.buttons { display: flex; gap: 6px; }
button { flex: 1; padding: 6px; border: 1px solid var(--line); border-radius: 8px; background: transparent; color: var(--text); font: inherit; font-size: 13px; cursor: pointer; }
button:hover { border-color: var(--accent); }
.done { color: var(--good); }
</style></head><body>
<header>
<h1>__TITLE__</h1>
<p>Each of its actions, moving as the mascot plays it. <b>Talk</b> plays while the chat bubble answers, best one that sits still;
<b>Answered</b> repeats while an answer waits to be read (the bubble was closed while it answered);
<b>Sleep</b> repeats while it is asleep, best one marked <i>lies still</i>. The buttons copy the command that makes it so:</p>
<p><code>mascot prototypes set "__NAME__" --talk &lt;action&gt;</code>, <code>--answered &lt;action&gt;</code> &nbsp;or&nbsp; <code>--sleep &lt;action&gt;</code></p>
<input id="search" type="search" placeholder="Find an action…" autocomplete="off">
</header>
<main id="cards"></main>
<script>
const data = __DATA__;
const cards = document.getElementById("cards");
function copy(text, button) {
  const done = () => { const old = button.textContent; button.textContent = "Copied"; button.classList.add("done");
    setTimeout(() => { button.textContent = old; button.classList.remove("done"); }, 1400); };
  if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, () => prompt("Copy:", text));
  else prompt("Copy:", text);
}
for (const action of data.actions) {
  const card = document.createElement("section");
  card.className = "card" + (action.uses.length ? " used" : "");
  card.dataset.name = action.name.toLowerCase();
  const stage = document.createElement("div");
  stage.className = "stage";
  const img = document.createElement("img");
  stage.append(img);
  let i = 0;
  const show = () => {
    const [image, ax, ay, ticks] = action.frames[i];
    img.src = data.images[image];
    img.style.left = (data.x - ax) + "px";
    img.style.top = (data.y - ay) + "px";
    i = (i + 1) % action.frames.length;
    if (action.frames.length > 1) setTimeout(show, Math.max(1, ticks) * 40);
  };
  show();
  const name = document.createElement("div");
  name.className = "name";
  name.textContent = action.name;
  const tags = document.createElement("div");
  tags.className = "tags";
  for (const use of action.uses) tags.insertAdjacentHTML("beforeend", `<span class="tag use"></span>`), tags.lastChild.textContent = use;
  if (action.still) tags.insertAdjacentHTML("beforeend", `<span class="tag still">lies still</span>`);
  const buttons = document.createElement("div");
  buttons.className = "buttons";
  for (const what of ["talk", "answered", "sleep"]) {
    const button = document.createElement("button");
    button.textContent = "Use for " + what;
    button.title = `mascot prototypes set "${data.name}" --${what} ${action.name}`;
    button.onclick = () => copy(button.title, button);
    buttons.append(button);
  }
  card.append(stage, name, tags, buttons);
  cards.append(card);
}
document.getElementById("search").oninput = event => {
  const words = event.target.value.toLowerCase().split(/\\s+/).filter(w => w);
  for (const card of cards.children) card.hidden = !words.every(w => card.dataset.name.includes(w));
};
</script></body></html>
"""


def show_poses(arguments: argparse.Namespace):
    """mascot prototypes poses: writes a page with the mascot's actions as
    moving pictures (its images are QOI, which browsers cannot show, so they
    go in as PNG) and opens it"""
    prototype = prototype_named(arguments.name)
    path, _ = prototype_dir(arguments, prototype.path)
    if not path:
        print(f"Cannot find where {prototype.display_name} is kept ({prototype.path})")
        exit(1)
    with open(os.path.join(path, "manifest.json")) as f:
        manifest = json.load(f)
    with open(os.path.join(path, manifest.get("actions", "actions.json"))) as f:
        definitions = json.load(f)
    with open(os.path.join(path, manifest.get("behaviors", "behaviors.json"))) as f:
        behaviors = {d.get("name"): d.get("action") for d in json.load(f).get("definitions", [])}
    assets_dir = os.path.join(path, manifest.get("assets", "assets"))
    by_name = {a["name"]: a for a in definitions}

    def frames_of(name, depth=0):
        action = by_name.get(name)
        if not action or depth > 8:
            return []
        if action.get("type") == "Sequence":
            return [f for item in action.get("content", []) if item.get("type") == "ActionReference"
                    for f in frames_of(item.get("action_name", ""), depth + 1)]
        animation = next((item for item in action.get("content", []) if item.get("type") == "Animation"), None)
        return [(f["image"], f.get("image_anchor_x", 0), f.get("image_anchor_y", 0), f.get("duration", 1))
                for f in (animation or {}).get("frames", []) if f.get("image")]

    # What it plays now: Talk, and the first of these it sleeps with (see mascot_sleep() in mascotd)
    uses = {}
    if behaviors.get("Talk"):
        uses.setdefault(behaviors["Talk"], []).append("Talk")
    if behaviors.get("Answered"):
        uses.setdefault(behaviors["Answered"], []).append("Answered")
    sleeping = next((b for b in ("Asleep", "Sleep", "LieDown", "SitDown") if behaviors.get(b)), None)
    if sleeping:
        uses.setdefault(behaviors[sleeping], []).append("Sleep")

    images, actions = {}, []
    for name in sorted(by_name, key=str.lower):
        if name.startswith("___"):
            continue
        frames = frames_of(name)
        for image in {f[0] for f in frames} - images.keys():
            try:
                with Image.open(os.path.join(assets_dir, image)) as picture:
                    out = io.BytesIO()
                    picture.save(out, "PNG")
                images[image] = "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()
            except OSError:
                images[image] = None  # missing or unreadable: the daemon drops such an action too
        frames = [f for f in frames if images.get(f[0])]
        if frames:
            actions.append({"name": name, "frames": frames, "uses": uses.get(name, []),
                            # As guess_sleep() would pick: named like sleeping or lying, and lies still
                            "still": any(h in name.lower() for h in SLEEP_HINTS) and stays_asleep(by_name, name)})
    if not actions:
        print(f"{prototype.display_name} has no actions with pictures")
        exit(1)
    # In use first; each picture with its anchor on one spot, its feet on the floor
    actions.sort(key=lambda a: not a["uses"])
    left = max(f[1] for a in actions for f in a["frames"])
    top = max(f[2] for a in actions for f in a["frames"])
    data = {"name": prototype.display_name, "images": {k: v for k, v in images.items() if v}, "actions": actions,
            "x": max(left, 90) + 10, "y": top + 6}
    page = (POSES_PAGE.replace("__TITLE__", html.escape(prototype.display_name))
            .replace("__NAME__", html.escape(prototype.display_name)).replace("__H__", str(top + 16))
            .replace("__DATA__", json.dumps(data).replace("</", "<\\/")))
    out_dir = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    out_path = os.path.join(out_dir, "mascot-poses-" + re.sub(r"[^A-Za-z0-9_-]+", "-", prototype.display_name) + ".html")
    with open(out_path, "w") as f:
        f.write(page)
    print(f"{prototype.display_name}: {len(actions)} actions in {out_path}")
    if not arguments.no_open:
        subprocess.Popen(["xdg-open", out_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def prototype_named(name: str):
    """The installed prototype by its exact name (any letter case):
    prototype_find() would take the closest one, maybe another mascot"""
    wanted = name.lower().removeprefix("shimeji.")
    found = [p for p in prototypes.values()
             if wanted in (p.display_name.lower(), p.name.lower().removeprefix("shimeji."))]
    if not found:
        print(f"No mascot called \"{name}\". Mascots: {', '.join(p.display_name for p in prototypes.values())}")
        exit(1)
    return found[0]


def set_prototype(arguments: argparse.Namespace, client: Client):
    """mascot prototypes set: changes the Talk, Answered and Asleep behaviors of
    an installed mascot in its own directory, and reloads it"""
    if not arguments.talk and not arguments.sleep and not arguments.answered:
        print("Say what to change: --talk, --answered and/or --sleep <action> ('auto' picks one)")
        exit(1)
    prototype = prototype_named(arguments.name)
    path, reloadable = prototype_dir(arguments, prototype.path)
    if not path:
        print(f"Cannot find where {prototype.display_name} is kept ({prototype.path})")
        exit(1)
    try:
        with open(os.path.join(path, "manifest.json")) as f:
            manifest = json.load(f)
        behaviors_path = os.path.join(path, manifest.get("behaviors", "behaviors.json"))
        with open(behaviors_path) as f:
            behaviors = json.load(f)
        with open(os.path.join(path, manifest.get("actions", "actions.json"))) as f:
            definitions = json.load(f)
        assets_dir = os.path.join(path, manifest.get("assets", "assets"))
        assets = {os.path.relpath(os.path.join(root, n), assets_dir) for root, _, files in os.walk(assets_dir) for n in files}
        changes = set_talk_sleep(behaviors, definitions, assets, arguments.talk, arguments.sleep, guess=False,
                                 answered=arguments.answered)
        # Written whole first, so a failure never leaves half a file
        with tempfile.NamedTemporaryFile("w", dir=path, delete=False, suffix=".tmp") as f:
            json.dump(behaviors, f, indent=4, ensure_ascii=False)
            f.write("\n")
        os.replace(f.name, behaviors_path)
    except ValueError as e:
        print(f"Not changed: {e}")
        exit(1)
    except OSError as e:
        print(f"Cannot change {prototype.display_name} in {path}: {e.strerror}")
        exit(1)
    print(f"{prototype.display_name}: " + "; ".join(changes))
    if reloadable:
        # By the path the daemon knows it by
        client.queue_packet(ReloadPrototype(prototype.path))
    else:
        print(f"It is a bundled mascot: this takes effect when Mascot starts next, and the next install of "
              f"Mascot replaces it ({path})")


def remove_prototype(arguments: argparse.Namespace, client: Client):
    """mascot prototypes remove: sends an installed mascot's mascots away,
    deletes its directory and has the daemon forget it. Only one of your own
    (PROTOTYPES_LOCATION): the bundled ones come with Mascot"""
    prototype = prototype_named(arguments.name)
    path, removable = prototype_dir(arguments, prototype.path)
    if not path:
        print(f"Cannot find where {prototype.display_name} is kept ({prototype.path})")
        exit(1)
    if not removable:
        print(f"{prototype.display_name} comes with Mascot and cannot be removed ({path})")
        exit(1)
    if not arguments.yes:
        answer = input(f"Remove {prototype.display_name} and delete {path}? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Not removed")
            exit(1)
    away = [m for m in list(mascots.values()) if m.prototype is prototype]
    for mascot in away:
        mascot.dismiss()
    try:
        shutil.rmtree(path)
    except OSError as e:
        print(f"Cannot delete {path}: {e.strerror}")
        exit(1)
    # By the path the daemon knows it by; it is gone, so the daemon forgets it
    client.queue_packet(ReloadPrototype(prototype.path))
    print(f"Removed {prototype.display_name}" + (f" (sent {len(away)} away)" if away else ""))


def prototypes_handler(arguments: argparse.Namespace, client: Client, parser):
    match arguments.action:
        case "list":
            print("Available prototypes:")
            for id, prototype in prototypes.items():
                if not arguments.detailed:
                    print(f"{id & 0x00FFFFFF}: {prototype.display_name}")
                else:
                    header = f"[Prototype \"{prototype.display_name}\" (aka \"{prototype.name}\")]"
                    padding_left = round(shutil.get_terminal_size().columns / 4  - len(header) / 2)
                    padding_right = round(shutil.get_terminal_size().columns / 4  - len(header) / 2)
                    print(f"{'-' * padding_left}{header}{'-' * padding_right}")
                    print(f"Id: {prototype.id & 0x00FFFFFF}")
                    print(f"Name: {prototype.name}")
                    print(f"Display name: {prototype.display_name}")
                    print(f"Author: {prototype.author}")
                    print(f"Format version: {prototype.version}")
                    print(f"Prototype store path: {prototype.path}")
                    print("Actions:")
                    for action in prototype.actions:
                        print(f"  - {action}")
                    print("Behaviors:")
                    for behavior in prototype.behaviors:
                        print(f"  - {behavior}")
                    print()
                    print(f"Object id: {id}")
                    header = '[END]'
                    padding_left = round(shutil.get_terminal_size().columns / 4  - len(header) / 2)
                    padding_right = round(shutil.get_terminal_size().columns / 4  - len(header) / 2)
                    print(f"{'-' * padding_left}{header}{'-' * padding_right}")
                    print()

        case "info":
            protos_selected = set([])
            for name in arguments.name or []:
                proto = prototype_find(name)
                if proto:
                    protos_selected.add(proto)
                else:
                    print(f"Unknown prototype: {name}", file=sys.stderr)
            prototype: Prototype
            for prototype in protos_selected:
                header = f"[Prototype \"{prototype.display_name}\" (aka \"{prototype.name}\")]"
                padding_left = round(shutil.get_terminal_size().columns / 4  - len(header) / 2)
                padding_right = round(shutil.get_terminal_size().columns / 4  - len(header) / 2)
                print(f"{'-' * padding_left}{header}{'-' * padding_right}")
                print(f"Id: {prototype.id & 0x00FFFFFF}")
                print(f"Name: {prototype.name}")
                print(f"Display name: {prototype.display_name}")
                print(f"Author: {prototype.author}")
                print(f"Format version: {prototype.version}")
                print(f"Prototype store path: {prototype.path}")
                print("Actions:")
                for action in prototype.actions:
                    print(f"  - {action}")
                print("Behaviors:")
                for behavior in prototype.behaviors:
                    print(f"  - {behavior}")
                print()
                print(f"Object id: {prototype.id}")
                header = '[END]'
                padding_left = round(shutil.get_terminal_size().columns / 4  - len(header) / 2)
                padding_right = round(shutil.get_terminal_size().columns / 4  - len(header) / 2)
                print(f"{'-' * padding_left}{header}{'-' * padding_right}")
                print()

        case "reload":
            for path in arguments.path or []:
                if not path: continue
                packet = ReloadPrototype(path)
                client.queue_packet(packet)

        case "reload-all":
            packet = ReloadPrototype("")
            client.queue_packet(packet)

        case "set":
            set_prototype(arguments, client)

        case "remove":
            remove_prototype(arguments, client)

        case "poses":
            show_poses(arguments)

        case "export":
            is_dir = os.path.isdir(arguments.output[0])
            if not is_dir and len(arguments.name) != len(arguments.output):
                print("ERROR: Count of output files should be equal to the number of inputs or output should be a directory")
                exit(1)

            files = []
            if not is_dir:
                for out in arguments.output:
                    if os.path.exists(out) and not arguments.force:
                        print(f"ERROR: File '{out}' already exists")
                        exit(1)
                    try:
                        fileno = os.open(out, os.O_WRONLY | os.O_CREAT | (os.O_EXCL if not arguments.force else os.O_TRUNC))
                    except OSError as E:
                        print(f"ERROR: Failed to open file '{out}' for writing: {E}")
                        exit(1)
                    files.append(fileno)
            else:
                for name in arguments.name:
                    new_name = f"{arguments.output[0]}/"+f"{name}.wlshm".replace(" ", "_").replace("/", "_")
                    if os.path.exists(new_name) and not arguments.force:
                        print(f"ERROR: File '{new_name}' already exists")
                        exit(1)
                    try:
                        fileno = os.open(new_name, os.O_WRONLY | os.O_CREAT | (os.O_EXCL if not arguments.force else os.O_TRUNC))
                    except OSError as E:
                        print(f"ERROR: Failed to open file '{new_name}' for writing: {E}")
                        exit(1)
                    files.append(fileno)

            selected_prototypes = []
            for name in arguments.name:
                if not name:
                    print("WARNING: Empty prototype name")
                else:
                    prot = prototype_find(name)
                    if not prot:
                        print(f"ERROR: Prototype '{name}' not found")
                    selected_prototypes.append(prot)

            def failed(client: Client, packet: ExportFailed):
                export = exports.get(packet.object_id)
                if export:
                    logger.error(f"Failed to export prototype '{export.prototype.name}': {packet.error_code}")
                    os.close(export.export_fd)
                    exports.pop(export.id, None)
                    objects.pop(export.id, None)

            def success(client: Client, packet: ExportFinished):
                export = exports.get(packet.object_id)
                if export:
                    logger.info(f"Successfully exported prototype '{export.prototype.name}'")
                    os.close(export.export_fd)
                    exports.pop(export.id, None)
                    objects.pop(export.id, None)

            client.register_callback(ExportFailed, failed)
            client.register_callback(ExportFinished, success)

            for i, prototype in enumerate(selected_prototypes):
                Export(files[i], prototype, client.socket)

            client.dispatch_events(until=lambda: len(exports) == 0)

        case "import":

            def failed(client: Client, packet: ImportFailed):
                import_object = imports.get(packet.object_id)
                if not import_object:
                    logger.error(f"Failed to import prototype referenced by unknown id {packet.object_id}: {packet.error_code}")
                    return

                errors = {
                    0: "Unknown error",
                    1: "Invalid file format",
                    2: "Invalid mascot version",
                    3: "Referenced prototype already exists. Use -f to overwrite",
                    4: "File referenced by fd is not valid TAR file",
                    5: "Invalid mascot version",
                    6: "FD points not to a file",
                    7: "FD opened in invalid mode"
                }

                label = getattr(import_object, "label", f"id {packet.object_id}")
                if packet.error_code == 3:
                    print(f"You already have {label}: use -f to replace it, or --name to keep both")
                else:
                    logger.error(f"Failed to import {label}: {errors.get(packet.error_code, 'Unknown error')}")
                imports.pop(packet.object_id, None)
                objects.pop(packet.object_id, None)

            def finished(client: Client, packet: ImportFinished):
                import_object = imports.get(packet.object_id)
                if import_object:
                    print(f"Imported {getattr(import_object, 'label', f'id {packet.object_id}')}: "
                          + "; ".join(getattr(import_object, "changes", [])))
                    rpacket = ReloadPrototype(packet.relative_path)
                    client.queue_packet(rpacket)

                imports.pop(packet.object_id, None)
                objects.pop(packet.object_id, None)


            client.register_callback(ImportFinished, finished)
            client.register_callback(ImportFailed, failed)

            # Kept open until the daemon is done with them
            adjusted = []
            # A pack's mascots were renamed when converted, see converted_for_import()
            rename = None if getattr(arguments, "renamed", False) else arguments.name
            if rename and len(arguments.input) != 1:
                logger.error("--name gives one mascot a name; import one file at a time")
                exit(1)
            for input_file in arguments.input:
                if not os.path.exists(input_file):
                    logger.error(f"File '{input_file}' does not exist")
                    exit(1)
                with open(input_file, "rb") as f:
                    if f.read(4) != b'WLPK':
                        logger.warning(f"File '{input_file}' is not a valid mascot prototype, please first convert it to a mascot prototype using the convert command (mascot convert)")
                        continue
                try:
                    copy, manifest, changes = wlshm_adjusted(input_file, arguments.no_climb, arguments.talk,
                                                             arguments.sleep, rename, arguments.answered)
                except (tarfile.TarError, ValueError, KeyError) as e:
                    logger.error(f"Could not prepare '{input_file}': {e}")
                    continue

                # The same name as a mascot you have: a different one (another
                # pack's "Red") is never replaced, the same one only with -f
                display = manifest.get("display_name") or manifest.get("name", "").removeprefix("Shimeji.")
                internal = manifest.get("name")
                other = next((p for p in prototypes.values() if p.name != internal
                              and (p.display_name or "").lower() == display.lower()), None)
                if other:
                    print(f"You already have another mascot called {display} ({other.name}): "
                          f"give this one another name with --name")
                    copy.close()
                    continue

                adjusted.append(copy)
                imported = Import(copy.fileno(), arguments.force, client.socket)
                imported.label = display
                imported.changes = changes


            client.dispatch_events(until=lambda: len(imports) == 0)
            for copy in adjusted:
                copy.close()

        case _:
            parser.print_help()
            exit(1)

def mascot_handler(arguments: argparse.Namespace, client: Client, parser):
    global active_selection
    data = {"mascot__": None}
    match arguments.action:
        case "summon":
            prototype = prototype_find(arguments.name)
            if prototype is None:
                logger.error(f"Prototype '{arguments.name}' not found")
                exit(1)

            envs = []
            envids = [int(x) for x in arguments.environment or [] if x.isdigit()]
            for envid in envids:
                if envid in environments:
                    envs.append(environments[envid])

            if arguments.position is not None and (arguments.x is not None or arguments.y is not None):
                logger.error("--position cannot be combined with -x or -y")
                exit(1)

            if not arguments.select:
                if arguments.position is None:
                    xpos = arguments.x if arguments.x is not None else -1
                    ypos = arguments.y if arguments.y is not None else 128
                else:
                    xpos, ypos = arguments.position

                random_env: Environment = random.choice(envs) if envs else random.choice(list(environments.values()))
                if xpos == -1:
                    xpos = 64 + random.randint(0, random_env.width - 128)
                # Nowhere in particular: the figure appears on the floor, if it can (Robo peeks out of a hole)
                behavior = arguments.behavior or ("Appear" if arguments.position is None and arguments.y is None else "")

                packet = Spawn(prototype.id, random_env.id, xpos, ypos, behavior)
                client.queue_packet(packet)
                if not chat_is_set_up(os.path.expanduser(arguments.config_root or "~/.local/share/mascot")):
                    print(SETUP_HINT, file=sys.stderr)

            else:
                selection = Selection(envs, client.socket)
                active_selection = selection
                def selected2(packet: SelectionDone):
                    global active_selection
                    xpos, ypos = packet.x, packet.y
                    env = environments.get(packet.environment_id)
                    if env is None:
                        logger.error(f"Environment {packet.environment_id} not found")
                        exit(1)

                    spawn_packet = Spawn(prototype.id, env.id, xpos, ypos, arguments.behavior)
                    client.queue_packet(spawn_packet)
                    active_selection = None
                    if not chat_is_set_up(os.path.expanduser(arguments.config_root or "~/.local/share/mascot")):
                        print(SETUP_HINT, file=sys.stderr)

                def cancelled2(packet: SelectionCancelled):
                    global active_selection
                    active_selection = None
                    logger.info(f"Selection cancelled")

                selection.selected = selected2
                selection.cancelled = cancelled2

                print(f"Using \"{prototype.name}\" prototype. Select spot to spawn new mascot.")
                try:
                    client.dispatch_events(until=lambda: active_selection != selection)
                except KeyboardInterrupt:
                    selection.cancel()

        case "dismiss":
            envs = []
            envids = [int(x) for x in arguments.environment or [] if x.isdigit()]
            for envid in envids:
                if envid in environments:
                    envs.append(environments[envid])

            mascots_to_dismiss: list[Mascot] = []

            if arguments.select or arguments.id is None:
                selection = Selection(envs, client.socket)
                active_selection = selection
                def selected(packet: SelectionDone):
                    global active_selection
                    if packet.mascot_id != 0:
                        mascot = mascots.get(packet.mascot_id)
                        if mascot is None:
                            logger.error(f"Failed to get mascot with id {packet.mascot_id}")
                        else:
                            mascots_to_dismiss.append(mascot)
                    if active_selection == selection:
                        active_selection = None

                def cancelled(packet: SelectionCancelled):
                    global active_selection
                    if active_selection == selection:
                        active_selection = None
                    logger.info(f"Selection cancelled")

                selection.selected = selected
                selection.cancelled = cancelled

                print(f"Select mascot to dismiss.")

                try:
                    client.dispatch_events(until=lambda: active_selection != selection)
                except KeyboardInterrupt:
                    selection.cancel()
            else:
                if not arguments.id.isnumeric():
                    print(f"Provided ID is not a number")
                    exit(1)

                mascot = mascot_by_id(arguments.id)
                if not mascot:
                    print(f"Mascot with ID {arguments.id} not found")
                    exit(1)

                else:
                    mascots_to_dismiss = [mascot]

            if arguments.all:
                for mascot in mascots.values():
                    if (mascot.environment in envs or not len(envs)) and mascot not in mascots_to_dismiss:
                        if not arguments.filter_same_type or (arguments.filter_same_type and mascot.prototype == mascots_to_dismiss[0].prototype):
                            mascots_to_dismiss.append(mascot)

            for i, mascot in enumerate(mascots_to_dismiss):
                if i == 0 and arguments.filter_other:
                    continue

                mascot.dismiss()

        case "info":
            mascot = None
            if arguments.id is None:
                selection = Selection([], client.socket)
                active_selection = selection

                def selected(packet: SelectionDone):
                    global active_selection
                    data["mascot__"] = mascots.get(packet.mascot_id)
                    active_selection = None

                def cancelled(packet: SelectionCancelled):
                    global active_selection
                    print("Selection cancelled")
                    active_selection = None

                selection.selected = selected
                selection.cancelled = cancelled

                print(f"Select mascot to get information about.")

                client.dispatch_events(until=lambda: active_selection is None)
                mascot = data["mascot__"]
            else:
                if not arguments.id.isdigit():
                    print("Invalid ID")
                    exit(1)
                mascot = mascot_by_id(arguments.id)

            if not mascot:
                print("Mascot not found")
                exit(1)

            print(mascot)
            packet = MascotGetInfo(mascot.id)
            client.queue_packet(packet)

            def got_mascot_info(client: Client, packet: MascotInfo):
                prototype = prototypes.get(packet.prototype_id)
                mascot = mascots.get(packet.object_id)
                environment = environments.get(packet.environment_id)
                if not prototype:
                    print("Prototype not found")
                    exit(1)
                if not mascot:
                    print("Mascot not found")
                    exit(1)
                print(f"Mascot id {packet.object_id} (Type {prototype.name}:")
                print(f"Environment: {packet.environment_id}")
                print(f"Current state: {packet.current_state}")
                print(f"Current action: {packet.current_action_name.decode()}")
                print(f"Current action index: {packet.current_action_index}")
                print(f"Current behavior: {packet.current_behavior_name.decode()}")
                print(f"Affordance: {packet.current_affordance_name.decode()}")
                print("Action stack:")
                for action_name, action_index in packet.actions:
                    print(f"  {action_name.decode()}, stored index: {action_index}")
                print("Behavior pool:")
                for behavior_name, frequency in packet.behaviors:
                    print(f"  {behavior_name.decode()}, frequency: {frequency}")

                print(f"Position: {packet.variables[0].value}, {packet.variables[1].value}")
                # print(f"Target: {packet.variables[2].value}, {packet.variables[3].value}")
                # print(f"Gravity: {packet.variables[4].value}")
                # print(f"Looking Right: {packet.variables[5].value}")
                # print(f"Air Drag: {packet.variables[6].value}, {packet.variables[7].value}")
                # print(f"Velocity: {packet.variables[8].value}, {packet.variables[9].value}")
                # print(f"Foot X: {packet.variables[15].value}")
                # print(f"Foot DX: {packet.variables[16].value}")
                print(f"IE Offset: {packet.variables[22].value}, {packet.variables[23].value}")
                exit(0)

            client.register_callback(MascotInfo, got_mascot_info)
            client.dispatch_events()

        case "set-behavior":
            mascot = None
            if arguments.id is None:
                selection = Selection([], client.socket)
                active_selection = selection

                def selected(packet: SelectionDone):
                    global active_selection
                    data["mascot__"] = mascots.get(packet.mascot_id)
                    active_selection = None

                def cancelled(packet: SelectionCancelled):
                    global active_selection
                    print("Selection cancelled")
                    active_selection = None

                selection.selected = selected
                selection.cancelled = cancelled

                print(f"Select mascot to set behavior for.")
                client.dispatch_events(until=lambda: active_selection is None)
                mascot = data["mascot__"]
            else:
                if not arguments.id.isdigit():
                    print("Invalid ID")
                    exit(1)
                mascot = mascot_by_id(arguments.id)

            if not mascot:
                print("Mascot not found")
                exit(1)

            packet = ApplyBehavior(mascot.id, arguments.behavior_name)
            client.queue_packet(packet)

        case _:
            parser.print_help()
            exit(1)


def environment_handler(arguments: argparse.Namespace, client: Client, parser):
    global active_selection
    match arguments.action:
        case "list":
            for environment in environments.values():
                print(environment)
        case "close":
            if not arguments.id:
                selection = Selection([], client.socket)
                active_selection = selection

                def selected(packet: SelectionDone):
                    global active_selection
                    environment = environments.get(packet.environment_id)
                    if environment is None:
                        print("Invalid environment!")
                        exit(1)

                    environment.close()
                    print(f"Closing environment {environment.id}")
                    active_selection = None

                def cancelled(packet: SelectionCancelled):
                    global active_selection
                    print("Selection cancelled")
                    active_selection = None

                selection.selected = selected
                selection.cancelled = cancelled

                print("Select screen to close. (Closes overlay on that screen)")
                client.dispatch_events(until=lambda: active_selection == None)
            else:
                environment = environments.get(arguments.id)
                if environment is None:
                    print("Invalid environment!")
                    exit(1)

                environment.close()
                print(f"Closing environment {environment.id}")

        case "info":
            returndict = {"env": None}
            if arguments.id is None:
                selection = Selection([], client.socket)
                active_selection = selection

                def selected(packet: SelectionDone):
                    global active_selection
                    environment = environments.get(packet.environment_id)
                    if environment is None:
                        print("Invalid environment!")
                        exit(1)

                    returndict["env"] = environment
                    active_selection = None

                def cancelled(packet: SelectionCancelled):
                    global active_selection
                    active_selection = None

                selection.selected = selected
                selection.cancelled = cancelled

                print("Select screen to get info about.")
                client.dispatch_events(until=lambda: active_selection == None)
            else:
                environment = environments.get(arguments.id)
                if environment is None:
                    print("Invalid environment id!")
                    exit(1)

                returndict["env"] = environment

            environment = returndict["env"]
            if environment is None:
                print("No environment was selected.")
                exit(1)

            print(f"Environment#{environment.id}")
            print(f"Name: {environment.name}")
            print(f"Description: {environment.description}")
            print(f"Compositor position: {environment.x}, {environment.y}")
            print(f"Size: {environment.width}x{environment.height}")
            print(f"Scale: {environment.scale}")
            print("Referenced mascots:")
            for id, mascot in environment.mascots.items():
                print(f" - {mascot.prototype.display_name}#{mascot.id} (aka {mascot.prototype.name})")

        case _:
            parser.print_help()
            exit(1)


# What mascotd accepts for each key (see config_set_by_key() in config.c,
# which takes e.g. an unknown policy or "maybe" for false without a word)
CONFIG_BOOLEANS = {"BREEDING", "DRAGGING", "WINDOW_INTERACTIONS", "WINDOW_THROWING", "CURSOR_POSITION",
                   "ALLOW_THROWING_MULTIHEAD", "ALLOW_DRAGGING_MULTIHEAD", "UNIFIED_OUTPUTS", "DISMISS_ANIMATIONS",
                   "AFFORDANCES", "TABLETS_ENABLED", "CHAT_ENABLED", "BUBBLE_ENABLED"}
CONFIG_CHOICES = {
    "WINDOW_THROW_POLICY": ["none", "stop_at_borders", "bounce_at_borders", "looping", "close", "minimize",
                            "keep_offscreen"],
    "WLR_SHELL_LAYER": ["background", "bottom", "top", "overlay"],
}
CONFIG_CHAT_TOOLS = ["time", "weather", "files", "todo", "reminders", "shell", "sleep", "system"]

def config_value_problem(key, value):
    """None if mascotd would take value for key, else why not"""
    if "\n" in value or "\r" in value:
        return "the value cannot span lines"
    if key in CONFIG_BOOLEANS:
        if value.lower() not in ["true", "yes", "on", "1", "false", "no", "off", "0"]:
            return "use true or false"
    elif key in CONFIG_CHOICES:
        if value.lower() not in CONFIG_CHOICES[key]:
            return "use one of " + ", ".join(CONFIG_CHOICES[key])
    elif key in ("POINTER_LEFT_BUTTON", "POINTER_RIGHT_BUTTON", "POINTER_MIDDLE_BUTTON") or key.startswith("ON_TOOL_"):
        if not re.fullmatch(r"-1|[0-4]", value):
            return "use a button value from 0 to 4, or -1 for the default"
    elif key in ("MASCOT_LIMIT", "INTERPOLATION_FRAMERATE", "CHAT_REMARKS", "CHAT_MEMORY"):
        if not re.fullmatch(r"-?\d+", value) or (key.startswith("CHAT_") and int(value) < 0):
            return "use a whole number" + (" of 0 or more" if key.startswith("CHAT_") else "")
    elif key in ("OPACITY", "MASCOT_SCALE"):
        try:
            float(value)
        except ValueError:
            return "use a number, e.g. " + ("0.8" if key == "OPACITY" else "1.5")
    elif key == "CHAT_TOOLS":
        unknown = [t.strip() for t in value.split(",") if t.strip() and t.strip().lower() not in CONFIG_CHAT_TOOLS]
        if unknown:
            return f"unknown tool {', '.join(unknown)} - use " + ", ".join(CONFIG_CHAT_TOOLS)
    return None


def config_handler(arguments: argparse.Namespace, client: Client, parser):
    name_cast = {
        "BREEDING": "Multiplication",
        "DRAGGING": "Dragging",
        "WINDOW_INTERACTIONS": "Window Interactions",
        "WINDOW_THROWING": "Window Throwing",
        "WINDOW_THROW_POLICY": "Window Throw Policy",
        "CURSOR_POSITION": "Cursor Position",
        "MASCOT_LIMIT": "Mascot Limit",
        "ALLOW_THROWING_MULTIHEAD": "Allow Throwing Multihead",
        "ALLOW_DRAGGING_MULTIHEAD": "Allow Dragging Multihead",
        "UNIFIED_OUTPUTS": "Unified Outputs",
        "DISMISS_ANIMATIONS": "Dismiss Animations",
        "AFFORDANCES": "Affordances",
        "INTERPOLATION_FRAMERATE": "Interpolation Framerate",
        "WLR_SHELL_LAYER": "Overlay layer",
        "TABLETS_ENABLED": "Tablets Enabled",
        "POINTER_LEFT_BUTTON": "Left Button",
        "POINTER_RIGHT_BUTTON": "Right Button",
        "POINTER_MIDDLE_BUTTON": "Middle Button",
        "ON_TOOL_PEN": "On Tool Pen Button",
        "ON_TOOL_ERASER": "On Tool Eraser Button",
        "ON_TOOL_BRUSH": "On Tool Brush Button",
        "ON_TOOL_PENCIL": "On Tool Pencil Button",
        "ON_TOOL_AIRBRUSH": "On Tool Airbrush Button",
        "ON_TOOL_FINGER": "On Tool Finger Button",
        "ON_TOOL_LENS": "On Tool Lens Button",
        "ON_TOOL_MOUSE": "On Tool Mouse Button",
        "ON_TOOL_BUTTON1": "On Tool Button 1",
        "ON_TOOL_BUTTON2": "On Tool Button 2",
        "ON_TOOL_BUTTON3": "On Tool Button 3",
        "OPACITY": "Opacity",
        "MASCOT_SCALE": "Scaling",
        "CHAT_ENABLED": "Chat Enabled",
        "CHAT_COMMAND": "Chat Command",
        "CHAT_ROLE": "Chat Role",
        "CHAT_ROLES": "Chat Roles",
        "CHAT_REMARKS": "Chat Remarks",
        "CHAT_MEMORY": "Chat Memory",
        "CHAT_TOOLS": "Chat Tools",
        "CHAT_DOTFILES": "Chat Dotfiles",
        "CHAT_LANGUAGE": "Chat Language",
        "BUBBLE_ENABLED": "Bubble Enabled",
        "BUBBLE_COMMAND": "Bubble Command"
    }
    starttime = time.time()
    wait_until_null_null = False

    def received_config_key(client: Client, packet: ConfigKey):
        if len(packet.key) == 0:
            exit(0)

        key = name_cast.get(packet.key, packet.key)

        print(f"  - {key} ({packet.key}) = {packet.value}")
        if not wait_until_null_null:
            exit(0)

    client.register_callback(ConfigKey, received_config_key)

    match arguments.subcommand:
        case "get":
            packet = GetConfigKey(arguments.key)
            client.queue_packet(packet)
            client.dispatch_events(until=lambda: time.time() - starttime > 5)
            print("Timeout.")
        case "set":
            if arguments.key not in name_cast:
                print(f"Unknown key: {arguments.key}\nAvailable keys:")
                for key in name_cast:
                    print(f"  - {key}")
                exit(1)
            problem = config_value_problem(arguments.key, arguments.value.strip())
            if problem:
                print(f"Not set: {problem}")
                exit(1)
            packet = SetConfigKey(arguments.key, arguments.value.strip())
            client.queue_packet(packet)
            client.dispatch_events(until=lambda: time.time() - starttime > 5)
            print("Timeout.")
        case "list":
            print("Config:")
            wait_until_null_null = True
            packet = ListConfigKeys()
            client.queue_packet(packet)
            client.dispatch_events(until=lambda: time.time() - starttime > 5)
            print("Timeout.")
        case _:
            parser.print_help()
            exit(1)

def local_config_handler(arguments: argparse.Namespace, parser):
    name_cast = {
        "BREEDING": "breeding",
        "DRAGGING": "dragging",
        "WINDOW_INTERACTIONS": "ie_interactions",
        "WINDOW_THROWING": "ie_throwing",
        "WINDOW_THROW_POLICY": "ie_throw_policy",
        "CURSOR_POSITION": "cursor_data",
        "MASCOT_LIMIT": "mascot_limit",
        "ALLOW_THROWING_MULTIHEAD": "allow_throwing_multihead",
        "ALLOW_DRAGGING_MULTIHEAD": "allow_dragging_multihead",
        "UNIFIED_OUTPUTS": "unified_outputs",
        "DISMISS_ANIMATIONS": "allow_dismiss_animations",
        "AFFORDANCES": "per_mascot_interactions",
        "INTERPOLATION_FRAMERATE": "interpolation_framerate",
        "WLR_SHELL_LAYER": "overlay_layer",
        "TABLETS_ENABLED": "tablets_enabled",
        "POINTER_LEFT_BUTTON": "pointer_left_value",
        "POINTER_RIGHT_BUTTON": "pointer_right_value",
        "POINTER_MIDDLE_BUTTON": "pointer_middle_value",
        "ON_TOOL_PEN": "on_tool_pen_value",
        "ON_TOOL_ERASER": "on_tool_eraser_value",
        "ON_TOOL_BRUSH": "on_tool_brush_value",
        "ON_TOOL_PENCIL": "on_tool_pencil_value",
        "ON_TOOL_AIRBRUSH": "on_tool_airbrush_value",
        "ON_TOOL_FINGER": "on_tool_finger_value",
        "ON_TOOL_LENS": "on_tool_lens_value",
        "ON_TOOL_MOUSE": "on_tool_mouse_value",
        "ON_TOOL_BUTTON1": "on_tool_button1_value",
        "ON_TOOL_BUTTON2": "on_tool_button2_value",
        "ON_TOOL_BUTTON3": "on_tool_button3_value",
        "OPACITY": "mascot_opacity",
        "MASCOT_SCALE": "mascot_scale",
        "PROTOTYPES_LOCATION": "prototypes_location",
        "PLUGINS_LOCATION": "plugins_location",
        "SOCKET_LOCATION": "socket_location",
        "CHAT_ENABLED": "chat_enabled",
        "CHAT_COMMAND": "chat_command",
        "CHAT_ROLE": "chat_role",
        "CHAT_ROLES": "chat_roles",
        "CHAT_REMARKS": "chat_remarks",
        "CHAT_MEMORY": "chat_memory",
        "CHAT_TOOLS": "chat_tools",
        "CHAT_DOTFILES": "chat_dotfiles",
        "CHAT_LANGUAGE": "chat_language",
        "BUBBLE_ENABLED": "bubble_enabled",
        "BUBBLE_COMMAND": "bubble_command",
    }

    backmap = { v: k for k, v in name_cast.items() }

    config_file_loc = arguments.config
    if config_file_loc is None:
        basedir = os.path.expanduser(arguments.config_root or "~/.local/share/mascot")
        config_file_loc = os.path.join(basedir, "mascotd.conf")

    if not os.path.exists(config_file_loc):
        print(f"Config file not found at {config_file_loc}! Please start mascot at least once before editing it.")
        exit(1)

    # Lines without a key (comments, blank ones) and keys this does not know
    # are kept as they are when a key is set
    with open(config_file_loc, "r") as f:
        lines = f.read().splitlines()
    config = {}
    for line in lines:
        if line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in backmap:
            config[backmap[key.strip()]] = value.strip()


    match arguments.subcommand:
        case "get":
            if arguments.key not in name_cast:
                print(f"Unknown key: {arguments.key}\nAvailable keys:")
                for key in name_cast:
                    print(f"  - {key}")
                exit(1)
            print(config.get(arguments.key, "Key not found"))
        case "set":
            if arguments.key not in name_cast:
                print(f"Unknown key: {arguments.key}\nAvailable keys:")
                for key in name_cast:
                    print(f"  - {key}")
                exit(1)
            value = arguments.value.strip()
            problem = config_value_problem(arguments.key, value)
            if problem:
                print(f"Not set: {problem}")
                exit(1)
            line = f"{name_cast[arguments.key]}={value}"
            at = next((i for i, l in enumerate(lines) if not l.startswith("#") and "=" in l
                       and l.split("=", 1)[0].strip() == name_cast[arguments.key]), None)
            if at is None:
                lines.append(line)
            else:
                lines[at] = line
            with open(config_file_loc, "w") as f:
                f.write("\n".join(lines) + "\n")
            print(f"{arguments.key} = {value} (mascot is not running; it takes effect when it starts)")
        case "list":
            print("Config:")
            for key, value in config.items():
                print(f"{key}: {value}")
        case _:
            parser.print_help()
            exit(1)

def installed_version() -> str:
    """mascotd's version: the one installed next to this script, else the first in PATH
    (the version lives in one place, MASCOTD_VERSION)"""
    beside = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), "mascotd")
    command = beside if os.access(beside, os.X_OK) else "mascotd"
    try:
        return subprocess.run([command, "--version"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"Cannot ask mascotd for its version: {e}", file=sys.stderr)
        exit(1)

def plugins_handler(arguments, client, plugins_category):
    if plugins_category == "restore-windows":
        packet = PluginRestoreWindows()
        client.queue_packet(packet)

if __name__ == "__main__":
    argparser = MascotParser(description="CLI client for the mascot overlay")
    argparser.add_argument("-s", "--socket", help="Path to the mascotd socket")
    argparser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    argparser.add_argument("-c", "--config", help="Path to the mascotd config")
    argparser.add_argument("-cr", "--config-root", help="Path to the mascotd config root directory")
    argparser.add_argument("--do-not-start", action="store_true", help="Do not start the overlay")
    argparser.add_argument("--do-start", action="store_true", help="Start the overlay")
    argparser.add_argument("--version", action="store_true", help="Show Mascot's version (the installed mascotd's)")

    # Only mascot --help ends with chat_help()
    category = argparser.add_subparsers(dest="category", help="", parser_class=argparse.ArgumentParser)

# Mascot category

    mascot_category = category.add_parser("mascot", help="Manage mascots")
    mascot_subparsers = mascot_category.add_subparsers(dest="action", help="Action to perform")

    summoner = mascot_subparsers.add_parser("summon", help="Summon a mascot")
    summoner.add_argument("name", help="Name of the mascot to summon. You can see available mascot types using prototypes list")
    summoner.add_argument('-s', "--select", action="store_true", help="Use selection mechanism to select place where to summon")
    summoner.add_argument("-e", "--environment", action="append", help="Selects possible environments to summon in. If specified with select, will act as filter for the selection")
    summoner.add_argument("-x", type=coordinate, help="Selects X coordinates to summon in. Does nothing when select is specified.")
    summoner.add_argument("-y", type=coordinate, help="Selects Y coordinates to summon in. Does nothing when select is specified.")
    summoner.add_argument("--position", type=position, help="Takes a position in the format x,y, mutually exclusive with -x and -y")
    summoner.add_argument("-b", "--behavior", help="Specifies starting behavior.", default="")

    dismisser = mascot_subparsers.add_parser("dismiss", help="Dismiss a mascot")
    dismisser.add_argument("-i", "--id", help="ID of the mascot to dismiss.")
    dismisser.add_argument('-s', "--select", action="store_true", help="Use selection mechanism to select place where to summon")
    dismisser.add_argument("-e", "--environment", action="append", help="Selects possible environments to where dismiss can be done. Acts as filter for the selection and if specified with --all will act as filter during processing")
    dismisser.add_argument("-a", "--all", action="store_true", help="Dismiss all mascots. Mutually exclusive with --all-other")
    dismisser.add_argument("-o", "--filter-other", action="store_true", help="Dismiss all mascots except the one selected")
    dismisser.add_argument("-fs", "--filter-same-type", action="store_true", help="Dismiss all mascots of the same type as the selected one")

    # info_getter = mascot_subparsers.add_parser("info", help="Get information about a mascot")
    # info_getter.add_argument("-i", "--id", help="ID of the mascot to get information about. If not specified, selection mechanism will be used")

    behavior_setter = mascot_subparsers.add_parser("set-behavior", help="Set behavior of a mascot")
    behavior_setter.add_argument("-i", "--id", help="ID of the mascot to set behavior for. If not specified, selection mechanism will be used")
    behavior_setter.add_argument("behavior_name", help="Behavior(s) to set for the mascot.")

# Environment category

    environment_category = category.add_parser("environment", help="Manage environments")
    environment_subparsers = environment_category.add_subparsers(dest="action", help="Action to perform")

    environment_list = environment_subparsers.add_parser("list", help="List known environments")

    environment_close = environment_subparsers.add_parser("close", help="Close overlay on a screen (Acts as if output was unplugged, to restore overlay on that screen you need to restart the overlay or replug the screen)")
    environment_close.add_argument("-i", "--id", help="ID of the environment to close")

    environment_info = environment_subparsers.add_parser("info", help="Get information about an environment")
    environment_info.add_argument("-i", "--id", help="ID of the environment to get information about")

# Prototype category

    prototype_category = category.add_parser("prototypes", help="Manage prototypes")
    prototype_subparsers = prototype_category.add_subparsers(dest="action", help="Action to perform")

    prototype_list = prototype_subparsers.add_parser("list", help="List known prototypes")
    prototype_list.add_argument("-d", "--detailed", action="store_true", help="Show detailed information about the prototypes")

    prototype_info = prototype_subparsers.add_parser("info", help="Get information about a prototype")
    prototype_info.add_argument("name", action="append", help="Name(s) of the prototype to get information about")

    prototype_reloader = prototype_subparsers.add_parser("reload", help="Reload a prototype")
    prototype_reloader.add_argument("path", action="append", help="Path(s) of the prototype to reload")

    prototype_reload_all = prototype_subparsers.add_parser("reload-all", help="Reload all prototypes")

    prototype_poses = prototype_subparsers.add_parser("poses", help="Show a mascot's actions as moving pictures in the browser, to pick what it talks and sleeps with")
    prototype_poses.add_argument("name", help="The mascot, by its name (e.g. \"Red Shiba\")")
    prototype_poses.add_argument("--no-open", action="store_true", help="Only write the page and say where")

    prototype_setter = prototype_subparsers.add_parser("set", help="Change what an installed mascot talks, waits with an answer and sleeps with")
    prototype_setter.add_argument("name", help="The mascot, by its name (e.g. \"Red Shiba\")")
    prototype_setter.add_argument("--talk", metavar="ACTION", help="Action it plays while the chat bubble answers; 'auto' to pick one, 'none' for none")
    prototype_setter.add_argument("--answered", metavar="ACTION", help="Action it repeats while an answer waits to be read (the bubble was closed while it answered); 'auto' to pick one, 'none' to sit")
    prototype_setter.add_argument("--sleep", metavar="ACTION", help="Action it plays while asleep; 'auto' to pick one (its own Sleep if that lies still), 'none' for its own Sleep")

    prototype_remover = prototype_subparsers.add_parser("remove", help="Remove one of your own installed mascots (sends its mascots away and deletes it)")
    prototype_remover.add_argument("name", help="The mascot, by its name (e.g. \"Red Shiba\")")
    prototype_remover.add_argument("-y", "--yes", action="store_true", help="Do not ask first")

    prototype_exporter = prototype_subparsers.add_parser("export", help="Export a prototype")
    prototype_exporter.add_argument("-i", "--name", action="append", help="Name of the prototype to export. Can be specified multiple times.")
    prototype_exporter.add_argument("-o", "--output", action="append", help="Output file path. Should match inputs count or be a directory")
    prototype_exporter.add_argument("-f", "--force", action="store_true", help="Overwrite existing files")

    prototype_importer = prototype_subparsers.add_parser("import", help="Import a prototype")
    prototype_importer.add_argument("input", nargs="*", help="Path(s) of the prototype to import: a .wlshm file, or a Shimeji-ee pack (zip file or directory), converted on the way. Can be specified multiple times.")
    prototype_importer.add_argument("-f", "--force", action="store_true", help="Overwrite existing prototypes")
    prototype_importer.add_argument("--no-climb", action="store_true", help="Remove wall and ceiling behaviors, so the mascot stays on the floor")
    prototype_importer.add_argument("--talk", metavar="ACTION", help="Action the mascot plays while the chat bubble answers (see 'mascot prototypes info'); without it one is picked (a petting, talking or waving one), 'none' for none")
    prototype_importer.add_argument("--answered", metavar="ACTION", help="Action the mascot repeats while an answer waits to be read; without it one is picked (looking at you, waving...), 'none' to sit")
    prototype_importer.add_argument("--sleep", metavar="ACTION", help="Action the mascot plays while asleep (mascot sleep, a middle click), if its own Sleep does not look like sleeping")
    prototype_importer.add_argument("--figure", action="append", metavar="NAME", help="Mascot of a Shimeji-ee pack to import (can be given more than once); without it, the pack's only one, or you pick")
    prototype_importer.add_argument("--all", action="store_true", help="Import all mascots of a Shimeji-ee pack")
    prototype_importer.add_argument("--name", help="Name for the mascot from a Shimeji-ee pack (one mascot)")

# Convert category

    convert_category = category.add_parser("convert", help="Convert a instance")
    convert_category.add_argument("input", help="Path of the instance to convert. Should be either a directory or a zip file. Must be Shimeji-EE instance.")
    convert_category.add_argument("-O", "--output", help="Output directory.", required=True)
    convert_category.add_argument("-f", "--force", action="store_true", help="Overwrite existing files")
    convert_category.add_argument("--figure", action="append", metavar="NAME", help="Mascot of the pack to convert (can be given more than once); without it, the pack's only one, or you pick")
    convert_category.add_argument("--all", action="store_true", help="Convert all mascots of the pack")
    convert_category.add_argument("--name", help="Name for the converted mascot (one mascot)")

# Config category

    config_category = category.add_parser("config", help="Config category")

    config_subparsers = config_category.add_subparsers(dest="subcommand", help="Subcommands")

    config_subparsers.add_parser("list", help="List all config files")
    getter = config_subparsers.add_parser("get", help="Get a config value")
    getter.add_argument("key", help="Key of the config value to get")

    setter = config_subparsers.add_parser("set", help="Set a config value")
    setter.add_argument("key", help="Key of the config value to set, e.g. CHAT_TOOLS (mascot config list shows them all, mascot --help the chat's)")
    setter.add_argument("value", help="Value to set, e.g. 'time,weather,files'")

# Stop

    stop_parser = category.add_parser("stop", help="Ask overlay daemon to stop")

# Chat bubble

    category.add_parser("setup", help="Set up the chat: where the mascot thinks, the model, your language and its tools")

    chat_parser = category.add_parser("chat", help="Open the chat bubble at the mascot you last talked to, or close it")
    chat_parser.add_argument("--remark", action="store_true", help="Let a random mascot say something now instead (as CHAT_REMARKS does)")

    category.add_parser("menu", help="Open the right-click menu at the mascot you last talked to (keyboard: arrows, Enter, Esc), or close it")

    sleep_parser = category.add_parser("sleep", help="Put the mascots to sleep until 'mascot wake' (e.g. from hypridle)")
    sleep_parser.add_argument("-m", "--minutes", type=float, help="Sleep this long instead; a plain 'mascot wake' does not end it")
    wake_parser = category.add_parser("wake", help="Wake the mascots up again")
    wake_parser.add_argument("-a", "--all", action="store_true", help="Also from a sleep with --minutes")

# Foreground
    foreground_parser = category.add_parser("foreground", help="Run overlay daemon in foreground")

# Shortcuts

    summoner = category.add_parser("summon", help="Summon a mascot")
    summoner.add_argument("name", help="Name of the mascot to summon. You can see available mascot types using prototypes list")
    summoner.add_argument('-s', "--select", action="store_true", help="Use selection mechanism to select place where to summon")
    summoner.add_argument("-e", "--environment", action="append", help="Selects possible environments to summon in. If specified with select, will act as filter for the selection")
    summoner.add_argument("-x", type=coordinate, help="Selects X coordinates to summon in. Does nothing when select is specified.")
    summoner.add_argument("-y", type=coordinate, help="Selects Y coordinates to summon in. Does nothing when select is specified.")
    summoner.add_argument("--position", type=position, help="Takes a position in the format x,y, mutually exclusive with -x and -y")
    summoner.add_argument("-b", "--behavior", help="Specifies starting behavior.", default="")

    dismisser = category.add_parser("dismiss", help="Dismiss a mascot")
    dismisser.add_argument("-i", "--id", help="ID of the mascot to dismiss.")
    dismisser.add_argument('-s', "--select", action="store_true", help="Use selection mechanism to select place where to summon")
    dismisser.add_argument("-e", "--environment", action="append", help="Selects possible environments to where dismiss can be done. Acts as filter for the selection and if specified with --all will act as filter during processing")
    dismisser.add_argument("-a", "--all", action="store_true", help="Dismiss all mascots. Mutually exclusive with --all-other")
    dismisser.add_argument("-o", "--filter-other", action="store_true", help="Dismiss all mascots except the one selected")
    dismisser.add_argument("-fs", "--filter-same-type", action="store_true", help="Dismiss all mascots of the same type as the selected one")

    behavior_setter = category.add_parser("set-behavior", help="Set behavior of a mascot")
    behavior_setter.add_argument("-i", "--id", help="ID of the mascot to set behavior for. If not specified, selection mechanism will be used")
    behavior_setter.add_argument("behavior_name", help="Behavior(s) to set for the mascot.")

    window_restorer = category.add_parser("restore-windows", help="Restore windows of a mascot")

    prototype_exporter = category.add_parser("export", help="Export a prototype")
    prototype_exporter.add_argument("-i", "--name", action="append", help="Name of the prototype to export. Can be specified multiple times.")
    prototype_exporter.add_argument("-o", "--output", action="append", help="Output file path. Should match inputs count or be a directory")
    prototype_exporter.add_argument("-f", "--force", action="store_true", help="Overwrite existing files")

    prototype_importer = category.add_parser("import", help="Import a prototype")
    prototype_importer.add_argument("input", nargs="*", help="Path(s) of the prototype to import: a .wlshm file, or a Shimeji-ee pack (zip file or directory), converted on the way. Can be specified multiple times.")
    prototype_importer.add_argument("-f", "--force", action="store_true", help="Overwrite existing prototypes")
    prototype_importer.add_argument("--no-climb", action="store_true", help="Remove wall and ceiling behaviors, so the mascot stays on the floor")
    prototype_importer.add_argument("--talk", metavar="ACTION", help="Action the mascot plays while the chat bubble answers (see 'mascot prototypes info'); without it one is picked (a petting, talking or waving one), 'none' for none")
    prototype_importer.add_argument("--answered", metavar="ACTION", help="Action the mascot repeats while an answer waits to be read; without it one is picked (looking at you, waving...), 'none' to sit")
    prototype_importer.add_argument("--sleep", metavar="ACTION", help="Action the mascot plays while asleep (mascot sleep, a middle click), if its own Sleep does not look like sleeping")
    prototype_importer.add_argument("--figure", action="append", metavar="NAME", help="Mascot of a Shimeji-ee pack to import (can be given more than once); without it, the pack's only one, or you pick")
    prototype_importer.add_argument("--all", action="store_true", help="Import all mascots of a Shimeji-ee pack")
    prototype_importer.add_argument("--name", help="Name for the mascot from a Shimeji-ee pack (one mascot)")

    prototype_list = category.add_parser("list", help="List known prototypes")
    prototype_list.add_argument("-d", "--detailed", action="store_true", help="Show detailed information about the prototypes")

    arguments = argparser.parse_args()
    if arguments.version:
        print(installed_version())
        exit(0)
    if arguments.category is None:
        if not chat_is_set_up(os.path.expanduser(arguments.config_root or "~/.local/share/mascot")):
            print(SETUP_HINT + "\n", file=sys.stderr)
        argparser.print_help()
        exit(1)

    # Setup asks in the terminal and writes files; the overlay is only told through mascot config set
    if arguments.category == "setup":
        exit(setup_handler(arguments))

    # Converting only writes files, so it must not need (or start) the overlay
    if arguments.category == "convert":
        logging.basicConfig(level=logging.DEBUG if arguments.verbose else logging.INFO)
        converter_handler(arguments, convert_category)
        exit(0)

    # Shimeji-ee packs are converted before the overlay is asked (or started)
    importing = arguments.category == "import" or (arguments.category == "prototypes" and getattr(arguments, "action", None) == "import")
    if importing:
        logging.basicConfig(level=logging.DEBUG if arguments.verbose else logging.INFO)
        converted_dirs = converted_for_import(arguments)
        if not arguments.input:
            logger.error("Nothing to import")
            exit(1)

    # Only in the user's own runtime directory: in /tmp another user could make the socket first
    if not arguments.socket and not os.environ.get("XDG_RUNTIME_DIR"):
        print("XDG_RUNTIME_DIR is not set: Mascot keeps its sockets there, where only you can reach them (your "
              "login sets it under Wayland). Set it, or give one with -s <path>", file=sys.stderr)
        exit(1)
    socket_path = arguments.socket or os.path.join(os.environ["XDG_RUNTIME_DIR"], "mascotd.sock")

    # Goes straight to the chat socket next to the IPC socket (foo.sock ->
    # foo-chat.sock, see src/chat.c); never starts the overlay
    if arguments.category in ("chat", "menu", "sleep", "wake"):
        chat_path = socket_path[:-len(".sock")] + "-chat.sock" if socket_path.endswith(".sock") else socket_path + "-chat"
        if arguments.category == "chat":
            message: dict[str, Any] = {"event": "remark" if arguments.remark else "toggle"}
        elif arguments.category == "menu":
            message = {"event": "menu_toggle"}
        else:
            message = {"event": arguments.category}
            if arguments.category == "sleep" and arguments.minutes and arguments.minutes > 0:
                message["minutes"] = arguments.minutes
            if arguments.category == "wake" and arguments.all:
                message["all"] = True
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as chat:
                chat.connect(chat_path)
                # No spaces: mascotd matches "event":"..." as it is
                chat.sendall(json.dumps(message, separators=(",", ":")).encode() + b"\n")
        except OSError as e:
            # hypridle runs these whether Mascot is running or not
            if arguments.category in ("sleep", "wake") and e.errno in (errno.ENOENT, errno.ECONNREFUSED):
                exit(0)
            print(f"Cannot reach the chat bubble at {chat_path} ({e.strerror}); is mascotd running?", file=sys.stderr)
            exit(1)
        exit(0)

    startopts: dict[str, Any] = {
        "cmdline": []
    }

    if arguments.verbose:
        logging.basicConfig(level=logging.DEBUG)
        startopts["verbose"] = True
    else:
        logging.basicConfig(level=logging.INFO)


    if arguments.socket:
        startopts["cmdline"].append('-s')
        startopts["cmdline"].append(socket_path)

    if arguments.do_not_start:
        startopts["start"] = False
    if arguments.do_start:
        startopts["start"] = True

    if arguments.do_start and arguments.do_not_start:
        logging.error("--do-not-start and --do-start are mutually exclusive")
        exit(1)

    if arguments.config:
        startopts["config"] = arguments.config
        startopts["cmdline"].append("--config-file")
        startopts["cmdline"].append(arguments.config)

    if arguments.config_root:
        startopts["config_root"] = arguments.config_root
        startopts["cmdline"].append("--configuration-root")
        startopts["cmdline"].append(arguments.config_root)

    if arguments.category == "foreground":
        startopts["start"] = True
        startopts["verbose"] = True

    if arguments.category == "config":
        startopts["start"] = False
        startopts["is_config_req"] = True

    try:
        client = Client(socket_path, startopts)
    except KeyboardInterrupt:
        logging.info("Interrupted.")
    except SystemExit as e:
        if arguments.category == "config":
            local_config_handler(arguments, config_category)
            exit(0)
        raise e
    except Exception as e:
        logging.error(f"Failed to start client: {e}")
        exit(1)

    if arguments.category == "foreground":
        try:
            client.dispatch_events()
        except KeyboardInterrupt:
            logging.info("Interrupted.")
            stopcommand = Stop()
            client.queue_packet(stopcommand)
        except Exception as e:
            logging.error(f"Failed to dispatch events: {e}")
            exit(1)
        exit(0)

    try:
        match arguments.category:
            case "prototypes":
                prototypes_handler(arguments, client, prototype_category)
            case "mascot":
                mascot_handler(arguments, client, mascot_category)
            case "environment":
                environment_handler(arguments, client, environment_category)
            case "stop":
                client.queue_packet(Stop())
            case "config":
                config_handler(arguments, client, config_category)
            case "summon":
                arguments.category = "mascot"
                arguments.action = "summon"
                mascot_handler(arguments, client, argparser)
            case "dismiss":
                arguments.category = "mascot"
                arguments.action = "dismiss"
                mascot_handler(arguments, client, argparser)
            case "set-behavior":
                arguments.category = "mascot"
                arguments.action = "set-behavior"
                mascot_handler(arguments, client, argparser)
            case "list":
                arguments.category = "prototypes"
                arguments.action = "list"
                prototypes_handler(arguments, client, argparser)
            case "import":
                arguments.category = "prototypes"
                arguments.action = "import"
                prototypes_handler(arguments, client, argparser)
            case "export":
                arguments.category = "prototypes"
                arguments.action = "export"
                prototypes_handler(arguments, client, argparser)
            case "restore-windows":
                arguments.category = "plugins"
                arguments.action = "restore-windows"
                plugins_handler(arguments, client, "restore-windows")
            case _:
                argparser.print_help()
                exit(1)
        if arguments.category != "stop":
            client.sync()
    except KeyboardInterrupt:
        logging.info("Interrupted.")
