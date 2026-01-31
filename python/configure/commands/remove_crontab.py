import subprocess
from typing import Any, Dict
from .cmd import BaseCmd
from .utils import run


class RemoveCrontabCmd(BaseCmd):
    """Command to remove the root crontab."""

    def name(self) -> str:
        return "Remove Crontab"

    def description(self) -> str:
        return "Removes the root user's crontab entries"

    def execute(self, env: Dict[str, Any]) -> bool:
        try:
            # Check if there's an existing crontab
            result = subprocess.run(
                ["crontab", "-l"],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print("No crontab found for root user. Nothing to remove.")
                return True

            # Show existing crontab before removal
            print("Current crontab entries:")
            print(result.stdout)

            # Remove the crontab
            print("Removing root crontab...")
            run(["crontab", "-r"], check=True)
            print("Root crontab removed successfully.")
            return True

        except subprocess.CalledProcessError as e:
            print(f"Failed to remove crontab: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error removing crontab: {e}")
            return False
