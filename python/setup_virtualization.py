import os
import subprocess
import re
import sys

import json
import os
import shutil
import sys
from pathlib import Path


INITRAMFS_MODULES_FILE = '/etc/initramfs-tools/modules'
VFIO_CONF_FILE = '/etc/modprobe.d/vfio.conf'

QEMU_CONF = Path("/etc/libvirt/qemu.conf")





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


def get_gpu_pci_ids():
    """
    Finds the PCI vendor and device IDs for NVIDIA GPUs.

    Returns:
        A list of "vendor:device" strings for each NVIDIA GPU found, or None on error.
    """
    try:
        lspci_output = subprocess.check_output(['lspci', '-nnk']).decode('utf-8')
        nvidia_lines = [line for line in lspci_output.splitlines() if 'NVIDIA Corporation' in line]

        if not nvidia_lines:
            print("No NVIDIA GPUs found.")
            return []

        pci_ids = []
        for line in nvidia_lines:
            match = re.search(r'\[([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\]', line)
            if match:
                vendor_id = match.group(1)
                device_id = match.group(2)
                pci_ids.append(f"{vendor_id}:{device_id}")

        return sorted(list(set(pci_ids)))
    except subprocess.CalledProcessError as e:
        print(f"Error running lspci: {e}")
        return None


def add_virtualization_options(pci_ids, iommu_type, existing_options: Dict[str, Any]):
    new_options = [
        'iommu=pt',
        'pci=realloc',
        'pcie_aspm=off',
        iommu_type,
        'nomodeset',
        'video=efifb:off'
    ]

    vfio_ids_str = ','.join(pci_ids)
    if vfio_ids_str:
        new_options.append(f'vfio-pci.ids={vfio_ids_str}')
        new_options.append('modprobe.blacklist=nouveau,nvidia,nvidiafb,snd_hda_intel')
    else:
        print("Warning: No PCI IDs provided for VFIO binding. Skipping VFIO options.")

    # Only add options that are not already present
    final_options_list = existing_options['GRUB_CMDLINE_LINUX_DEFAULT'].split()
    for opt in new_options:
        # Simple check to avoid duplicates for non-vfio options
        if not any(opt.split('=')[0] in existing_opt for existing_opt in final_options_list):
            final_options_list.append(opt)

    # Handle the vfio-pci.ids and modprobe.blacklist options carefully
    # We remove the old ones if they exist and add our new, complete ones
    final_options_list = [opt for opt in final_options_list if not opt.startswith('vfio-pci.ids=')]
    final_options_list = [opt for opt in final_options_list if not opt.startswith('modprobe.blacklist=')]
    if vfio_ids_str:
        final_options_list.append(f'vfio-pci.ids={vfio_ids_str}')
        final_options_list.append('modprobe.blacklist=nouveau,nvidia,nvidiafb,snd_hda_intel')
    
    existing_options['GRUB_CMDLINE_LINUX_DEFAULT'] = ' '.join(final_options_list)
    
    return existing_options
    

def update_initramfs_modules():
    """
    Adds VFIO modules to /etc/initramfs-tools/modules if they don't exist.
    """
    modules_file = '/etc/initramfs-tools/modules'
    modules_to_add = ['vfio', 'vfio_iommu_type1', 'vfio_pci', 'vfio_virqfd']

    try:
        with open(modules_file, 'r+') as f:
            existing_modules = f.read()
            f.seek(0, 0)

            updated = False
            for module in modules_to_add:
                if f'\n{module}\n' not in existing_modules:
                    f.write(f'{module}\n')
                    updated = True

            f.write(existing_modules)

        if updated:
            print("VFIO modules added to /etc/initramfs-tools/modules.")
        else:
            print("VFIO modules are already present in /etc/initramfs-tools/modules.")

    except FileNotFoundError:
        print(f"Error: {modules_file} not found.")
    except IOError as e:
        print(f"Error writing to {modules_file}: {e}")


def create_vfio_conf():
    """
    Creates or updates /etc/modprobe.d/vfio.conf to disable PCIe power management.
    """
    conf_dir = '/etc/modprobe.d/'
    conf_file = os.path.join(conf_dir, 'vfio.conf')
    option_line = "options vfio-pci disable_idle_d3=1\n"

    if not os.path.exists(conf_dir):
        os.makedirs(conf_dir)

    try:
        with open(conf_file, 'w') as f:
            f.write(option_line)
        print(f"Created/updated {conf_file} to disable power management for VFIO devices.")
    except IOError as e:
        print(f"Error writing to {conf_file}: {e}")



def setup_virtualization(existing_options: Dict[str, Any]):
    """
    Main function to orchestrate the script's execution.
    """
    if os.geteuid() != 0:
        print("This script must be run with sudo.")
        sys.exit(1)
    
    ensure_qemu_conf_lines()
    restart_libvirtd()

    # Determine IOMMU type
    iommu_type = 'intel_iommu=on'
    if 'AMD' in open('/proc/cpuinfo').read():
        iommu_type = 'amd_iommu=on'
    print(f"Detected CPU type, using '{iommu_type}'.")

    # Get PCI IDs
    pci_ids = get_gpu_pci_ids()
    if pci_ids is None:
        sys.exit(1)

    if not pci_ids:
        print(
            "Warning: No NVIDIA GPUs found. The script will still configure IOMMU options, but VFIO binding will be skipped.")
    else:
        print("Found NVIDIA GPU PCI IDs:", pci_ids)

    # Perform configuration steps

    grub_options = add_virtualization_options(existing_options)
    create_grub_override(grub_options)
    update_initramfs_modules()
    create_vfio_conf()

    # After reboot, run this to check the status
    # check_vfio_driver()





