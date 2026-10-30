#!/usr/bin/env python3
"""Made-up machines for check_system's "machine" area, to see what it says on hardware we do not have.

    scripts/fake_machines.py <dir>          builds them in <dir> and runs check_system on each

Each machine is a /proc and /sys of its own (MASCOT_MACHINE_ROOT); disks are folders in it, so their
sizes are those of <dir>'s file system. /proc/stat does not change, so "how busy the CPU is" is
always missing here.
"""
import json
import os
import stat
import subprocess
import sys

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools", "bin", "check_system")


def write(root, path, text):
    path = os.path.join(root, path.lstrip("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text + "\n")


def hwmon(root, n, name, temps=(), fans=(), files=None):
    """temps: (label or None, millidegrees, crit or None); fans: rpm"""
    base = f"/sys/class/hwmon/hwmon{n}"
    write(root, f"{base}/name", name)
    for i, (label, value, crit) in enumerate(temps, 1):
        write(root, f"{base}/temp{i}_input", str(value))
        if label:
            write(root, f"{base}/temp{i}_label", label)
        if crit:
            write(root, f"{base}/temp{i}_crit", str(crit))
    for i, rpm in enumerate(fans, 1):
        write(root, f"{base}/fan{i}_input", str(rpm))
    for path, text in (files or {}).items():
        write(root, f"{base}/{path}", text)


def zone(root, n, kind, value):
    write(root, f"/sys/class/thermal/thermal_zone{n}/type", kind)
    write(root, f"/sys/class/thermal/thermal_zone{n}/temp", str(value))


def common(root, mem_kb, avail_kb, programs, disks=("/",)):
    write(root, "/proc/stat", "cpu  100 0 50 1000 10 0 0 0 0 0")
    write(root, "/proc/loadavg", "0.52 0.40 0.31 1/200 1234")
    write(root, "/proc/meminfo", f"MemTotal: {mem_kb} kB\nMemAvailable: {avail_kb} kB\nSwapTotal: 0 kB\nSwapFree: 0 kB")
    for pid, (name, pages) in enumerate(programs, 100):
        write(root, f"/proc/{pid}/stat", f"{pid} ({name}) S 1 1 1 0 -1 4194304 0 0 0 0 10 5 0 0 20 0 1 0 1 0 0")
        write(root, f"/proc/{pid}/statm", f"{pages * 2} {pages} 0 0 0 0 0")
    mounts = []
    for where in disks:
        os.makedirs(os.path.join(root, where.lstrip("/")), exist_ok=True)
        mounts.append(f"/dev/sda1 {where} ext4 rw,relatime 0 0")
    write(root, "/proc/self/mounts", "\n".join(mounts + ["proc /proc proc rw 0 0"]))


def intel_laptop(root):
    """Intel CPU and graphics (i915: no hwmon), Wi-Fi; no fan sensors"""
    common(root, 16_000_000, 9_000_000, [("firefox", 300_000), ("code", 200_000)])
    hwmon(root, 0, "acpitz", [(None, 50000, 120000)])
    hwmon(root, 1, "coretemp", [("Package id 0", 72000, 100000), ("Core 0", 70000, 100000),
                                ("Core 1", 71000, 100000)])
    hwmon(root, 2, "iwlwifi_1", [(None, 45000, None)])
    zone(root, 0, "x86_pkg_temp", 72000)


def nvidia_desktop(root):
    """Intel CPU, a mainboard with fans (nct6775), an SSD near its limit, NVIDIA's own driver; little memory left"""
    common(root, 32_000_000, 2_000_000, [("steam", 500_000), ("game.exe", 2_000_000)], disks=("/", "/games"))
    hwmon(root, 0, "coretemp", [("Package id 0", 81000, 100000)])
    hwmon(root, 1, "nct6775", [("SYSTIN", 38000, None), ("CPUTIN", 55000, None)], fans=(1100, 0, 870))
    hwmon(root, 2, "nvme", [("Composite", 82000, 84850)])
    os.makedirs(os.path.join(root, "proc/driver/nvidia"), exist_ok=True)
    smi = os.path.join(root, "bin", "nvidia-smi")
    write(root, "/bin/nvidia-smi", "#!/bin/sh\necho 'NVIDIA GeForce RTX 4070, 74, 97 %, 11020 MiB, 12282 MiB, 68 %'")
    os.chmod(smi, os.stat(smi).st_mode | stat.S_IEXEC)


def virtual_machine(root):
    """No sensors at all"""
    common(root, 4_000_000, 3_000_000, [("sshd", 2_000)])


def arm_board(root):
    """Only a thermal zone (cpu-thermal), and hot"""
    common(root, 8_000_000, 6_000_000, [("python3", 30_000)])
    zone(root, 0, "cpu-thermal", 93000)


MACHINES = {"intel-laptop": intel_laptop, "nvidia-desktop": nvidia_desktop, "virtual-machine": virtual_machine,
            "arm-board": arm_board}

if __name__ == "__main__":
    out = os.path.abspath(sys.argv[1])
    for name, build in MACHINES.items():
        root = os.path.join(out, name)
        build(root)
        env = dict(os.environ, MASCOT_TOOLS_LOCAL="1", MASCOT_TOOLS_ALLOWED="check_system", MASCOT_MACHINE_ROOT=root,
                   PATH=os.path.join(root, "bin") + os.pathsep + os.environ.get("PATH", ""))
        done = subprocess.run([TOOLS, json.dumps({"area": "machine"})], capture_output=True, text=True, env=env)
        marks = [l for l in done.stderr.splitlines() if l.startswith("mascot-") and not l.startswith("mascot-doing")]
        print(f"== {name}: {build.__doc__} ({', '.join(marks)})")
        print(done.stdout.strip() or done.stderr.strip())
        print()
