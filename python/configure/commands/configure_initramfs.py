from typing import Any, Dict

from .cmd import BaseCmd
from .utils import run

def update_initramfs():
    """
    Updates the initramfs to include any changes made to modules.
    """
    print("Updating initramfs...")
    run(['sudo', 'update-initramfs', '-u', '-k', 'all'], check=True)
    print("Initramfs updated.")

def update_initramfs_modules() -> bool:
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
            return True
        else:
            print("VFIO modules are already present in /etc/initramfs-tools/modules.")
            return False

    except FileNotFoundError:
        print(f"Error: {modules_file} not found.")
    except IOError as e:
        print(f"Error writing to {modules_file}: {e}")

    return False

class UpdateInitramfsModulesCmd(BaseCmd):
    """ Command to update initramfs modules. """

    def name(self) -> str:
        return "Update Initramfs Modules"
    
    def description(self) -> str:
        return "Ensures VFIO modules are included in initramfs."

    def execute(self, env: Dict[str, Any]) -> bool:
        try:
            if update_initramfs_modules():
                update_initramfs()
            return True
        except Exception as e:
            print(f"Error updating initramfs modules: {e}")
            return False