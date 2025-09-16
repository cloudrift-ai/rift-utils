from .cmd import BaseCmd
from pathlib import Path
from .utils import run
from typing import Any, Dict

QEMU_CONF = Path("/etc/libvirt/qemu.conf")

def ensure_qemu_conf_lines() -> bool:
    print(f"Ensuring user/group lines in {QEMU_CONF} ...")
    QEMU_CONF.parent.mkdir(parents=True, exist_ok=True)
    contents = QEMU_CONF.read_text() if QEMU_CONF.exists() else ""
    desired = 'user = "root"\n' 'group = "root"\n'
    # Append only if not already present
    if 'user = "root"' not in contents or 'group = "root"' not in contents:
        with QEMU_CONF.open("a") as f:
            f.write(desired)
        print("Appended user/group configuration.")
        return True
    else:
        print("User/group configuration already present; skipping.")
        return False

def restart_libvirtd():
    svc = "libvirtd"
    print(f"Restarting {svc} service...")
    run(["systemctl", "restart", svc])
    run(["systemctl", "is-active", "--quiet", svc])
    print(f"{svc} is active.")

class ConfigureLibvirtCmd(BaseCmd):
    """ Command to configure libvirt for virtualization. """

    def name(self) -> str:
        return "Configure Libvirt"

    def description(self) -> str:
        return "Sets up libvirt."

    def execute(self, env: Dict[str, Any]) -> bool:
        if ensure_qemu_conf_lines():
            restart_libvirtd()
        return True
    
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