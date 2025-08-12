import os
import subprocess
import sys


def run_command(command, shell=False):
    """
    Runs a shell command and returns the output.
    Exits the script if the command fails.
    """
    try:
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
    # This command requires sudo, so we use a different method.
    command = f'echo {num_hugepages} | sudo tee /sys/kernel/mm/hugepages/hugepages-1048576kB/nr_hugepages'
    try:
        subprocess.run(command, check=True, text=True, shell=True)
        print(f"Successfully allocated {num_hugepages} huge pages.")
    except subprocess.CalledProcessError as e:
        print(f"Error allocating huge pages. Return code: {e.returncode}")
        print(f"STDERR: {e.stderr}")
        print("Please check if you have enough free memory or try a smaller number.")
        sys.exit(1)


def add_hugepages_to_grub_options(grub_options: Dict[str, Any], num_hugepages, enable_5level_paging=False):
    cmdline_linux_options = grub_options.get('GRUB_CMDLINE_LINUX', '').split()
    cmdline_linux_default_options = grub_options.get('GRUB_CMDLINE_LINUX_DEFAULT', '').split()
    # Add the new hugepage configuration
    cmdline_linux_options.append(f'default_hugepagesz=1G hugepagesz=1G hugepages={num_hugepages}')

    # Remove any existing hugepage configuration
    cmdline_linux_options = [opt for opt in cmdline_linux_options if not opt.startswith(('default_hugepagesz', 'hugepagesz', 'hugepages'))]

    if enable_5level_paging:
        cmdline_linux_default_options = [opt for opt in cmdline_linux_default_options if opt != 'la57']

        # Add the new la57 option
        cmdline_linux_default_options.append('la57')
        grub_options['GRUB_CMDLINE_LINUX_DEFAULT'] = ' '.join(cmdline_linux_default_options)

    grub_options['GRUB_CMDLINE_LINUX'] = ' '.join(cmdline_linux_options)
    return grub_options



def enable_5level_paging():
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
    run_command(f"sudo mkdir -p {mount_point}")
    run_command(f"sudo mount -t hugetlbfs -o pagesize=1G none {mount_point}")
    print("Verifying mount point...")
    run_command("grep hugetlbfs /proc/mounts")
    return mount_point


def persist_mount(mount_point):
    """
    Adds the huge page mount to /etc/fstab to persist across reboots.
    """
    print("\n--- Making Mount Persistent with /etc/fstab ---")
    fstab_line = f"none {mount_point} hugetlbfs pagesize=1G 0 0\n"

    try:
        # Check if the line already exists
        with open("/etc/fstab", 'r') as f:
            if fstab_line in f.read():
                print(f"Mount point '{mount_point}' already exists in /etc/fstab.")
                return
    except FileNotFoundError:
        print("Error: /etc/fstab not found.")
        sys.exit(1)

    # Use sudo tee to append the line
    try:
        command = f'echo "{fstab_line}" | sudo tee -a /etc/fstab'
        subprocess.run(command, check=True, text=True, shell=True)
        print(f"Successfully added '{fstab_line.strip()}' to /etc/fstab.")
    except subprocess.CalledProcessError as e:
        print(f"Error adding mount to /etc/fstab. Return code: {e.returncode}")
        sys.exit(1)


def reboot_and_verify():
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


def main():
    """
    Main function to orchestrate the huge page configuration.
    """
    if os.geteuid() != 0:
        print("This script requires root privileges. Please run with sudo.")
        sys.exit(1)

    print("--- Huge Page Configuration Script ---")

    # 1. Check Huge Page Support
    hugepage_info = get_hugepage_info()
    if 'Hugepagesize' not in hugepage_info or '1048576 kB' not in hugepage_info.get('Hugepagesize'):
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

    while True:
        try:
            vm_memory_gb = int(input("\nEnter the total memory you want to dedicate to VMs (in GB): "))
            buffer_gb = int(input("Enter the buffer size (in GB): "))

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

            allocate_hugepages(num_hugepages)
            get_hugepage_info()

            break
        except ValueError:
            print("Invalid input. Please enter a valid number.")

    # 3. Make Huge Pages Persistent
    enable_5level = False
    if enable_5level_paging():
        print("\nDo you want to enable 5-level paging? (y/n)")
        if input().lower() == 'y':
            enable_5level = True

    update_grub_for_hugepages(num_hugepages, enable_5level_paging=enable_5level)

    # 5. Mount Huge Page Table
    mount_point = mount_hugepage_table()

    # 6. Persist the Mount on Reboot
    persist_mount(mount_point)

    # 7. Reboot and Verify
    reboot_and_verify()


if __name__ == "__main__":
    main()