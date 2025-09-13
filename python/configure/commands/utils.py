
import subprocess

CLOUDRIFT_MEDIA_MOUNT = '/media/cloudrift'

def run(cmd, check=True, capture_output=False, quiet_stderr=False, shell=False):
    kwargs = {}
    if capture_output:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["text"] = True
    if quiet_stderr:
        kwargs["stderr"] = subprocess.DEVNULL
    print(f"Running command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(cmd, check=check, shell=shell, **kwargs)
    stdout = result.stdout.strip() if capture_output and result.stdout else ""
    return stdout, result.stderr if quiet_stderr else None, result.returncode

def apt_install(packages):
    print(f"Updating apt and installing packages {packages}...")
    run(["apt", "update"])
    run(["apt", "install", "-y", *packages])

def add_mp_to_fstab(fstab_line, mount_point) -> bool:
    """
    Adds the mount point to /etc/fstab to persist across reboots.
    """
    fstab_line = f"none {mount_point} hugetlbfs pagesize=1G 0 0\n"
    try:
        # Check if the line already exists
        with open("/etc/fstab", 'r') as f:
            if fstab_line in f.read():
                print(f"Mount point '{mount_point}' already exists in /etc/fstab.")
                return True
    except FileNotFoundError:
        print("Error: /etc/fstab not found.")
        return False

    # Use sudo tee to append the line
    try:
        command = f'echo "{fstab_line}" | sudo tee -a /etc/fstab'
        run(command, check=True, shell=True)
        print(f"Successfully added '{fstab_line.strip()}' to /etc/fstab.")
    except subprocess.CalledProcessError as e:
        print(f"Error adding mount to /etc/fstab. Return code: {e.returncode}")
        return False
    
    return True