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

    # Check if user and group are already set (uncommented)
    if 'user = "root"' in contents and 'group = "root"' in contents:
        print("User/group configuration already present; skipping.")
        return False

    # Process the configuration file line by line
    lines = contents.splitlines() if contents else []
    modified = False
    user_found = False
    group_found = False

    for i, line in enumerate(lines):
        # Check for commented user line
        if line.strip().startswith('#') and 'user =' in line:
            # Uncomment the line and set to root
            lines[i] = 'user = "root"'
            user_found = True
            modified = True
            print(f"Uncommented and set user = \"root\"")
        # Check for uncommented user line that's not root
        elif line.strip().startswith('user =') and 'user = "root"' not in line:
            lines[i] = 'user = "root"'
            user_found = True
            modified = True
            print(f"Updated existing user setting to root")
        elif 'user = "root"' in line:
            user_found = True

        # Check for commented group line
        if line.strip().startswith('#') and 'group =' in line:
            # Uncomment the line and set to root
            lines[i] = 'group = "root"'
            group_found = True
            modified = True
            print(f"Uncommented and set group = \"root\"")
        # Check for uncommented group line that's not root
        elif line.strip().startswith('group =') and 'group = "root"' not in line:
            lines[i] = 'group = "root"'
            group_found = True
            modified = True
            print(f"Updated existing group setting to root")
        elif 'group = "root"' in line:
            group_found = True

    # If user or group not found, append them
    if not user_found:
        lines.append('user = "root"')
        modified = True
        print("Added user = \"root\" configuration")

    if not group_found:
        lines.append('group = "root"')
        modified = True
        print("Added group = \"root\" configuration")

    # Write back if modifications were made
    if modified:
        try:
            with QEMU_CONF.open("w") as f:
                f.write('\n'.join(lines) + '\n')
            print("Updated qemu.conf configuration.")
            return True
        except Exception as e:
            print(f"Error updating qemu.conf: {e}")
            return False

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