import os
import subprocess
import re
import sys

GRUB_MAIN_FILE = '/etc/default/grub'
GRUB_D_DIR = '/etc/default/grub.d'
VFIO_GRUB_FILE = os.path.join(GRUB_D_DIR, '99-cloudrift.cfg')
INITRAMFS_MODULES_FILE = '/etc/initramfs-tools/modules'
VFIO_CONF_FILE = '/etc/modprobe.d/vfio.conf'


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
    


def create_grub_override(grub_options: Dict[str, Any]):
    """
    Creates a new GRUB configuration file in /etc/default/grub.d with the
    necessary kernel parameters, appending to existing ones.

    Args:
        pci_ids: A list of "vendor:device" strings for the GPUs.
        iommu_type: 'intel_iommu=on' or 'amd_iommu=on'.
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


def setup_virtualization():
    """
    Main function to orchestrate the script's execution.
    """
    if os.geteuid() != 0:
        print("This script must be run with sudo.")
        sys.exit(1)

    print("This script will configure your system for VFIO passthrough.")
    print("It will modify /etc/default/grub, /etc/initramfs-tools/modules, and /etc/modprobe.d/vfio.conf.")

    # Get user confirmation
    choice = input("Do you want to proceed? (y/n): ")
    if choice.lower() != 'y':
        print("Script aborted by user.")
        sys.exit(0)

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

    existing_options = get_existing_grub_parameters('GRUB_CMDLINE_LINUX_DEFAULT')
    grub_options = add_virtualization_options(existing_options)
    create_grub_override(pci_ids, iommu_type)
    update_initramfs_modules()
    create_vfio_conf()

    # Run update commands
    update_system()

    # After reboot, run this to check the status
    # check_vfio_driver()





