# Modified for Mascot by Xedoc91, 2026; see the git history for details.
from __future__ import annotations
import socket
import os
import sys
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
from PIL import Image
from qoi.src.qoi import encode_img
import time

from levenstein import lv_variant
from noclimb import strip_climbing

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

def converter_handler(arguments: argparse.Namespace, parser):
    if not os.path.exists(arguments.input):
        print(f"Input file '{arguments.input}' does not exist.")
        exit(1)

    if not os.path.exists(arguments.output):
        os.makedirs(arguments.output, exist_ok=True)

    if not os.path.isdir(arguments.output):
        print("Output is not a directory.")
        exit(1)

    instance_root = arguments.input
    tmpdir_instance_root = None

    if not os.path.isdir(instance_root):
        try:
            zipf = zipfile.ZipFile(instance_root, 'r')
        except Exception as e:
            print(f'Failed to parse Shimeji-EE instance: Cannot open zip file: {e}')
            exit(1)

        tmpdir_instance_root = tempfile.TemporaryDirectory()
        instance_root = tmpdir_instance_root.name
        zipf.extractall(instance_root)

    filelist = os.listdir(instance_root)
    if len(os.listdir(instance_root)) == 1:
        instance_root = os.path.join(instance_root, os.listdir(instance_root)[0])
        if not os.path.isdir(instance_root):
            print("Failed to parse Shimeji-EE instance: Passed input does not contain a valid directory nor is Shimeji-EE instance")
            exit(1)
        filelist = os.listdir(instance_root)

    if not all([
        "img" in filelist,
        "conf" in filelist
    ]):
        print("Failed to parse Shimeji-EE instance: Passed input is not a valid Shimeji-EE instance")
        exit(1)

    if not os.path.isdir(os.path.join(instance_root, "img")):
        print(f"Failed to parse Shimeji-EE instance: \"img\" inside instance is not a directory")
        exit(1)

    if not os.path.isdir(os.path.join(instance_root, "conf")):
        print(f"Failed to parse Shimeji-EE instance: \"conf\" inside instance is not a directory")
        exit(1)

    prototype_names = [dnode for dnode in os.listdir(os.path.join(instance_root, "img")) if (os.path.isdir(os.path.join(instance_root, "img", dnode)) and dnode != "unused")]
    print("Prototypes available for conversion:")
    for i, prototype_name in enumerate(prototype_names):
        print(f"{i+1}. {prototype_name}")
    print("\nEnter prototypes index or name to convert (can be comma-separated or A to convert all)")
    user_input = input(">").rstrip().lstrip()

    if user_input == "A":
        user_input = ",".join([str(i+1) for i in range(len(prototype_names))])

    selected = []
    for index in user_input.split(","):
        if not index.isnumeric():
            if index in prototype_names:
                selected.append(index)
        else:
            index = int(index)
            if index > 0 and index <= len(prototype_names):
                selected.append(prototype_names[index-1])

    if not selected:
        print("No prototypes selected")
        exit(1)

    failed = 0
    for prototype in selected:

        if os.path.exists(os.path.join(arguments.output, f"Shimeji.{prototype}.wlshm")):
            if not arguments.force:
                print(f"File {os.path.join(arguments.output, f'Shimeji.{prototype}.wlshm')} already exists")
                failed += 1
                continue

        config_base_dir_name = os.path.join(instance_root, "conf")

        if os.path.exists(os.path.join(instance_root, "img", prototype, "conf")):
            if os.path.isdir(os.path.join(instance_root, "img", prototype, "conf")):
                config_base_dir_name = os.path.join(instance_root, "img", prototype, "conf")

        config_dirfd = os.open(config_base_dir_name, os.O_PATH)
        try:
            scripts, actions, behaviors = \
            Compiler.compile_shimeji(
                os.path.join(instance_root, "img", prototype),
                config_dirfd
            )
        except Exception as e:
            print(f"Conversion failed for {prototype}: {e}")
            failed += 1
            continue
        finally:
            os.close(config_dirfd)

        manifest = \
        {
            "name": f"Shimeji.{prototype}",
            "version": "0.0.1",
            "description": "",
            "display_name": prototype,
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

        # info.xml sits next to actions.xml, or in the image directory
        info_path = None
        for candidate in (config_base_dir_name, os.path.join(instance_root, "img", prototype)):
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

            manifest["display_name"] = info_text("Name") or manifest["display_name"]
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

        for path, dirs, files in os.walk(os.path.join(instance_root, "img", prototype)):
            if path != os.path.join(instance_root, "img", prototype):
                tarinfo = tarfile.TarInfo("assets/" + path.removeprefix(os.path.join(instance_root, "img", prototype)))
                tarinfo.type = tarfile.DIRTYPE
                tar.addfile(tarinfo)

            for file in files:
                if file.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    img = Image.open(os.path.join(path, file))
                    tempf = tempfile.NamedTemporaryFile(delete=False)
                    tempf.close()
                    encode_img(img, False, tempf.name)
                    tempf = open(tempf.name, "rb")
                    tarinfo = tarfile.TarInfo("assets/" + os.path.join(path.removeprefix(os.path.join(instance_root, "img", prototype)), file.removesuffix(".png")\
                    .removesuffix(".jpg")\
                    .removesuffix(".jpeg")\
                    .removesuffix(".gif")\
                    .removesuffix(".webp") + ".qoi"))
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
        with open(os.path.join(arguments.output, f"Shimeji.{prototype}.wlshm"), "wb") as wlpak:
            wlpak.write(wlpak_prefix)
            wlpak.write(memfile.getvalue())
        print(f'Converted {prototype} to {os.path.join(arguments.output, f"Shimeji.{prototype}.wlshm")}')

    if failed:
        exit(1)

def wlshm_adjusted(path: str, no_climb: bool, talk: str | None):
    """Copy of a .wlshm with --no-climb/--talk applied, as an unlinked temporary file.

    The daemon unpacks whatever fd it is given, so the original file is never touched.
    Returns the file and what was changed, one line each.
    """
    with open(path, "rb") as f:
        header = f.read(512)
        source = tarfile.open(fileobj=io.BytesIO(f.read()), mode="r:*")

    names = source.getnames()
    manifest = json.load(source.extractfile("manifest.json")) if "manifest.json" in names else {}
    behaviors_name = manifest.get("behaviors", "behaviors.json")
    actions_name = manifest.get("actions", "actions.json")
    for needed in (behaviors_name, actions_name):
        if needed not in names:
            raise ValueError(f"{needed} not found")
    behaviors = json.load(source.extractfile(behaviors_name))
    changes = []

    if talk:
        # Inlined actions are anonymous parts of other actions, not something to pick
        actions = [a["name"] for a in json.load(source.extractfile(actions_name)) if not a["name"].startswith("___")]
        match = next((a for a in actions if a.lower() == talk.lower()), None)
        if not match:
            raise ValueError(f"no action called '{talk}'. Actions: {', '.join(actions)}")
        definitions = behaviors.setdefault("definitions", [])
        definitions[:] = [d for d in definitions if d.get("name") != "Talk"]
        # Never picked at random (frequency 0); the daemon switches to it while a reply streams
        definitions.append({"name": "Talk", "action": match, "next_behavior_list": [], "next_behavior_list_count": 0,
                            "hidden": True, "condition": None, "is_conditioner": False,
                            "next_behavior_list_add": True, "frequency": 0})
        changes.append(f"talks with {match}")

    if no_climb:
        disabled = strip_climbing(behaviors)
        changes.append(f"climbing removed ({len(disabled)} behaviors)" if disabled else "no climbing to remove")

    behaviors_data = json.dumps(behaviors).encode("utf-8")
    out = tempfile.TemporaryFile()
    out.write(header)
    with tarfile.open(fileobj=out, mode="w") as tar:
        for member in source.getmembers():
            if member.name == behaviors_name:
                member.size = len(behaviors_data)
                tar.addfile(member, io.BytesIO(behaviors_data))
            else:
                tar.addfile(member, source.extractfile(member) if member.isfile() else None)
    source.close()
    out.seek(0)
    return out, changes

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

                logger.error(f"Failed to import prototype referenced by id {packet.object_id}: {errors.get(packet.error_code, 'Unknown error')}")
                imports.pop(packet.object_id, None)
                objects.pop(packet.object_id, None)

            def finished(client: Client, packet: ImportFinished):
                import_object = imports.get(packet.object_id)
                if import_object:
                    logger.info(f"Successfully imported prototype referenced by id {packet.object_id}")
                    rpacket = ReloadPrototype(packet.relative_path)
                    client.queue_packet(rpacket)

                imports.pop(packet.object_id, None)
                objects.pop(packet.object_id, None)


            client.register_callback(ImportFinished, finished)
            client.register_callback(ImportFailed, failed)

            # Kept open until the daemon is done with them
            adjusted = []
            for input_file in arguments.input:
                if not os.path.exists(input_file):
                    logger.error(f"File '{input_file}' does not exist")
                    exit(1)
                with open(input_file, "rb") as f:
                    if f.read(4) != b'WLPK':
                        logger.warning(f"File '{input_file}' is not a valid mascot prototype, please first convert it to a mascot prototype using the convert command (mascot convert)")
                        continue
                    if not arguments.no_climb and not arguments.talk:
                        Import(f.fileno(), arguments.force, client.socket)
                        continue
                try:
                    copy, changes = wlshm_adjusted(input_file, arguments.no_climb, arguments.talk)
                except (tarfile.TarError, ValueError, KeyError) as e:
                    logger.error(f"Could not prepare '{input_file}': {e}")
                    continue
                print(f"{input_file}: {', '.join(changes)}")
                adjusted.append(copy)
                Import(copy.fileno(), arguments.force, client.socket)


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

                packet = Spawn(prototype.id, random_env.id, xpos, ypos, arguments.behavior)
                client.queue_packet(packet)

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
            packet = SetConfigKey(arguments.key, arguments.value)
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

    def parse_boolean(value):
        if value.lower() in ["true", "yes", "on", "1"]:
            return True
        elif value.lower() in ["false", "no", "off", "0"]:
            return False
        return True

    config = {}
    with open(config_file_loc, "r") as f:
        for line in f.readlines():
            key, value = line.strip().split("=", 1)
            if key in backmap:
                config[backmap[key]] = value.strip()


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
            config[arguments.key] = arguments.value
            with open(config_file_loc, "w") as f:
                for key, value in config.items():
                    f.write(f"{name_cast[key]}={value}\n")
        case "list":
            print("Config:")
            for key, value in config.items():
                print(f"{key}: {value}")
        case _:
            parser.print_help()
            exit(1)

def plugins_handler(arguments, client, plugins_category):
    if plugins_category == "restore-windows":
        packet = PluginRestoreWindows()
        client.queue_packet(packet)

if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description="CLI client for the mascot overlay")
    argparser.add_argument("-s", "--socket", help="Path to the mascotd socket")
    argparser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    argparser.add_argument("-c", "--config", help="Path to the mascotd config")
    argparser.add_argument("-cr", "--config-root", help="Path to the mascotd config root directory")
    argparser.add_argument("--do-not-start", action="store_true", help="Do not start the overlay")
    argparser.add_argument("--do-start", action="store_true", help="Start the overlay")

    category = argparser.add_subparsers(dest="category", help="")

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

    prototype_exporter = prototype_subparsers.add_parser("export", help="Export a prototype")
    prototype_exporter.add_argument("-i", "--name", action="append", help="Name of the prototype to export. Can be specified multiple times.")
    prototype_exporter.add_argument("-o", "--output", action="append", help="Output file path. Should match inputs count or be a directory")
    prototype_exporter.add_argument("-f", "--force", action="store_true", help="Overwrite existing files")

    prototype_importer = prototype_subparsers.add_parser("import", help="Import a prototype")
    prototype_importer.add_argument("input", nargs="*", help="Path(s) of the prototype to import. Can be either in wlshm format or in Shimeji-ee format. Can be specified multiple times.")
    prototype_importer.add_argument("-f", "--force", action="store_true", help="Overwrite existing prototypes")
    prototype_importer.add_argument("--no-climb", action="store_true", help="Remove wall and ceiling behaviors, so the mascot stays on the floor")
    prototype_importer.add_argument("--talk", metavar="ACTION", help="Action the mascot plays while the chat bubble answers (see 'mascot prototypes info')")

