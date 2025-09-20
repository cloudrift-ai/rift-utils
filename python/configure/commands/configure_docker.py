import subprocess
import os
from typing import Any, Dict
from .cmd import BaseCmd
from .utils import run

class ConfigureDockerCmd(BaseCmd):
    """Command to install and configure Docker."""

    def name(self) -> str:
        return "Configure Docker"

    def description(self) -> str:
        return "Installs Docker CE and related components from official Docker repository"

    def execute(self, env: Dict[str, Any]) -> bool:
        try:
            print("🐋 Starting Docker installation...")

            # Step 1: Uninstall conflicting packages
            print("📦 Removing conflicting packages...")
            conflicting_packages = [
                "docker.io",
                "docker-doc",
                "docker-compose",
                "docker-compose-v2",
                "podman-docker",
                "containerd",
                "runc"
            ]

            for pkg in conflicting_packages:
                try:
                    # Use --purge to remove config files and ignore if package doesn't exist
                    run(["apt-get", "remove", "-y", "--purge", pkg], check=False)
                except:
                    pass  # Package might not be installed

            # Step 2: Setup repository
            print("🔑 Setting up Docker repository...")

            # Update apt and install prerequisites
            run(["apt-get", "update"])
            run(["apt-get", "install", "-y", "ca-certificates", "curl"])

            # Create keyrings directory
            keyrings_dir = "/etc/apt/keyrings"
            if not os.path.exists(keyrings_dir):
                os.makedirs(keyrings_dir, mode=0o755)

            # Download and install Docker's GPG key
            docker_gpg_path = "/etc/apt/keyrings/docker.asc"
            run(["curl", "-fsSL", "https://download.docker.com/linux/ubuntu/gpg",
                 "-o", docker_gpg_path])
            run(["chmod", "a+r", docker_gpg_path])

            # Add Docker repository to apt sources
            print("📝 Adding Docker repository to apt sources...")

            # Get architecture and Ubuntu codename
            arch_result = subprocess.run(["dpkg", "--print-architecture"],
                                       capture_output=True, text=True, check=True)
            architecture = arch_result.stdout.strip()

            # Get Ubuntu version codename
            with open("/etc/os-release", "r") as f:
                os_release = f.read()
                for line in os_release.split('\n'):
                    if line.startswith("VERSION_CODENAME="):
                        codename = line.split('=')[1].strip('"')
                        break

            # Create Docker repository entry
            repo_entry = f"deb [arch={architecture} signed-by={docker_gpg_path}] " \
                        f"https://download.docker.com/linux/ubuntu {codename} stable"

            with open("/etc/apt/sources.list.d/docker.list", "w") as f:
                f.write(repo_entry + "\n")

            # Step 3: Install Docker packages
            print("📥 Installing Docker packages...")
            run(["apt-get", "update"])

            docker_packages = [
                "docker-ce",
                "docker-ce-cli",
                "containerd.io",
                "docker-buildx-plugin",
                "docker-compose-plugin"
            ]

            run(["apt-get", "install", "-y"] + docker_packages)

            # Step 4: Verify installation
            print("✅ Verifying Docker installation...")
            result = subprocess.run(["docker", "--version"],
                                  capture_output=True, text=True, check=True)
            print(f"   Docker version: {result.stdout.strip()}")

            # Optional: Start and enable Docker service
            run(["systemctl", "start", "docker"])
            run(["systemctl", "enable", "docker"])

            print("🎉 Docker installation completed successfully!")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install Docker: {e}")
            if hasattr(e, 'stderr') and e.stderr:
                print(f"   Error details: {e.stderr}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error during Docker installation: {e}")
            return False