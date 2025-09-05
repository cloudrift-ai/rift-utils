
import subprocess

def run(cmd, check=True, capture_output=False, quiet_stderr=False):
    kwargs = {}
    if capture_output:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["text"] = True
    if quiet_stderr:
        kwargs["stderr"] = subprocess.DEVNULL
    return subprocess.run(cmd, check=check, **kwargs)



def apt_install(packages):
    print("Updating apt and installing packages...")
    run(["apt", "update"])
    run(["apt", "install", "-y", *packages])