# Convert category

    convert_category = category.add_parser("convert", help="Convert a instance")
    convert_category.add_argument("input", help="Path of the instance to convert. Should be either a directory or a zip file. Must be Shimeji-EE instance.")
    convert_category.add_argument("-O", "--output", help="Output directory.", required=True)
    convert_category.add_argument("-f", "--force", action="store_true", help="Overwrite existing files")

# Config category

    config_category = category.add_parser("config", help="Config category")

    config_subparsers = config_category.add_subparsers(dest="subcommand", help="Subcommands")

    config_subparsers.add_parser("list", help="List all config files")
    getter = config_subparsers.add_parser("get", help="Get a config value")
    getter.add_argument("key", help="Key of the config value to get")

    setter = config_subparsers.add_parser("set", help="Set a config value")
    setter.add_argument("key", help="Key of the config value to set")
    setter.add_argument("value", help="Value to set")

# Stop

    stop_parser = category.add_parser("stop", help="Ask overlay daemon to stop")

# Chat bubble

    chat_parser = category.add_parser("chat", help="Open the chat bubble at the mascot you last talked to, or close it")
    chat_parser.add_argument("--remark", action="store_true", help="Let a random mascot say something now instead (as CHAT_REMARKS does)")

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
    prototype_importer.add_argument("input", nargs="*", help="Path(s) of the prototype to import. Can be either in wlshm format or in Shimeji-ee format. Can be specified multiple times.")
    prototype_importer.add_argument("-f", "--force", action="store_true", help="Overwrite existing prototypes")
    prototype_importer.add_argument("--no-climb", action="store_true", help="Remove wall and ceiling behaviors, so the mascot stays on the floor")
    prototype_importer.add_argument("--talk", metavar="ACTION", help="Action the mascot plays while the chat bubble answers (see 'mascot prototypes info')")

    prototype_list = category.add_parser("list", help="List known prototypes")
    prototype_list.add_argument("-d", "--detailed", action="store_true", help="Show detailed information about the prototypes")

    arguments = argparser.parse_args()
    if arguments.category is None:
        argparser.print_help()
        exit(1)

    # Converting only writes files, so it must not need (or start) the overlay
    if arguments.category == "convert":
        logging.basicConfig(level=logging.DEBUG if arguments.verbose else logging.INFO)
        converter_handler(arguments, convert_category)
        exit(0)

    socket_path = arguments.socket or (
        os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp", "mascotd.sock")
    )

    # Goes straight to the chat socket next to the IPC socket (foo.sock ->
    # foo-chat.sock, see src/chat.c); never starts the overlay
    if arguments.category == "chat":
        chat_path = socket_path[:-len(".sock")] + "-chat.sock" if socket_path.endswith(".sock") else socket_path + "-chat"
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as chat:
                chat.connect(chat_path)
                chat.sendall(b'{"event":"remark"}\n' if arguments.remark else b'{"event":"toggle"}\n')
        except OSError as e:
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
