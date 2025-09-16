

import subprocess
from typing import Any, Dict, List
from .cmd import BaseCmd
from .utils import run

class AptInstallCmd(BaseCmd):
    """ Command to install packages using apt. """
    
    def name(self) -> str:
        return "Apt Install Packages"
    
    def description(self) -> str:
        return f"Installs packages using apt ({', '.join(self.packages)})"
    
    def __init__(self, packages: List[str]):
        self.packages = packages

    def execute(self, env: Dict[str, Any]) -> bool:
        try:
            run(["apt-get", "update"])
            run(["apt-get", "install", "-y"] + self.packages)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to install packages {self.packages}: {e}")
            return False