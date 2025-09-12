#!/usr/bin/env python3
from utils import run
import json
import shutil
import sys

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

