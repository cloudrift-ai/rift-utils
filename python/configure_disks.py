#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REQUIRED_PACKAGES = [
    "qemu-kvm",
    "libvirt-daemon-system",
    "genisoimage",
    "whois",
]

QEMU_CONF = Path("/etc/libvirt/qemu.conf")

def run(cmd, check=True, capture_output=False, quiet_stderr=False):
    kwargs = {}
    if capture_output:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["text"] = True
    if quiet_stderr:
        kwargs["stderr"] = subprocess.DEVNULL
    return subprocess.run(cmd, check=check, **kwargs)


def apt_install():
    print("Updating apt and installing packages...")
    run(["apt", "update"])
    run(["apt", "install", "-y", *REQUIRED_PACKAGES])

def ensure_qemu_conf_lines():
    print(f"Ensuring user/group lines in {QEMU_CONF} ...")
    QEMU_CONF.parent.mkdir(parents=True, exist_ok=True)
    contents = QEMU_CONF.read_text() if QEMU_CONF.exists() else ""
    desired = 'user = "root"\n' 'group = "root"\n'
    # Append only if not already present
    if 'user = "root"' not in contents or 'group = "root"' not in contents:
        with QEMU_CONF.open("a") as f:
            f.write(desired)
        print("Appended user/group configuration.")
    else:
        print("User/group configuration already present; skipping.")

def restart_libvirtd():
    svc = "libvirtd"
    print(f"Restarting {svc} service...")
    run(["systemctl", "restart", svc])
    run(["systemctl", "is-active", "--quiet", svc])
    print(f"{svc} is active.")

def find_unused_whole_disks(add_dev_prefix=False):
    # Use lsblk JSON; suppress stderr warnings like "not a block device"
    res = run(
        ["lsblk", "-J", "-o", "NAME,TYPE,MOUNTPOINT"],
        capture_output=True,
        quiet_stderr=True,
    )
    data = json.loads(res.stdout)
    disks = []
    for dev in data.get("blockdevices", []):
        # Select only whole disks: type=="disk", no children, no mountpoint
        if (
            dev.get("type") == "disk"
            and not dev.get("children")
            and dev.get("mountpoint") in (None, "")
        ):
            name = dev.get("name")
            if not name:
                continue
            disks.append(f"/dev/{name}" if add_dev_prefix else name)
    return disks

def configure_disks():

    # Validate dependencies we directly call
    for bin_name in ("lsblk", "systemctl", "bash"):
        if shutil.which(bin_name) is None:
            print(f"Missing required command: {bin_name}", file=sys.stderr)
            sys.exit(1)

    apt_install()
    ensure_qemu_conf_lines()
    restart_libvirtd()

    # Discover disks (no /dev prefix by default, matching your Bash)
    disks = find_unused_whole_disks(add_dev_prefix=False)

    print(f"Detected unused whole disks: {disks}")

    if len(disks) == 0:
        print("Single disk setup. Create logical volume")
        # (Your original script only printed a message here.)
        return
    elif len(disks) == 1:
        # Exactly one disk; pass it as a single argument
        target = disks[0]
        print(f"Running ./one_disk.sh {target}")
    else:
        # More than one disk; pass as a single comma-separated argument
        joined = ",".join(disks)
        print(f'Running ./many_disks.sh "{joined}"')

