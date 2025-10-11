
import subprocess
import os
from typing import Any, Dict
from .cmd import BaseCmd
from .utils import numbered_prompt, run, reboot_prompt, yes_no_prompt

def check_nvidia():
    """
    Check if nvidia driver is installed
    """
    
    output, _, return_code = run("lsmod | grep nvidia", shell=True, capture_output=True, check=False)
    if return_code == 0 and output:
        print("NVIDIA driver is in use.")
    else:
        print("NVIDIA driver is not in use.")
    
    return return_code == 0 and output

def check_nvidia_installed():
    """
    Check if nvidia driver is installed
    """
    
    output, _, return_code = run("nvidia-smi", shell=True, capture_output=True, check=False)
    if return_code == 0 and output:
        print("NVIDIA driver is installed.")
    else:
        print("NVIDIA driver is not installed.")
    
    return return_code == 0 and output

def remove_nvidia_driver():
    """
    Main function to check for and remove NVIDIA drivers.
    """
    # Check if the nvidia module is loaded
    if check_nvidia():
        print("NVIDIA driver is in use. Attempting to remove it.")

        # Run the NVIDIA uninstaller (if it exists)
        if os.path.exists("/usr/bin/nvidia-uninstall"):
            print("Running NVIDIA uninstaller...")
            run(["/usr/bin/nvidia-uninstall", "-s"], check=False)
        else:
            print("NVIDIA uninstaller not found, skipping...")

        # Remove NVIDIA driver and associated packages
        print("Removing NVIDIA packages...")
        run(["apt-get", "remove", "--purge", "^nvidia-.*"])
        run(["apt-get", "autoremove"])

        # Blacklist the nouveau driver
        print("Adding 'nouveau' to /etc/modules...")
        with open("/etc/modules", "a") as f:
            f.write("nouveau\n")

        # Clean up X11 configuration
        print("Removing X11 configuration files...")
        #run(["rm", "/etc/X11/xorg.conf"])
        run(["rm", "-rf", "/etc/X11/xorg.conf"])

        # Clean up modprobe configurations
        print("Removing modprobe configuration files...")
        run(["rm", "-rf", "/etc/modprobe.d/nvidia*.conf"])
        run(["rm", "-rf", "/lib/modprobe.d/nvidia*.conf"])

        reboot_prompt()
    else:
        print("NVIDIA driver does not appear to be in use, or the command failed to run.")

def find_nvidia_driver() -> list[str]:
    """
    Find available NVIDIA drivers from the package repository.
    """
    try:
        # Search for nvidia driver packages
        output, _, return_code = run(
            ["apt", "search", "nvidia-driver"], 
            shell=False, 
            capture_output=True, 
            check=False
        )
        
        if return_code != 0:
            return []
        
        drivers = []
        for line in output.split('\n'):
            if 'nvidia-driver-' in line and line.startswith('nvidia-driver-'):
                # Extract driver package name
                package_name = line.split('/')[0].strip()
                if package_name not in drivers:
                    drivers.append(package_name)
        
        return sorted(drivers)
        
    except Exception as e:
        print(f"Error finding NVIDIA drivers: {e}")
        return []    
    return []

def install_nvidia_driver():
    """
    Install the NVIDIA driver.
    """

    if yes_no_prompt("Do you want to purge existing NVIDIA drivers before installation?", True):
        print("Removing any existing NVIDIA drivers...")
        run(["apt-get", "remove", "--purge", "^nvidia-.*"])

    drivers = find_nvidia_driver()

    for idx, driver in enumerate(drivers):
        print(f"{idx + 1}. {driver}")
    choice = numbered_prompt("Select the NVIDIA driver to install:", 1, len(drivers))
    if choice is None:
        print("No driver selected, aborting installation.")
        return

    print(f"Installing NVIDIA driver {drivers[choice - 1]}...")
    run(["apt-get", "install", "-y", drivers[choice - 1]])
    reboot_prompt()

class RemoveNvidiaDriverCmd(BaseCmd):
    """ Command to remove NVIDIA driver. """

    def name(self) -> str:
        return "Remove NVIDIA Driver"
    
    def description(self) -> str:
        return "Checks for and removes NVIDIA drivers if they are installed."

    def execute(self, env: Dict[str, Any]) -> bool:
        remove_nvidia_driver()
        return True


class InstallNvidiaDriverCmd(BaseCmd):
    """ Command to install NVIDIA driver. """

    def name(self) -> str:
        return "Install NVIDIA Driver"

    def description(self) -> str:
        return "Checks for and installs NVIDIA drivers if they are not installed."

    def execute(self, env: Dict[str, Any]) -> bool:
        if check_nvidia_installed():
            if not yes_no_prompt("NVIDIA driver is already installed. Do you want to reinstall it?", False):
                return True
        
        install_nvidia_driver()
        return True
