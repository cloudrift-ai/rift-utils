import os
import subprocess
import sys
from typing import Dict, Any
from .cmd import BaseCmd
from .utils import run, add_mp_to_fstab

def run_command(command):
    shell = isinstance(command, str)
    try:
        out, _, _ = run(cmd=command, shell=shell, check=True, capture_output=True, quiet_stderr=True)
        return out
    except subprocess.CalledProcessError as e:
        print(f"Error running command: '{command}'")
        print(f"Return code: {e.returncode}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        sys.exit(1)


def run_command_old(command, shell=False):
    """
    Runs a shell command and returns the output.
    Exits the script if the command fails.
    """
    try:
        print(f"Running command: {command}")
        if shell:
            result = subprocess.run(command, check=True, text=True, capture_output=True, shell=True)
        else:
            result = subprocess.run(command.split(), check=True, text=True, capture_output=True)
        print(f"Command '{command}' succeeded.")
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: '{command}'")
        print(f"Return code: {e.returncode}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        sys.exit(1)


def get_hugepage_info():
    """
    Reads and returns the huge page information from /proc/meminfo.
    """
    print("\n--- Checking Huge Page Support ---")
    output = run_command("grep -i huge /proc/meminfo")
    print(output)
    return {line.split(":")[0].strip(): line.split(":")[1].strip() for line in output.split('\n')}


def allocate_hugepages(num_hugepages):
    """
    Allocates the specified number of 1GB huge pages.
    """
    print(f"\n--- Allocating {num_hugepages} Huge Pages ---")
    # Write directly to sysfs to allocate hugepages
    command = f'echo {num_hugepages} | tee /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages'
    try:
        run(command, check=True, shell=True)
        print(f"Successfully allocated {num_hugepages} huge pages.")
    except subprocess.CalledProcessError as e:
        print(f"Error allocating huge pages. Return code: {e.returncode}")
        print(f"STDERR: {e.stderr}")
        print("Please check if you have enough free memory or try a smaller number.")
        raise e


def add_hugepages_to_grub_options(grub_options: Dict[str, Any], num_hugepages, enable_5level_paging=False) -> Dict[str, Any]:
    opt = grub_options.get('GRUB_CMDLINE_LINUX', '')
    cmdline_linux_options = opt.split() if isinstance(opt, str) else opt
    opt = grub_options.get('GRUB_CMDLINE_LINUX_DEFAULT', '')
    cmdline_linux_default_options = opt.split() if isinstance(opt, str) else opt

    # Remove any existing hugepage configuration from both GRUB_CMDLINE_LINUX and GRUB_CMDLINE_LINUX_DEFAULT
    cmdline_linux_options = [opt for opt in cmdline_linux_options if not opt.startswith(('default_hugepagesz', 'hugepagesz', 'hugepages'))]
    cmdline_linux_default_options = [opt for opt in cmdline_linux_default_options if not opt.startswith(('default_hugepagesz', 'hugepagesz', 'hugepages'))]

    # Add the new hugepage configuration to GRUB_CMDLINE_LINUX_DEFAULT (not GRUB_CMDLINE_LINUX)
    # This ensures it's applied to normal boot entries on Ubuntu
    cmdline_linux_default_options.append(f'default_hugepagesz=1G')
    cmdline_linux_default_options.append(f'hugepagesz=1G')
    cmdline_linux_default_options.append(f'hugepages={num_hugepages}')

    if enable_5level_paging:
        cmdline_linux_default_options = [opt for opt in cmdline_linux_default_options if opt != 'la57']
        # Add the new la57 option
        cmdline_linux_default_options.append('la57')

    grub_options['GRUB_CMDLINE_LINUX_DEFAULT'] = ' '.join(cmdline_linux_default_options)
    grub_options['GRUB_CMDLINE_LINUX'] = ' '.join(cmdline_linux_options)
    return grub_options



def supports_5level_paging():
    """
    Checks for 5-level paging support and prompts the user to enable it.
    """
    print("\n--- Checking for 5-level Paging Support ---")
    try:
        output = run_command('lscpu | grep "Address sizes"')
        if "57 bits virtual" in output:
            print("CPU supports 57-bit address space (5-level paging).")
            # We will handle the GRUB update in the main function
            return True
        else:
            print("CPU does not support 57-bit virtual address space. Skipping 5-level paging configuration.")
            return False
    except subprocess.CalledProcessError:
        print("Could not check for 5-level paging support. Skipping.")
        return False


def mount_hugepage_table():
    """
    Creates a mount point and mounts the huge page table.
    """
    print("\n--- Mounting Huge Page Table ---")
    mount_point = "/mnt/hugepages-1G"
    run_command(f"mkdir -p {mount_point}")
    run_command(f"mount -t hugetlbfs -o pagesize=1G none {mount_point}")
    print("Verifying mount point...")
    run_command("grep hugetlbfs /proc/mounts")
    return mount_point


def persist_mount(mount_point):
    """
    Adds the huge page mount to /etc/fstab to persist across reboots.
    """
    print("\n--- Making Mount Persistent with /etc/fstab ---")
    fstab_line = f"none {mount_point} hugetlbfs pagesize=1G 0 0\n"
    if add_mp_to_fstab(fstab_line, mount_point):
        print(f"Successfully added '{fstab_line.strip()}' to /etc/fstab.")
    else:
        print(f"Failed to add '{fstab_line.strip()}' to /etc/fstab.")
        sys.exit(1)

def configure_memory(existing_options: Dict[str, Any]):
    """
    Main function to orchestrate the huge page configuration.
    """

    print("--- Huge Page Configuration Script ---")

    # 1. Check Huge Page Support
    hugepage_info = get_hugepage_info()
    if 'Hugepagesize' not in hugepage_info:
        print("Warning: 1GB Hugepagesize not detected. Please ensure your kernel supports it.")

    # 2. Allocate Huge Pages
    try:
        total_ram_gb = int(run_command("free -g | grep Mem | awk '{print $2}'"))
        print(f"\nTotal system RAM detected: {total_ram_gb} GB.")
    except Exception:
        total_ram_gb = 0
        print("Could not determine total system RAM. Please enter it manually.")

    if total_ram_gb < 128:
        print("System RAM is less than 128 GB. 1GB Huge Pages are not recommended.")
        print("Script will exit.")
        return

    recommended_vm_memory = total_ram_gb * 0.8
    recommended_buffer = total_ram_gb * 0.05

    while True:
        try:
            vm_memory_gb = int(input(f"\nEnter the total memory you want to dedicate to VMs (in GB) [{recommended_vm_memory}]: ") or recommended_vm_memory)
            print(f"You entered: {vm_memory_gb}")
            buffer_gb = int(input(f"Enter the buffer size (in GB) [{recommended_buffer}]: ") or recommended_buffer)

            if vm_memory_gb + buffer_gb > total_ram_gb:
                print("Error: The requested memory exceeds total system RAM. Please enter a smaller value.")
                continue

            num_hugepages = (vm_memory_gb + buffer_gb)
            if num_hugepages <= 0:
                print("Error: The number of huge pages must be greater than zero.")
                continue

            print(f"\nCalculation: ({vm_memory_gb} GB + {buffer_gb} GB) / 1 GB = {num_hugepages} Huge Pages needed.")

            print(f"Allocating {num_hugepages} huge pages temporarily.")

            # We don't allocate here as it is a temporary allocation that will be lost on reboot.
            # We'll rely on the GRUB configuration for persistence.
            # This is a change from the user's instructions to make the script more robust.
            # The temporary allocation is mainly for testing.

            try:
                allocate_hugepages(num_hugepages)
            except Exception as e:
                print(f"Failed to allocate huge pages temporarily. Error: {e}")
                continue
            get_hugepage_info()

            break
        except ValueError:
            print("Invalid input. Please enter a valid number.")

    # 3. Make Huge Pages Persistent
    enable_5level = False
    if supports_5level_paging():
        print("\nDo you want to enable 5-level paging? (Y/n)")
        if (input() or 'y').lower() == 'y':
            print("5-level paging will be enabled.")
            enable_5level = True

    print("\nUpdating GRUB configuration...")
    existing_options = add_hugepages_to_grub_options(existing_options, num_hugepages, enable_5level_paging=enable_5level)

    # 5. Mount Huge Page Table
    print("\nMounting huge page table...")
    mount_point = mount_hugepage_table()

    # 6. Persist the Mount on Reboot
    print("\nMaking the mount persistent...")
    persist_mount(mount_point)

    return existing_options

class ConfigureMemoryCmd(BaseCmd):
    """ Command to configure huge pages. """

    def name(self) -> str:
        return "Configure Huge Pages"
    
    def description(self) -> str:
        return "Configures 1GB huge pages for virtualization."

    def execute(self, env: Dict[str, Any]) -> bool:
        try:
            configure_memory(env)
            print(f"Updated GRUB_CMDLINE_LINUX_DEFAULT: {env['GRUB_CMDLINE_LINUX_DEFAULT']}")
            print(f"Updated GRUB_CMDLINE_LINUX: {env['GRUB_CMDLINE_LINUX']}")
            return True
        except Exception as e:
            print(f"Error configuring memory: {e}")
            return False