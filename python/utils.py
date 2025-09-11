
import subprocess

def run(cmd, check=True, capture_output=False, quiet_stderr=False, shell=False):
    kwargs = {}
    if capture_output:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["text"] = True
    if quiet_stderr:
        kwargs["stderr"] = subprocess.DEVNULL
    result = subprocess.run(cmd, check=check, shell=shell, **kwargs)
    stdout = result.stdout.strip() if capture_output and result.stdout else ""
    return stdout, result.stderr if quiet_stderr else None, result.returncode

def apt_install(packages):
    print("Updating apt and installing packages...")
    run(["apt", "update"])
    run(["apt", "install", "-y", *packages])
