import os
from typing import Any, Dict
from .cmd import BaseCmd

def create_vfio_conf():
    """
    Creates or updates /etc/modprobe.d/99-cloudrift-vfio.conf to disable PCIe power management.
    """
    conf_dir = '/etc/modprobe.d/'
    conf_file = os.path.join(conf_dir, '99-cloudrift-vfio.conf')
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
        return "Creates or updates /etc/modprobe.d/99-cloudrift-vfio.conf to disable PCIe power management."

    def execute(self, env: Dict[str, Any]) -> bool:
        try:
            create_vfio_conf()
            return True
        except Exception as e:
            print(f"Error creating 99-cloudrift-vfio.conf: {e}")
            return False


def create_nvidia_no_drm_conf():
    """
    Creates /etc/modprobe.d/99-cloudrift-nvidia-no-drm.conf to prevent nvidia_drm and
    nvidia_modeset from loading to fix the issue of switching between container and VM mode when using OSS drivers.
    NVIDIA driver is designed so that if a container uses one GPU, all GPUs are locked and cannot be unbound.
    Blacklisting these modules fixes the problem.
    """
    conf_dir = '/etc/modprobe.d/'
    conf_file = os.path.join(conf_dir, '99-cloudrift-nvidia-no-drm.conf')
    content = """\
# Prevents NVIDIA DRM/modeset modules from loading on the host,
# allowing the GPU to be cleanly passed through to a VM
blacklist nvidia_drm
blacklist nvidia_modeset
install nvidia_drm /bin/false
install nvidia_modeset /bin/false
"""

    if not os.path.exists(conf_dir):
        os.makedirs(conf_dir)

    try:
        with open(conf_file, 'w') as f:
            f.write(content)
        print(f"Created/updated {conf_file} to block NVIDIA DRM modules.")
    except IOError as e:
        print(f"Error writing to {conf_file}: {e}")


class CreateNvidiaNoDrmConfCmd(BaseCmd):
    """ Command to create 99-cloudrift-nvidia-no-drm.conf to block NVIDIA DRM modules. """

    def name(self) -> str:
        return "Create NVIDIA No-DRM Modprobe Config"

    def description(self) -> str:
        return "Creates /etc/modprobe.d/99-cloudrift-nvidia-no-drm.conf to prevent nvidia_drm and nvidia_modeset from loading."

    def execute(self, env: Dict[str, Any]) -> bool:
        try:
            create_nvidia_no_drm_conf()
            return True
        except Exception as e:
            print(f"Error creating 99-cloudrift-nvidia-no-drm.conf: {e}")
            return False