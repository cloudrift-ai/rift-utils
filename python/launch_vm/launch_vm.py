#!/usr/bin/env python3
"""
Python version of launch_vm.sh
Creates and manages VM instances using libvirt and cloud-init.
Configuration is loaded from vm_config.yaml file.
"""

import os
import sys
import subprocess
import tempfile
import shutil
import uuid
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass

# Handle PyYAML import
try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required but not installed.")
    print("Please install it with: pip install PyYAML")
    print("Or install from requirements.txt: pip install -r requirements.txt")
    sys.exit(1)


@dataclass
class VMConfig:
    """Configuration for a single VM"""
    name: str
    vcpus: int
    ram_gb: int
    disk_gb: int
    description: str = ""


class VMManager:
    """Manages VM creation and configuration"""
    
    def __init__(self, config_file: Optional[Path] = None):
        # Load configuration from YAML file
        self.config = self._load_config(config_file)
        
        # Initialize configuration-dependent attributes
        self.ssh_pubkey = self._get_ssh_pubkey()
        self.vms = self._load_vm_configs()
        
        # Networking configuration
        self.libvirt_net_name = self.config["networking"]["libvirt_net_name"]
        self.linux_bridge_name = self.config["networking"]["linux_bridge_name"]
        
        # Base image configuration
        self.base_img_url = self.config["base_image"]["url"]
        self.base_os_variant = self.config["base_image"]["os_variant"]
        
        # Storage/working dirs
        root_dir_config = self.config["storage"]["root_dir"]
        if os.path.isabs(root_dir_config):
            self.root_dir = Path(root_dir_config)
        else:
            self.root_dir = Path.home() / root_dir_config
        
        self.img_dir = self.root_dir / self.config["storage"]["images_subdir"]
        self.vm_dir = self.root_dir / self.config["storage"]["instances_subdir"]
        
        # Hardware configuration
        self.cpu_model = self.config["hardware"]["cpu_model"]
        self.machine_opts = self.config["hardware"]["machine_opts"]
        
        self.use_libvirt_net = False
    
    def _load_config(self, config_file: Optional[Path] = None) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if config_file is None:
            # Try to find config file in the same directory as the script
            script_dir = Path(__file__).parent
            config_file = script_dir / "vm_config.yaml"
        
        if not config_file.exists():
            print(f"ERROR: Configuration file not found: {config_file}")
            print("Please create a vm_config.yaml file or specify a different config file.")
            sys.exit(1)
        
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            return config
        except yaml.YAMLError as e:
            print(f"ERROR: Failed to parse YAML configuration file: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Failed to load configuration file: {e}")
            sys.exit(1)
    
    def _load_vm_configs(self) -> List[VMConfig]:
        """Load VM configurations from the config file"""
        vm_configs = []
        for vm_data in self.config["vms"]:
            vm_config = VMConfig(
                name=vm_data["name"],
                vcpus=vm_data["vcpus"],
                ram_gb=vm_data["ram_gb"],
                disk_gb=vm_data["disk_gb"],
                description=vm_data.get("description", "")
            )
            vm_configs.append(vm_config)
        return vm_configs
    
    def _get_ssh_pubkey(self) -> str:
        """Get SSH public key from config, environment, or default location"""
        # First check if key is specified in config
        ssh_pubkey = self.config["ssh"].get("public_key", "")
        
        # If not in config, check environment variable
        if not ssh_pubkey:
            ssh_pubkey = os.environ.get("SSH_PUBKEY", "")
        
        # If still not found, check for public key file in config
        if not ssh_pubkey and "public_key_file" in self.config["ssh"]:
            key_file_path = Path(self.config["ssh"]["public_key_file"]).expanduser()
            if key_file_path.exists():
                try:
                    ssh_pubkey = key_file_path.read_text().strip()
                except Exception:
                    pass
        
        # Last resort: try default SSH key location
        if not ssh_pubkey:
            try:
                ssh_key_path = Path.home() / ".ssh" / "id_rsa.pub"
                if ssh_key_path.exists():
                    ssh_pubkey = ssh_key_path.read_text().strip()
            except Exception:
                pass
        
        return ssh_pubkey
    
    def _run_command(self, cmd: List[str], check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
        """Run a shell command"""
        try:
            result = subprocess.run(
                cmd, 
                check=check, 
                capture_output=capture_output, 
                text=True
            )
            return result
        except subprocess.CalledProcessError as e:
            if capture_output:
                print(f"Command failed: {' '.join(cmd)}")
                print(f"Exit code: {e.returncode}")
                if e.stdout:
                    print(f"Stdout: {e.stdout}")
                if e.stderr:
                    print(f"Stderr: {e.stderr}")
            raise
    
    def _need_cmd(self, cmd: str) -> None:
        """Check if a command is available"""
        if not shutil.which(cmd):
            print(f"Missing: {cmd}")
            sys.exit(1)
    
    def check_prerequisites(self) -> None:
        """Check that all required commands are available"""
        print("[*] Checking prerequisites...")
        
        required_commands = [
            "sudo", "qemu-img", "virsh", "virt-install", 
            "wget", "cloud-localds", "uuidgen"
        ]
        
        for cmd in required_commands:
            self._need_cmd(cmd)
        
        if not self.ssh_pubkey:
            print("ERROR: SSH_PUBKEY is empty. Set SSH_PUBKEY env var or ensure ~/.ssh/id_rsa.pub exists.")
            sys.exit(1)
    
    def setup_libvirt(self) -> None:
        """Ensure libvirtd is running"""
        print("[*] Ensuring libvirtd is running...")
        self._run_command(["sudo", "systemctl", "enable", "--now", "libvirtd"])
    
    def create_directories(self) -> None:
        """Create necessary directories"""
        print(f"[*] Creating directories: {self.img_dir}, {self.vm_dir}")
        self.img_dir.mkdir(parents=True, exist_ok=True)
        self.vm_dir.mkdir(parents=True, exist_ok=True)
    
    def download_base_image(self) -> Path:
        """Download base image if it doesn't exist"""
        base_img_path = self.img_dir / "noble-server-cloudimg-amd64.img"
        
        if not base_img_path.exists():
            print("[*] Downloading base image...")
            temp_path = base_img_path.with_suffix(".tmp")
            self._run_command(["wget", "-O", str(temp_path), self.base_img_url])
            temp_path.rename(base_img_path)
        
        return base_img_path
    
    def detect_network(self) -> None:
        """Detect network attachment method"""
        print("[*] Detecting network attachment method...")
        
        # Check if libvirt network exists
        try:
            result = self._run_command(
                ["virsh", "net-info", self.libvirt_net_name], 
                check=False, 
                capture_output=True
            )
            
            if result.returncode == 0:
                # Check if network is active
                net_info = result.stdout
                active = False
                for line in net_info.splitlines():
                    if "Active:" in line and "yes" in line:
                        active = True
                        break
                
                if not active:
                    print(f"[*] Starting libvirt network {self.libvirt_net_name}...")
                    self._run_command(["sudo", "virsh", "net-start", self.libvirt_net_name])
                    self._run_command(["sudo", "virsh", "net-autostart", self.libvirt_net_name])
                
                self.use_libvirt_net = True
                return
        except subprocess.CalledProcessError:
            pass
        
        # Check if Linux bridge exists
        try:
            self._run_command(
                ["ip", "link", "show", self.linux_bridge_name], 
                check=True, 
                capture_output=True
            )
            print(f"[*] Will attach directly to Linux bridge {self.linux_bridge_name}.")
            return
        except subprocess.CalledProcessError:
            pass
        
        # Neither found
        error_msg = f"""ERROR: Could not find libvirt network "{self.libvirt_net_name}" or Linux bridge "{self.linux_bridge_name}".
- Option A (recommended): define a libvirt bridge network named "{self.libvirt_net_name}" that forwards to {self.linux_bridge_name}
- Option B: create Linux bridge {self.linux_bridge_name} via netplan
Then re-run this script."""
        print(error_msg)
        sys.exit(1)
    
    def create_cloud_init(self, vm_config: VMConfig) -> Path:
        """Create cloud-init configuration for a VM"""
        vmwork = self.vm_dir / vm_config.name
        cloudinit_dir = vmwork / "cloudinit"
        cloudinit_dir.mkdir(parents=True, exist_ok=True)
        
        # Create user-data using configuration values
        cloud_init_config = self.config["cloud_init"]
        packages = "\n".join([f"  - {pkg}" for pkg in cloud_init_config["packages"]])
        
        user_data = f"""#cloud-config
hostname: {vm_config.name}
manage_etc_hosts: true
users:
  - name: {cloud_init_config["default_user"]}
    groups: [sudo]
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - {self.ssh_pubkey}
package_update: {str(cloud_init_config["package_update"]).lower()}
packages:
{packages}
runcmd:
  - [ systemctl, enable, --now, qemu-guest-agent ]
  - [ timedatectl, set-timezone, {cloud_init_config["timezone"]} ]
# Uncomment and edit if you want static IP (example):
#network:
#  version: 2
#  ethernets:
#    ens3:
#      dhcp4: true
"""
        
        user_data_path = cloudinit_dir / "user-data"
        user_data_path.write_text(user_data)
        
        # Create meta-data
        meta_data = f"""instance-id: {uuid.uuid4()}
local-hostname: {vm_config.name}
"""
        
        meta_data_path = cloudinit_dir / "meta-data"
        meta_data_path.write_text(meta_data)
        
        # Create ISO seed
        seed_path = vmwork / f"{vm_config.name}-seed.iso"
        self._run_command([
            "cloud-localds", 
            str(seed_path),
            str(user_data_path),
            str(meta_data_path)
        ])
        
        return seed_path
    
    def create_vm(self, vm_config: VMConfig, base_img_path: Path) -> None:
        """Create and start a VM"""
        vmwork = self.vm_dir / vm_config.name
        disk_path = vmwork / f"{vm_config.name}.qcow2"
        
        vmwork.mkdir(parents=True, exist_ok=True)
        
        # Check if VM already exists
        try:
            self._run_command(
                ["virsh", "dominfo", vm_config.name], 
                check=True, 
                capture_output=True
            )
            print(f"[*] VM {vm_config.name} already defined. Skipping define.")
        except subprocess.CalledProcessError:
            # VM doesn't exist, create it
            
            # Create disk if it doesn't exist
            if not disk_path.exists():
                print(f"[*] Preparing disk for {vm_config.name} ({vm_config.disk_gb}G, CoW backing {base_img_path})")
                self._run_command([
                    "qemu-img", "create", 
                    "-f", "qcow2",
                    "-F", "qcow2", 
                    "-b", str(base_img_path),
                    str(disk_path),
                    f"{vm_config.disk_gb}G"
                ])
            
            # Create cloud-init seed
            print(f"[*] Creating cloud-init seed for {vm_config.name}")
            seed_path = self.create_cloud_init(vm_config)
            
            # Build virt-install command
            print(f"[*] Defining & starting VM {vm_config.name}")
            
            virt_install_cmd = [
                "sudo", "virt-install",
                "--name", vm_config.name,
                "--memory", str(vm_config.ram_gb * 1024),
                "--vcpus", str(vm_config.vcpus),
                "--cpu", self.cpu_model,
                "--disk", f"path={disk_path},format=qcow2,discard=unmap",
                "--disk", f"path={seed_path},device=cdrom",
                "--os-variant", self.base_os_variant,
                "--import",
                "--graphics", "none",
                "--controller", "type=scsi,model=virtio-scsi",
                "--machine", self.machine_opts,
                "--noautoconsole"
            ]
            
            # Add network configuration
            if self.use_libvirt_net:
                virt_install_cmd.extend([
                    "--network", f"network={self.libvirt_net_name},model=virtio"
                ])
            else:
                virt_install_cmd.extend([
                    "--network", f"bridge={self.linux_bridge_name},model=virtio"
                ])
            
            self._run_command(virt_install_cmd)
        
        # Ensure VM is running
        print(f"[*] Ensuring {vm_config.name} is running...")
        try:
            self._run_command(
                ["sudo", "virsh", "start", vm_config.name], 
                check=False, 
                capture_output=True
            )
        except subprocess.CalledProcessError:
            pass  # VM might already be running
    
    def print_config_summary(self) -> None:
        """Print a summary of the loaded configuration"""
        print("[*] Configuration Summary:")
        print(f"    Network: {self.libvirt_net_name} (libvirt) or {self.linux_bridge_name} (bridge)")
        print(f"    Base Image: {self.base_img_url}")
        print(f"    Storage: {self.root_dir}")
        print(f"    VMs to create: {len(self.vms)}")
        for vm in self.vms:
            desc = f" ({vm.description})" if vm.description else ""
            print(f"      - {vm.name}: {vm.vcpus}v/{vm.ram_gb}GB RAM/{vm.disk_gb}GB disk{desc}")
        print()
    
    def run(self, dry_run: bool = False) -> None:
        """Main execution function"""
        self.print_config_summary()
        
        if dry_run:
            print("[*] Dry run mode - configuration loaded successfully!")
            return
            
        self.check_prerequisites()
        self.setup_libvirt()
        self.create_directories()
        base_img_path = self.download_base_image()
        self.detect_network()
        
        print("[*] Creating VMs...")
        for vm_config in self.vms:
            self.create_vm(vm_config, base_img_path)
        
        print()
        print("===============================================")
        print(" All done! Your VMs should boot in a few secs.")
        print(" Tips:")
        print("   - List VMs:            virsh list --all")
        print("   - Get IPs (example):   virsh domifaddr api-vm")
        print("   - Serial console:      virsh console api-vm  (Ctrl-])")
        print("   - Shutdown a VM:       virsh shutdown web-vm")
        print("   - Delete a VM:         virsh destroy web-vm; virsh undefine --remove-all-storage web-vm")
        print("   - Edit config:         vi vm_config.yaml")
        print("===============================================")


def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Create and manage VM instances using libvirt and cloud-init"
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        help="Path to YAML configuration file (default: vm_config.yaml in script directory)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load and validate configuration without creating VMs"
    )
    
    args = parser.parse_args()
    
    try:
        vm_manager = VMManager(config_file=args.config)
        vm_manager.run(dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()