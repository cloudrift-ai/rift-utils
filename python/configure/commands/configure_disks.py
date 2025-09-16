#!/usr/bin/env python3

import os
from typing import Any, Dict

from .cmd import BaseCmd
from .utils import run, add_mp_to_fstab, CLOUDRIFT_MEDIA_MOUNT
import json
import shutil
import sys


def find_unused_whole_disks(add_dev_prefix=False):
    # Use lsblk JSON; suppress stderr warnings like "not a block device"
    out, _, _ = run(
        ["lsblk", "-J", "-o", "NAME,TYPE,MOUNTPOINT"],
        capture_output=True,
        quiet_stderr=True,
    )
    data = json.loads(out)
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

def reload_daemon():
    run(["systemctl", "daemon-reload"])

def add_to_fstab(dev, mp):
    run(["udevadm", "trigger"])
    uuid, _, _ = run(["blkid", "-s", "UUID", "-o", "value", dev], capture_output=True)
    print(f"Adding {dev} with UUID {uuid} to /etc/fstab at mount point {mp}")
    fstab_line = f"UUID={uuid} {mp} ext4 defaults,nofail,discard 0 0\n"
    add_mp_to_fstab(fstab_line, mp)


def mount_media_disk(dev, mp):
    run(["mkdir", "-p", mp])
    run(["mount", dev, mp])

def create_filesystem(dev):
    run(["mkfs.ext4", dev])

def create_raid_array(disks):
    cmd = ["mdadm", "--create", "--verbose", "/dev/md0", "--level=0", "--raid-devices={}".format(len(disks))]
    devices = ["/dev/"+disk for disk in disks]
    print("Creating RAID 0 array with devices: {}".format(devices))
    cmd.extend(devices)
    run(cmd)

def configure_disks():

    # Validate dependencies we directly call
    for bin_name in ("lsblk", "systemctl", "bash"):
        if shutil.which(bin_name) is None:
            print(f"Missing required command: {bin_name}", file=sys.stderr)
            sys.exit(1)


    # Discover disks (no /dev prefix by default, matching your Bash)
    disks = find_unused_whole_disks(add_dev_prefix=False)

    print(f"Detected unused whole disks: {disks}")

    if len(disks) == 0:
        print("Single disk setup. Create logical volume")
        # (Your original script only printed a message here.)
        print("Not implemented yet.")
    elif len(disks) == 1:
        # Exactly one disk; pass it as a single argument
        print("Not implemented yet.")        
    else:
        create_raid_array(disks)
        create_filesystem("/dev/md0")
        mount_media_disk("/dev/md0", CLOUDRIFT_MEDIA_MOUNT)
        add_to_fstab("/dev/md0", CLOUDRIFT_MEDIA_MOUNT)
        reload_daemon()

class ConfigureDisksCmd(BaseCmd):
    """ Command to configure disks. """

    def name(self) -> str:
        return "Configure Disks"
    
    def description(self) -> str:
        return "Configures disks for use with LVM and RAID."

    def execute(self, env: Dict[str, Any]) -> bool:
        try:
            if os.path.exists(CLOUDRIFT_MEDIA_MOUNT):
                print(f"{CLOUDRIFT_MEDIA_MOUNT} already exists, skipping disk configuration.")
                return True
            configure_disks()
            return True
        except Exception as e:
            print(f"Error configuring disks: {e}")
            return False