from .cmd import BaseCmd
from pathlib import Path
from .utils import run
from typing import Any, Dict
import subprocess

QEMU_CONF = Path("/etc/libvirt/qemu.conf")

def ensure_qemu_conf_lines() -> bool:
    print(f"Ensuring user/group lines in {QEMU_CONF} ...")

    try:
        # Read current configuration with sudo
        result = subprocess.run(['sudo', 'cat', str(QEMU_CONF)],
                              capture_output=True, text=True, check=True)
        contents = result.stdout
    except subprocess.CalledProcessError:
        print(f"Warning: Could not read {QEMU_CONF}.")
        contents = ""

    # Check if user and group are already set
    if 'user = "root"' in contents and 'group = "root"' in contents:
        print("User/group configuration already present; skipping.")
        return False

    # Append user and group configuration
    desired = '\nuser = "root"\ngroup = "root"\n'

    try:
        # Use sudo to append to the file
        process = subprocess.Popen(['sudo', 'tee', '-a', str(QEMU_CONF)],
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 text=True)
        stdout, stderr = process.communicate(input=desired)

        if process.returncode == 0:
            print("Appended user/group configuration.")
            return True
        else:
            print(f"Error writing to qemu.conf: {stderr}")
            return False

    except Exception as e:
        print(f"Error updating qemu.conf: {e}")
        return False

def restart_libvirtd():
    svc = "libvirtd"
    print(f"Restarting {svc} service...")
    run(["sudo", "systemctl", "restart", svc])
    run(["sudo", "systemctl", "is-active", "--quiet", svc])
    print(f"{svc} is active.")

def verify_qemu_conf() -> bool:
    """Verify that qemu.conf has the user and group settings."""
    print("Verifying libvirt qemu.conf configuration...")

    try:
        result = subprocess.run(['sudo', 'cat', str(QEMU_CONF)],
                              capture_output=True, text=True, check=True)
        contents = result.stdout

        user_ok = 'user = "root"' in contents
        group_ok = 'group = "root"' in contents

        print(f"  {'✓' if user_ok else '✗'} User set to root")
        print(f"  {'✓' if group_ok else '✗'} Group set to root")

        return user_ok and group_ok

    except subprocess.CalledProcessError as e:
        print(f"Error reading qemu.conf: {e}")
        return False

class ConfigureLibvirtCmd(BaseCmd):
    """ Command to configure libvirt for virtualization. """

    def name(self) -> str:
        return "Configure Libvirt"

    def description(self) -> str:
        return "Sets up libvirt."

    def execute(self, env: Dict[str, Any]) -> bool:
        changes_made = ensure_qemu_conf_lines()
        if changes_made:
            restart_libvirtd()

        # Verify the configuration
        if verify_qemu_conf():
            print("Libvirt configuration completed successfully.")
            return True
        else:
            print("Warning: Libvirt configuration verification failed.")
            return False
    
class CheckVirtualizationCmd(BaseCmd):
    """ Command to check if virtualization is supported. """

    def name(self) -> str:
        return "Check Virtualization Support"

    def description(self) -> str:
        return "Checks if the CPU supports virtualization."

    def execute(self, env: Dict[str, Any]) -> bool:
        print("Checking for virtualization support...")
        cpuinfo, _, _ = run(["grep", "-E", "vmx|svm", "/proc/cpuinfo"], capture_output=True, quiet_stderr=True)
        if cpuinfo:
            print("Virtualization support detected.")
            return True
        else:
            print("No virtualization support detected. Exiting.")
            return False