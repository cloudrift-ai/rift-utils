#!/usr/bin/env python3

import os
from typing import Any, Dict, Optional, Tuple

from .cmd import BaseCmd
from .utils import run, add_mp_to_fstab, CLOUDRIFT_MEDIA_MOUNT
import json
import shutil
import subprocess


def get_lvm_free_space() -> Optional[Tuple[str, float]]:
    """
    Check for free space in LVM volume groups.
    Returns (vg_name, free_gb) or None if no free space available.
    """
    try:
        # Get volume group info in JSON format
        out, _, rc = run(["vgs", "--reportformat", "json", "--units", "g"], capture_output=True, quiet_stderr=True)
        if rc != 0:
            return None

        data = json.loads(out)
        for vg in data.get("report", [{}])[0].get("vg", []):
            vg_name = vg.get("vg_name", "")
            vg_free = vg.get("vg_free", "0g")

            # Parse free space value (remove 'g' suffix and convert to float)
            free_gb = float(vg_free.rstrip('g'))

            # If there's significant free space (> 10GB), we can use it
            if free_gb > 10:
                print(f"Found {free_gb:.1f}GB free space in volume group '{vg_name}'")
                return vg_name, free_gb

    except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as e:
        print(f"Could not check LVM free space: {e}")

    return None

def create_lvm_logical_volume(vg_name: str) -> str:
    """
    Create a logical volume using all free space in the volume group.
    Returns the device path of the created logical volume.
    """
    lv_name = "cloudrift"

    # Create logical volume using 100% of free space
    print(f"Creating logical volume '{lv_name}' in volume group '{vg_name}'")
    run(["lvcreate", "-l", "100%FREE", "-n", lv_name, vg_name])

    # Return the device path
    lv_path = f"/dev/{vg_name}/{lv_name}"
    print(f"Created logical volume: {lv_path}")
    return lv_path

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
    # For LVM volumes, use noatime and defaults, for regular disks use nofail and discard
    if "/dev/mapper/" in dev or "-vg-" in dev:
        fstab_line = f"UUID={uuid} {mp} ext4 defaults,noatime 0 2\n"
    else:
        fstab_line = f"UUID={uuid} {mp} ext4 defaults,nofail,discard 0 0\n"
    add_mp_to_fstab(fstab_line, mp)


def mount_media_disk(dev, mp):
    run(["mkdir", "-p", mp])
    run(["mount", dev, mp])

def create_filesystem(dev, label="cloudrift"):
    # Use -m 0 to reserve 0% for root (maximizing available space)
    run(["mkfs.ext4", "-m", "0", "-L", label, dev])

def create_raid_array(disks):
    cmd = ["mdadm", "--create", "--verbose", "/dev/md0", "--level=0", "--raid-devices={}".format(len(disks))]
    devices = ["/dev/"+disk for disk in disks]
    print("Creating RAID 0 array with devices: {}".format(devices))
    cmd.extend(devices)
    run(cmd)

def configure_disks():

    # Validate dependencies we directly call
    for bin_name in ("lsblk", "systemctl", "bash", "vgs", "lvcreate"):
        if shutil.which(bin_name) is None:
            raise RuntimeError(f"Missing required command: {bin_name}")

    # First, check if there's free space in LVM
    lvm_info = get_lvm_free_space()

    if lvm_info:
        # Use LVM free space
        vg_name, free_gb = lvm_info
        print(f"Using LVM free space: {free_gb:.1f}GB in volume group '{vg_name}'")

        # Create logical volume
        lv_path = create_lvm_logical_volume(vg_name)

        # Create filesystem
        create_filesystem(lv_path)

        # Mount the logical volume
        mount_media_disk(lv_path, CLOUDRIFT_MEDIA_MOUNT)

        # Add to fstab (will use the device mapper path)
        # The actual device path might be /dev/mapper/vg_name-lv_name
        mapper_path = f"/dev/mapper/{vg_name.replace('-', '--')}-cloudrift"
        if os.path.exists(mapper_path):
            add_to_fstab(mapper_path, CLOUDRIFT_MEDIA_MOUNT)
        else:
            add_to_fstab(lv_path, CLOUDRIFT_MEDIA_MOUNT)

        reload_daemon()
        print(f"Successfully configured LVM logical volume at {CLOUDRIFT_MEDIA_MOUNT}")

    else:
        # No LVM free space, check for unused disks
        disks = find_unused_whole_disks(add_dev_prefix=False)
        print(f"Detected unused whole disks: {disks}")

        if len(disks) == 0:
            raise RuntimeError("No unused disks and no LVM free space available. Unable to configure storage automatically.")
        elif len(disks) == 1:
            # Single disk setup
            disk_path = f"/dev/{disks[0]}"
            print(f"Using single disk: {disk_path}")

            create_filesystem(disk_path)
            mount_media_disk(disk_path, CLOUDRIFT_MEDIA_MOUNT)
            add_to_fstab(disk_path, CLOUDRIFT_MEDIA_MOUNT)
            reload_daemon()
            print(f"Successfully configured single disk at {CLOUDRIFT_MEDIA_MOUNT}")
        else:
            # Multiple disks - create RAID
            create_raid_array(disks)
            create_filesystem("/dev/md0")
            mount_media_disk("/dev/md0", CLOUDRIFT_MEDIA_MOUNT)
            add_to_fstab("/dev/md0", CLOUDRIFT_MEDIA_MOUNT)
            reload_daemon()
            print(f"Successfully configured RAID array at {CLOUDRIFT_MEDIA_MOUNT}")

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