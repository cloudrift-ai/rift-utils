
import subprocess
from utils import run

def check_nvidia():
    """
    Check if nvidia driver is installed
    """
    
    output, _, return_code = run("lsmod | grep nvidia", shell=True, capture_output=True)
    if return_code == 0 and output:
        print("NVIDIA driver is in use.")
    else:
        print("NVIDIA driver is not in use.")
    
    return return_code == 0 and output


def remove_nvidia_driver():
    """
    Main function to check for and remove NVIDIA drivers.
    """
    # Check if the nvidia module is loaded
    if check_nvidia():
        print("NVIDIA driver is in use. Attempting to remove it.")

        # Run the NVIDIA uninstaller (if it exists)
        print("Running NVIDIA uninstaller...")
        run(["/usr/bin/nvidia-uninstall", "-s"])

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

        print("Rebooting machine now...")
        run(["reboot"])
    else:
        print("NVIDIA driver does not appear to be in use, or the command failed to run.")
        print(f"lsmod output: {output}")
