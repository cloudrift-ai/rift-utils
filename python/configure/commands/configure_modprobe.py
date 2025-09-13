import os
from typing import Any, Dict
from .cmd import BaseCmd

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

class CreateVfioConfCmd(BaseCmd):
    """ Command to create or update vfio.conf. """

    def name(self) -> str:
        return "Create VFIO Modprobe Config"
    
    def description(self) -> str:
        return "Creates or updates /etc/modprobe.d/vfio.conf to disable PCIe power management."

    def execute(self, env: Dict[str, Any]) -> bool:
        try:
            create_vfio_conf()
            return True
        except Exception as e:
            print(f"Error creating vfio.conf: {e}")
            return False