

import subprocess
from typing import Any, Dict, List
from .cmd import BaseCmd
from .utils import run

class AptInstallCmd(BaseCmd):
    """ Command to install packages using apt. """
    
    def name(self) -> str:
        return "Apt Install Packages"
    
    def description(self) -> str:
        return f"Installs packages using apt."
    
    def execute(self, env: Dict[str, Any]) -> bool:
        packages = env.get("packages", [])
        try:
            run(["apt-get", "update"])
            if len(packages) > 0:
                print(f"Installing packages: {packages}")
                run(["apt-get", "install", "-y"] + packages)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to install packages {packages}: {e}")
            return False