#!/usr/bin/env python3

import os
import re
import sys
import subprocess
from typing import Dict, Any
from setup_virtualization import add_virtualization_options
from configure_memory import configure_memory
from nvidia import remove_nvidia_driver, check_nvidia
from configure_disks import configure_disks

GRUB_MAIN_FILE = '/etc/default/grub'
GRUB_D_DIR = '/etc/default/grub.d'
VFIO_GRUB_FILE = os.path.join(GRUB_D_DIR, '99-cloudrift.cfg')


REQUIRED_PACKAGES = [
    "qemu-kvm",
    "libvirt-daemon-system",
    "genisoimage",
    "whois",
]


def read_options_from_file(file_path, param_name):
    all_options = []
    with open(file_path, 'r') as f:
        for line in f:
            if param_name in line:
                match = re.search(param_name + r'="([^"]*)"', line)
                if match:
                    all_options.extend(match.group(1).split())
    return all_options

def get_existing_grub_parameters(param_name):
    """
    Reads the param_name from /etc/default/grub and any
    overrides in /etc/default/grub.d.

    Returns:
        A string containing all existing kernel parameters.
    """
    all_options = []

    # Read from the main GRUB file
    try:
        all_options = read_options_from_file(GRUB_MAIN_FILE, param_name)
    except FileNotFoundError:
        print(f"Warning: {GRUB_MAIN_FILE} not found. Starting with an empty command line.")

    # Read from override files in grub.d
    if os.path.exists(GRUB_D_DIR):
        for filename in sorted(os.listdir(GRUB_D_DIR)):
            if filename.endswith('.cfg'):
                filepath = os.path.join(GRUB_D_DIR, filename)
                try:
                    all_options.extend(read_options_from_file(filepath, param_name))
                except IOError as e:
                    print(f"Warning: Could not read {filepath}: {e}")

    # Deduplicate and return as a list
    unique_options = sorted(list(set(all_options)))
    return unique_options



def create_grub_override(grub_options: Dict[str, Any]):
    """
    Creates a new GRUB configuration file in /etc/default/grub.d with the
    necessary kernel parameters, appending to existing ones.

    Args:
        grub_options: A dictionary of kernel parameters with options to add.
    """

    # grub_d_content = f'GRUB_CMDLINE_LINUX_DEFAULT="{final_options_str}"\n'

    grub_d_content = "\n".join([f'{key}="{grub_options[key]}"' for key in grub_options])

    print(f"Creating override file {VFIO_GRUB_FILE}...")
    print(f"Adding line: {grub_d_content}")

    if not os.path.exists(GRUB_D_DIR):
        os.makedirs(GRUB_D_DIR)

    try:
        with open(VFIO_GRUB_FILE, 'w') as f:
            f.write(grub_d_content)
        print("GRUB override file created successfully.")
    except IOError as e:
        print(f"Error writing to {VFIO_GRUB_FILE}: {e}")

def update_system():
    """
    Runs the necessary system commands and prompts for a reboot.
    """
    print("\nRunning system update commands...")
    try:
        subprocess.run(['sudo', 'update-initramfs', '-u', '-k', 'all'], check=True)
        subprocess.run(['sudo', 'update-grub'], check=True)
        print("System updated successfully.")

    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
    except FileNotFoundError as e:
        print(
            f"Error: Command not found. Please ensure 'update-initramfs', 'update-grub', and 'reboot' are in your PATH. {e}")


def reboot_server():
    """
    Prompts the user to reboot and provides verification instructions.
    """
    print("\n--- Reboot and Verify ---")
    print("The configuration is complete. You need to reboot for the changes to take effect.")
    print("After rebooting, you can verify the configuration by running the following commands:")
    print("  grep -i huge /proc/meminfo")
    print("  grep hugetlbfs /proc/mounts")
    print("\nReboot now? (y/n)")
    if input().lower() == 'y':
        print("Rebooting...")
        run_command("sudo reboot")
    else:
        print("Please reboot at your convenience to apply the changes.")



def configure_server():
    """
    Main function to orchestrate the script's execution.
    """
    if os.geteuid() != 0:
        print("This script must be run with sudo.")
        sys.exit(1)

    print("This script will configure your system for server use.")
    print("It adds the necessary kernel parameters to /etc/default/grub.d/99-cloudrift.cfg, /etc/initramfs-tools/modules, and /etc/modprobe.d/vfio.conf.")


    if check_nvidia():
        print("NVIDIA driver is in use. Attempting to remove it.")
        remove_nvidia_driver()

    apt_install(REQUIRED_PACKAGES)

    # Perform configuration steps
    existing_options = {}
    existing_options['GRUB_CMDLINE_LINUX_DEFAULT'] = get_existing_grub_parameters('GRUB_CMDLINE_LINUX_DEFAULT')
    existing_options['GRUB_CMDLINE_LINUX'] = get_existing_grub_parameters('GRUB_CMDLINE_LINUX')

    grub_options = add_virtualization_options(existing_options)
    grub_options = configure_memory(grub_options)
    configure_disks()
    create_grub_override(grub_options)

    # Run update commands
    update_system()

    # Reboot server to apply changes
    reboot_server()

if __name__ == "__main__":
    configure_server()
