from .cmd import BaseCmd
from pathlib import Path
from .utils import run
from typing import Any, Dict

QEMU_CONF = Path("/etc/libvirt/qemu.conf")

def ensure_qemu_conf_lines() -> bool:
    print(f"Ensuring user/group lines in {QEMU_CONF} ...")

    # Create directory if it doesn't exist
    QEMU_CONF.parent.mkdir(parents=True, exist_ok=True)

    # Read current configuration
    contents = QEMU_CONF.read_text() if QEMU_CONF.exists() else ""

    # Check if user and group are already set
    if 'user = "root"' in contents and 'group = "root"' in contents:
        print("User/group configuration already present; skipping.")
        return False

    # Append user and group configuration
    desired = 'user = "root"\ngroup = "root"\n'

    try:
        with QEMU_CONF.open("a") as f:
            f.write(desired)
        print("Appended user/group configuration.")
        return True
    except Exception as e:
        print(f"Error updating qemu.conf: {e}")
        return False

def restart_libvirtd():
    svc = "libvirtd"
    print(f"Restarting {svc} service...")
    run(["systemctl", "restart", svc])
    run(["systemctl", "is-active", "--quiet", svc])
    print(f"{svc} is active.")

def verify_qemu_conf() -> bool:
    """Verify that qemu.conf has the user and group settings."""
    print("Verifying libvirt qemu.conf configuration...")

    try:
        contents = QEMU_CONF.read_text() if QEMU_CONF.exists() else ""

        user_ok = 'user = "root"' in contents
        group_ok = 'group = "root"' in contents

        print(f"  {'✓' if user_ok else '✗'} User set to root")
        print(f"  {'✓' if group_ok else '✗'} Group set to root")

        return user_ok and group_ok

    except Exception as e:
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