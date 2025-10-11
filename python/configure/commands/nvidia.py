
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

def configure_container_toolkit_repository() -> bool:
    """
    Configure the NVIDIA Container Toolkit repository.
    """
    try:
        print("Configuring NVIDIA Container Toolkit repository...")

        print("Downloading and installing NVIDIA GPG key...")
        tmp_gpg_path = "/tmp/nvidia-gpg-key"
        run(["curl", "-fsSL", "https://nvidia.github.io/libnvidia-container/gpgkey", "-o", tmp_gpg_path], check=True)
        run(["gpg", "--dearmor", tmp_gpg_path, "-o", "/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg"], shell=True, check=True)
        os.remove(tmp_gpg_path)

        print("Adding NVIDIA Container Toolkit repository...")
        tmp_repo_path = "/tmp/nvidia-container-toolkit.list"
        run(["curl", "-sL", "https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list", "-o", tmp_repo_path], check=True)
        run(["sed", "-i", "s#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g", tmp_repo_path], check=True)
        run(["mv", tmp_repo_path, "/etc/apt/sources.list.d/nvidia-container-toolkit.list"], check=True)

        print("Updating package lists...")
        run(["apt-get", "update"], check=True)

        print("NVIDIA Container Toolkit repository configured successfully.")
    except Exception as e:
        print(f"Error configuring NVIDIA Container Toolkit repository: {e}")
        return False
    return True

def check_nvidia_container_toolkit_installed() -> bool:
    """
    Check if NVIDIA Container Toolkit is installed.
    """
    try:
        # Method 1: Check if nvidia-ctk command is available
        output, _, return_code = run(
            ["nvidia-ctk", "--version"], 
            shell=False, 
            capture_output=True, 
            check=False
        )
        if return_code == 0:
            print(f"NVIDIA Container Toolkit is installed: {output.strip()}")
            return True
        
        # Method 2: Check package installation status
        output, _, return_code = run(
            ["dpkg", "-s", "nvidia-container-toolkit"], 
            shell=False, 
            capture_output=True, 
            check=False
        )
        if return_code == 0 and "Status: install ok installed" in output:
            print("NVIDIA Container Toolkit package is installed.")
            return True
            
        print("NVIDIA Container Toolkit is not installed.")
        return False
        
    except Exception as e:
        print(f"Error checking NVIDIA Container Toolkit installation: {e}")
        return False

def install_nvidia_container_toolkit() -> bool:
    """
    Install NVIDIA Container Toolkit if not already installed.
    """
    # Check if already installed
    if check_nvidia_container_toolkit_installed():
        if not yes_no_prompt("NVIDIA Container Toolkit is already installed. Do you want to reinstall it?", False):
            return True
    
    if not configure_container_toolkit_repository():
        print("Failed to configure NVIDIA Container Toolkit repository.")
        return False

    try:
        print("Installing NVIDIA Container Toolkit...")
        run(["apt-get", "install", "-y", "nvidia-container-toolkit"])
        
        print("Configuring Docker runtime...")
        run(["nvidia-ctk", "runtime", "configure", "--runtime=docker"])
        
        print("Restarting Docker service...")
        run(["systemctl", "restart", "docker"])
        
        print("NVIDIA Container Toolkit installation completed successfully.")
        return True
    except Exception as e:
        print(f"Error installing NVIDIA Container Toolkit: {e}")
        return False

def find_cuda_versions() -> list[str]:
    """
    Find available CUDA Toolkit versions from the package repository.
    """
    try:
        # Search for cuda toolkit packages
        output, _, return_code = run(
            ["apt", "search", "cuda-toolkit"], 
            shell=False, 
            capture_output=True, 
            check=False
        )
        
        if return_code != 0:
            return []
        
        versions = []
        for line in output.split('\n'):
            if 'cuda-toolkit-' in line and line.startswith('cuda-toolkit-'):
                # Extract version number
                package_name = line.split('/')[0].strip()
                if package_name not in versions:
                    versions.append(package_name)
        
        return sorted(versions)
        
    except Exception as e:
        print(f"Error finding CUDA Toolkit versions: {e}")
        return []    
    return []

def check_cuda_installed() -> bool:
    """
    Check if CUDA Toolkit is installed.
    """
    try:
        output, _, return_code = run(
            ["nvcc", "--version"], 
            shell=False, 
            capture_output=True, 
            check=False
        )
        if return_code == 0 and output:
            print(f"CUDA Toolkit is installed: {output.strip()}")
            return True
        else:
            print("CUDA Toolkit is not installed.")
            return False
    except Exception as e:
        print(f"Error checking CUDA Toolkit installation: {e}")
        return False

def install_nvidia_cuda_toolkit() -> bool:
    """
    Install NVIDIA CUDA Toolkit.
    """
    try:
        cuda_packages = find_cuda_versions()
        if not cuda_packages:
            print("No CUDA Toolkit versions found in the repository.")
            return False

        for idx, package in enumerate(cuda_packages):
            print(f"{idx + 1}. {package}")
        print("CUDA Toolkit Driver Version Ranges:")
        print("  cuda-toolkit-13: Driver >= 580")
        print("  cuda-toolkit-12: Driver >= 525")
        print("  cuda-toolkit-11: Driver >= 450")
        choice = numbered_prompt("Select the CUDA Toolkit package to install:", 1, len(cuda_packages))
        if choice is None:
            print("No package selected, aborting installation.")
            return False

        print(f"Installing NVIDIA CUDA Toolkit {cuda_packages[choice - 1]}")
        run(["apt-get", "install", "-y", cuda_packages[choice - 1]])

        print("NVIDIA CUDA Toolkit installation completed successfully.")
        return True
    except Exception as e:
        print(f"Error installing NVIDIA CUDA Toolkit: {e}")
        return False

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

class InstallNvidiaContainerToolkitCmd(BaseCmd):
    """ Command to install NVIDIA Container Toolkit. """

    def name(self) -> str:
        return "Install NVIDIA Container Toolkit"

    def description(self) -> str:
        return "Installs the NVIDIA Container Toolkit."

    def execute(self, env: Dict[str, Any]) -> bool:
        if not check_nvidia_installed():
            print("NVIDIA driver is not installed. Please install the driver first.")
            return False

        return install_nvidia_container_toolkit()

class InstallNvidiaCudaToolkitCmd(BaseCmd):
    """ Command to install NVIDIA CUDA Toolkit. """

    def name(self) -> str:
        return "Install NVIDIA CUDA Toolkit"

    def description(self) -> str:
        return "Installs the NVIDIA CUDA Toolkit."

    def execute(self, env: Dict[str, Any]) -> bool:
        if not check_nvidia_installed():
            print("NVIDIA driver is not installed. Please install the driver first.")
            return False

        if check_cuda_installed():
            if not yes_no_prompt("NVIDIA CUDA Toolkit is already installed. Do you want to reinstall it?", False):
                return True

        return install_nvidia_cuda_toolkit()