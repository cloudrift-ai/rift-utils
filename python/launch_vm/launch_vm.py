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
import time
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
        self.network_mode = self.config["networking"].get("mode", "auto")
        self.libvirt_net_name = self.config["networking"].get("libvirt_net_name", "default")
        self.linux_bridge_name = self.config["networking"].get("linux_bridge_name", "br0")
        self.nat_config = self.config["networking"].get("nat", {})
        self.bridge_config = self.config["networking"].get("bridge", {})
        self.macvtap_config = self.config["networking"].get("macvtap", {})
        
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
        self.virt_type = self.config["hardware"].get("virt_type", "kvm")
        self.fallback_machine_opts = self.config["hardware"].get("fallback_machine_opts", "pc,accel=tcg")
        self.fallback_virt_type = self.config["hardware"].get("fallback_virt_type", "qemu")
        
        self.use_libvirt_net = False
        self.use_nat_network = False
        self.use_macvtap = False
        self.macvtap_interface = None  # Will be set when macvtap is created
        self.network_type = None  # Will be set by detect_network()
    
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
                else:
                    ssh_key_path = Path.home() / ".ssh" / "id_ed25519.pub"
                    if ssh_key_path.exists():
                        ssh_pubkey = ssh_key_path.read_text().strip()                
            except Exception:
                pass
        
        return ssh_pubkey
    
    def _create_nat_network(self) -> None:
        """Create NAT network if it doesn't exist"""
        nat_config = self.nat_config
        network_name = nat_config.get("network_name", "vm-nat")
        
        # Check if NAT network already exists
        try:
            result = self._run_command(
                ["virsh", "net-info", network_name],
                check=False,
                capture_output=True
            )
            if result.returncode == 0:
                print(f"[*] NAT network '{network_name}' already exists")
                # Ensure it's active
                net_info = result.stdout
                active = any("Active:" in line and "yes" in line for line in net_info.splitlines())
                if not active:
                    print(f"[*] Starting NAT network {network_name}...")
                    self._run_command(["sudo", "virsh", "net-start", network_name])
                    self._run_command(["sudo", "virsh", "net-autostart", network_name])
                return
        except subprocess.CalledProcessError:
            pass
        
        # Create NAT network XML
        subnet = nat_config.get("subnet", "192.168.100.0/24")
        gateway = nat_config.get("gateway", "192.168.100.1")
        dhcp_start = nat_config.get("dhcp_start", "192.168.100.10")
        dhcp_end = nat_config.get("dhcp_end", "192.168.100.100")
        forward_mode = nat_config.get("forward_mode", "nat")
        forward_dev = nat_config.get("forward_dev", "")
        
        # Create network XML
        forward_xml = f'<forward mode="{forward_mode}"'
        if forward_dev:
            forward_xml += f' dev="{forward_dev}"'
        forward_xml += '/>'
        
        network_xml = f"""<network>
  <name>{network_name}</name>
  <uuid>{uuid.uuid4()}</uuid>
  {forward_xml}
  <bridge name="virbr-{network_name}" stp="on" delay="0"/>
  <ip address="{gateway}" netmask="{self._cidr_to_netmask(subnet)}">
    <dhcp>
      <range start="{dhcp_start}" end="{dhcp_end}"/>
    </dhcp>
  </ip>
</network>"""
        
        # Create temporary XML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
            f.write(network_xml)
            xml_file = f.name
        
        try:
            print(f"[*] Creating NAT network '{network_name}' with subnet {subnet}...")
            self._run_command(["sudo", "virsh", "net-define", xml_file])
            self._run_command(["sudo", "virsh", "net-start", network_name])
            self._run_command(["sudo", "virsh", "net-autostart", network_name])
            print(f"[*] NAT network '{network_name}' created and started")
        finally:
            # Clean up temporary file
            Path(xml_file).unlink(missing_ok=True)
    
    def _cidr_to_netmask(self, cidr: str) -> str:
        """Convert CIDR notation to netmask (e.g., '192.168.100.0/24' -> '255.255.255.0')"""
        if '/' not in cidr:
            return "255.255.255.0"  # Default netmask
        
        prefix_len = int(cidr.split('/')[1])
        mask = (0xffffffff >> (32 - prefix_len)) << (32 - prefix_len)
        return f"{(mask >> 24) & 0xff}.{(mask >> 16) & 0xff}.{(mask >> 8) & 0xff}.{mask & 0xff}"
    
    def _create_bridge_network(self) -> None:
        """Create Linux bridge network if it doesn't exist"""
        bridge_config = self.bridge_config
        bridge_name = bridge_config.get("bridge_name", "vmbr0")
        physical_interface = bridge_config.get("physical_interface", "")
        
        if not physical_interface:
            print("ERROR: physical_interface must be specified in bridge configuration")
            sys.exit(1)
        
        # Check if bridge already exists
        try:
            self._run_command(
                ["ip", "link", "show", bridge_name],
                check=True,
                capture_output=True
            )
            print(f"[*] Bridge '{bridge_name}' already exists")
            return
        except subprocess.CalledProcessError:
            pass
        
        # Check if physical interface exists
        try:
            self._run_command(
                ["ip", "link", "show", physical_interface],
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError:
            print(f"ERROR: Physical interface '{physical_interface}' not found")
            print("Available interfaces:")
            result = self._run_command(["ip", "link", "show"], check=False, capture_output=True)
            if result.stdout:
                for line in result.stdout.splitlines():
                    if ": " in line and not line.strip().startswith("lo:"):
                        interface = line.split(":")[1].strip().split("@")[0]
                        if interface != "lo":
                            print(f"  - {interface}")
            sys.exit(1)
        
        use_netplan = bridge_config.get("use_netplan", True)
        
        if use_netplan:
            self._create_bridge_via_netplan(bridge_name, physical_interface)
        else:
            self._create_bridge_via_commands(bridge_name, physical_interface)
    
    def _create_bridge_via_netplan(self, bridge_name: str, physical_interface: str) -> None:
        """Create bridge network via netplan configuration"""
        bridge_config = self.bridge_config
        ip_address = bridge_config.get("ip_address", "")
        gateway = bridge_config.get("gateway", "")
        dns_servers = bridge_config.get("dns_servers", [])
        use_dhcp = bridge_config.get("use_dhcp", True)
        
        # Create netplan configuration
        netplan_config = {
            "network": {
                "version": 2,
                "ethernets": {
                    physical_interface: {}  # Remove IP from physical interface
                },
                "bridges": {
                    bridge_name: {
                        "interfaces": [physical_interface]
                    }
                }
            }
        }
        
        # Configure bridge IP
        if ip_address and not use_dhcp:
            netplan_config["network"]["bridges"][bridge_name]["addresses"] = [ip_address]
            if gateway:
                netplan_config["network"]["bridges"][bridge_name]["gateway4"] = gateway
            if dns_servers:
                netplan_config["network"]["bridges"][bridge_name]["nameservers"] = {
                    "addresses": dns_servers
                }
        elif use_dhcp:
            netplan_config["network"]["bridges"][bridge_name]["dhcp4"] = True
        
        # Write netplan configuration
        netplan_file = f"/etc/netplan/50-{bridge_name}.yaml"
        
        print(f"[*] Creating bridge '{bridge_name}' via netplan...")
        print(f"[*] This will modify network configuration and may interrupt connectivity!")
        print(f"[*] Netplan config will be written to: {netplan_file}")
        
        import tempfile
        import yaml
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(netplan_config, f, default_flow_style=False)
            temp_file = f.name
        
        try:
            # Copy netplan file
            self._run_command(["sudo", "cp", temp_file, netplan_file])
            self._run_command(["sudo", "chmod", "600", netplan_file])
            
            # Apply netplan configuration
            print(f"[*] Applying netplan configuration...")
            self._run_command(["sudo", "netplan", "apply"])
            
            print(f"[*] Bridge '{bridge_name}' created successfully via netplan")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to create bridge via netplan: {e}")
            print("You may need to manually configure the bridge or check your netplan syntax")
            sys.exit(1)
        finally:
            Path(temp_file).unlink(missing_ok=True)
    
    def _create_bridge_via_commands(self, bridge_name: str, physical_interface: str) -> None:
        """Create bridge network via manual commands (temporary until reboot)"""
        bridge_config = self.bridge_config
        ip_address = bridge_config.get("ip_address", "")
        use_dhcp = bridge_config.get("use_dhcp", True)
        
        print(f"[*] Creating bridge '{bridge_name}' via manual commands...")
        print("[*] WARNING: This configuration is temporary and will not persist after reboot!")
        
        try:
            # Create bridge
            self._run_command(["sudo", "ip", "link", "add", "name", bridge_name, "type", "bridge"])
            
            # Add physical interface to bridge
            self._run_command(["sudo", "ip", "link", "set", "dev", physical_interface, "master", bridge_name])
            
            # Bring up bridge
            self._run_command(["sudo", "ip", "link", "set", "dev", bridge_name, "up"])
            
            # Configure IP if specified
            if ip_address and not use_dhcp:
                self._run_command(["sudo", "ip", "addr", "add", ip_address, "dev", bridge_name])
            elif use_dhcp:
                # Try to get DHCP lease on bridge
                self._run_command(["sudo", "dhclient", bridge_name], check=False)
            
            print(f"[*] Bridge '{bridge_name}' created successfully")
            print("[*] To make this permanent, consider using netplan configuration")
            
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to create bridge via commands: {e}")
            sys.exit(1)
    
    def _create_macvtap_interface(self) -> str:
        """Create macvtap interface and return its name"""
        macvtap_config = self.macvtap_config
        physical_interface = macvtap_config.get("physical_interface", "")
        mode = macvtap_config.get("mode", "bridge")
        interface_prefix = macvtap_config.get("interface_prefix", "macvtap")
        
        if not physical_interface:
            print("ERROR: physical_interface must be specified in macvtap configuration")
            sys.exit(1)
        
        # Check if physical interface exists
        try:
            self._run_command(
                ["ip", "link", "show", physical_interface],
                check=True,
                capture_output=True
            )
        except subprocess.CalledProcessError:
            print(f"ERROR: Physical interface '{physical_interface}' not found for macvtap")
            print("Available interfaces:")
            result = self._run_command(["ip", "link", "show"], check=False, capture_output=True)
            if result.stdout:
                for line in result.stdout.splitlines():
                    if ": " in line and not line.strip().startswith("lo:"):
                        interface = line.split(":")[1].strip().split("@")[0]
                        if interface != "lo":
                            print(f"  - {interface}")
            sys.exit(1)
        
        # Find available macvtap interface name
        macvtap_interface = None
        for i in range(100):  # Try up to macvtap99
            candidate = f"{interface_prefix}{i}"
            try:
                self._run_command(
                    ["ip", "link", "show", candidate],
                    check=True,
                    capture_output=True
                )
                # Interface exists, try next number
                continue
            except subprocess.CalledProcessError:
                # Interface doesn't exist, we can use this name
                macvtap_interface = candidate
                break
        
        if not macvtap_interface:
            print(f"ERROR: Could not find available macvtap interface name (tried {interface_prefix}0-{interface_prefix}99)")
            sys.exit(1)
        
        # Create macvtap interface
        print(f"[*] Creating macvtap interface '{macvtap_interface}' on '{physical_interface}' in {mode} mode...")
        
        try:
            # Create macvtap interface
            self._run_command([
                "sudo", "ip", "link", "add", "link", physical_interface,
                "name", macvtap_interface, "type", "macvtap", "mode", mode
            ])
            
            # Bring up the interface
            self._run_command([
                "sudo", "ip", "link", "set", "dev", macvtap_interface, "up"
            ])
            
            print(f"[*] Macvtap interface '{macvtap_interface}' created successfully")
            return macvtap_interface
            
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to create macvtap interface: {e}")
            sys.exit(1)
    
    def _cleanup_macvtap_interface(self, interface_name: str) -> None:
        """Clean up macvtap interface"""
        try:
            print(f"[*] Cleaning up macvtap interface '{interface_name}'...")
            self._run_command([
                "sudo", "ip", "link", "delete", interface_name
            ], check=False)  # Don't fail if interface doesn't exist
        except Exception as e:
            print(f"[!] Could not clean up macvtap interface '{interface_name}': {e}")
    
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
        
        # Check KVM availability if using KVM
        if self.virt_type == "kvm":
            self._check_kvm_availability()
    
    def _check_kvm_availability(self) -> None:
        """Check if KVM is available and suggest alternatives if not"""
        kvm_available = False
        
        # Check if /dev/kvm exists
        if Path("/dev/kvm").exists():
            # Check if user has access to KVM
            try:
                self._run_command(["test", "-r", "/dev/kvm", "-a", "-w", "/dev/kvm"], check=True, capture_output=True)
                kvm_available = True
                print("[*] KVM acceleration available")
            except subprocess.CalledProcessError:
                print("[!] KVM device exists but not accessible. You may need to:")
                print("    - Add your user to the 'kvm' group: sudo usermod -a -G kvm $USER")
                print("    - Log out and back in for group changes to take effect")
        else:
            print("[!] KVM not available (/dev/kvm not found)")
        
        if not kvm_available:
            print("[*] Will use fallback virtualization settings:")
            print(f"    - Virtualization type: {self.fallback_virt_type}")
            print(f"    - Machine options: {self.fallback_machine_opts}")
            # Update settings to use fallback
            self.virt_type = self.fallback_virt_type
            self.machine_opts = self.fallback_machine_opts
            if self.fallback_virt_type == "qemu":
                # Use a safer CPU model for QEMU emulation
                if self.cpu_model == "host-passthrough":
                    self.cpu_model = "qemu64"
    
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
        """Detect and configure network attachment method"""
        print(f"[*] Configuring network (mode: {self.network_mode})...")
        
        # Handle explicit network mode settings
        if self.network_mode == "nat":
            self._setup_nat_network()
            return
        elif self.network_mode == "libvirt":
            self._setup_libvirt_network()
            return  
        elif self.network_mode == "bridge":
            self._setup_bridge_network()
            return
        elif self.network_mode == "macvtap":
            self._setup_macvtap_network()
            return
        
        # Auto mode - try in order of preference: libvirt -> bridge -> macvtap -> nat
        if self.network_mode == "auto":
            # Try libvirt network first
            if self._try_libvirt_network():
                return
            
            # Try Linux bridge (existing)
            if self._try_bridge_network():
                return
            
            # Try configured bridge creation if available
            if self.bridge_config:
                bridge_name = self.bridge_config.get("bridge_name", "vmbr0")
                if not self._try_bridge_network_by_name(bridge_name):
                    print(f"[*] Creating bridge '{bridge_name}' as configured...")
                    try:
                        self._create_bridge_network()
                        self.linux_bridge_name = bridge_name
                        self.network_type = "bridge"
                        print(f"[*] Using created Linux bridge: {bridge_name}")
                        return
                    except Exception as e:
                        print(f"[*] Bridge creation failed: {e}, trying macvtap...")
            
            # Try macvtap if configured
            if self.macvtap_config:
                physical_interface = self.macvtap_config.get("physical_interface", "")
                if physical_interface:
                    try:
                        print(f"[*] Creating macvtap on '{physical_interface}' as configured...")
                        self._setup_macvtap_network()
                        return
                    except Exception as e:
                        print(f"[*] Macvtap creation failed: {e}, falling back to NAT")
            
            # Fallback to creating NAT network
            print("[*] No existing networks found, creating NAT network as fallback...")
            self._setup_nat_network()
            return
        
        # Invalid network mode
        print(f"ERROR: Invalid network mode '{self.network_mode}'. Valid options: auto, libvirt, bridge, macvtap, nat")
        sys.exit(1)
    
    def _setup_nat_network(self) -> None:
        """Set up NAT network"""
        self._create_nat_network()
        self.use_nat_network = True
        self.network_type = "nat"
        print(f"[*] Using NAT network: {self.nat_config.get('network_name', 'vm-nat')}")
    
    def _setup_libvirt_network(self) -> None:
        """Set up libvirt network (must exist)"""
        if not self._try_libvirt_network():
            print(f"ERROR: Libvirt network '{self.libvirt_net_name}' not found or could not be started.")
            sys.exit(1)
    
    def _setup_bridge_network(self) -> None:
        """Set up Linux bridge network (create if configured)"""
        # First try the configured linux_bridge_name
        if self._try_bridge_network_by_name(self.linux_bridge_name):
            return
            
        # If not found and we have bridge config, try to create it
        if self.bridge_config:
            bridge_name = self.bridge_config.get("bridge_name", "vmbr0")
            # Try the configured bridge name first
            if self._try_bridge_network_by_name(bridge_name):
                # Update linux_bridge_name to the found bridge
                self.linux_bridge_name = bridge_name
                return
            
            # Create the bridge if it doesn't exist
            self._create_bridge_network()
            # Update linux_bridge_name to the newly created bridge
            self.linux_bridge_name = bridge_name
            self.network_type = "bridge"
            print(f"[*] Using created Linux bridge: {bridge_name}")
        else:
            print(f"ERROR: Linux bridge '{self.linux_bridge_name}' not found and no bridge configuration provided.")
            print("Either create the bridge manually or add bridge configuration to create it automatically.")
            sys.exit(1)
    
    def _setup_macvtap_network(self) -> None:
        """Set up macvtap network"""
        if not self.macvtap_config:
            print("ERROR: Macvtap mode selected but no macvtap configuration provided.")
            sys.exit(1)
        
        # Create macvtap interface if auto_create is enabled
        auto_create = self.macvtap_config.get("auto_create", True)
        if auto_create:
            self.macvtap_interface = self._create_macvtap_interface()
        else:
            # User must provide existing macvtap interface name
            interface_name = self.macvtap_config.get("interface_name", "")
            if not interface_name:
                print("ERROR: auto_create is disabled but no interface_name provided in macvtap configuration")
                sys.exit(1)
            
            # Verify the interface exists
            try:
                self._run_command(
                    ["ip", "link", "show", interface_name],
                    check=True,
                    capture_output=True
                )
                self.macvtap_interface = interface_name
                print(f"[*] Using existing macvtap interface: {interface_name}")
            except subprocess.CalledProcessError:
                print(f"ERROR: Specified macvtap interface '{interface_name}' not found")
                sys.exit(1)
        
        self.use_macvtap = True
        self.network_type = "macvtap"
        physical_interface = self.macvtap_config.get("physical_interface", "")
        mode = self.macvtap_config.get("mode", "bridge")
        print(f"[*] Using macvtap network: {self.macvtap_interface} -> {physical_interface} (mode: {mode})")
    
    def _try_libvirt_network(self) -> bool:
        """Try to use libvirt network, return True if successful"""
        try:
            result = self._run_command(
                ["virsh", "net-info", self.libvirt_net_name], 
                check=False, 
                capture_output=True
            )
            
            if result.returncode == 0:
                # Check if network is active
                net_info = result.stdout
                active = any("Active:" in line and "yes" in line for line in net_info.splitlines())
                
                if not active:
                    print(f"[*] Starting libvirt network {self.libvirt_net_name}...")
                    self._run_command(["sudo", "virsh", "net-start", self.libvirt_net_name])
                    self._run_command(["sudo", "virsh", "net-autostart", self.libvirt_net_name])
                
                self.use_libvirt_net = True
                self.network_type = "libvirt"
                print(f"[*] Using libvirt network: {self.libvirt_net_name}")
                return True
        except subprocess.CalledProcessError:
            pass
        
        return False
    
    def _try_bridge_network(self) -> bool:
        """Try to use Linux bridge, return True if successful"""
        return self._try_bridge_network_by_name(self.linux_bridge_name)
    
    def _try_bridge_network_by_name(self, bridge_name: str) -> bool:
        """Try to use specific Linux bridge by name, return True if successful"""
        try:
            self._run_command(
                ["ip", "link", "show", bridge_name], 
                check=True, 
                capture_output=True
            )
            self.network_type = "bridge"
            print(f"[*] Using Linux bridge: {bridge_name}")
            return True
        except subprocess.CalledProcessError:
            pass
        
        return False
    
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

    def virt_install_vm(self, vm_config: VMConfig, base_img_path: Path, disk_path: Path) -> None:
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
            "--virt-type", self.virt_type,
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
        elif self.use_nat_network:
            nat_network_name = self.nat_config.get("network_name", "vm-nat")
            virt_install_cmd.extend([
                "--network", f"network={nat_network_name},model=virtio"
            ])
        elif self.use_macvtap:
            # For macvtap, we use the type=direct with the physical interface
            physical_interface = self.macvtap_config.get("physical_interface", "")
            mode = self.macvtap_config.get("mode", "bridge")
            virt_install_cmd.extend([
                "--network", f"type=direct,source={physical_interface},source_mode={mode},model=virtio"
            ])
        else:
            virt_install_cmd.extend([
                "--network", f"bridge={self.linux_bridge_name},model=virtio"
            ])
        
        try:
            self._run_command(virt_install_cmd)
        except subprocess.CalledProcessError as e:
            if self.virt_type == "kvm" and "domain type" in str(e):
                print(f"[!] KVM virtualization failed, trying fallback with {self.fallback_virt_type}...")
                # Rebuild command with fallback settings
                virt_install_cmd_fallback = virt_install_cmd.copy()
                # Update virt-type
                virt_type_index = virt_install_cmd_fallback.index("--virt-type") + 1
                virt_install_cmd_fallback[virt_type_index] = self.fallback_virt_type
                # Update machine options
                machine_index = virt_install_cmd_fallback.index("--machine") + 1
                virt_install_cmd_fallback[machine_index] = self.fallback_machine_opts
                # Update CPU model if needed
                if self.fallback_virt_type == "qemu" and self.cpu_model == "host-passthrough":
                    cpu_index = virt_install_cmd_fallback.index("--cpu") + 1
                    virt_install_cmd_fallback[cpu_index] = "qemu64"
                
                self._run_command(virt_install_cmd_fallback)
            else:
                raise

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
            self.virt_install_vm(vm_config, base_img_path, disk_path)            
        
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
        print(f"    Network Mode: {self.network_mode}")
        if self.network_mode == "nat" or (self.network_mode == "auto" and self.nat_config):
            nat_subnet = self.nat_config.get("subnet", "192.168.100.0/24")
            nat_name = self.nat_config.get("network_name", "vm-nat")
            print(f"    NAT Network: {nat_name} ({nat_subnet})")
        if self.network_mode in ["libvirt", "auto"]:
            print(f"    Libvirt Network: {self.libvirt_net_name}")
        if self.network_mode in ["bridge", "auto"]:
            print(f"    Linux Bridge: {self.linux_bridge_name}")
            if self.bridge_config:
                bridge_name = self.bridge_config.get("bridge_name", "vmbr0")
                physical_if = self.bridge_config.get("physical_interface", "")
                print(f"    Bridge Config: {bridge_name} -> {physical_if}")
        if self.network_mode in ["macvtap", "auto"]:
            if self.macvtap_config:
                physical_if = self.macvtap_config.get("physical_interface", "")
                mode = self.macvtap_config.get("mode", "bridge")
                print(f"    Macvtap Config: {physical_if} (mode: {mode})")
        print(f"    Base Image: {self.base_img_url}")
        print(f"    Storage: {self.root_dir}")
        print(f"    Virtualization: {self.virt_type} ({self.machine_opts})")
        print(f"    CPU Model: {self.cpu_model}")
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
        print("   - List networks:       virsh net-list --all")
        if self.use_nat_network:
            nat_name = self.nat_config.get("network_name", "vm-nat")
            print(f"   - NAT network info:    virsh net-info {nat_name}")
            print(f"   - NAT DHCP leases:     virsh net-dhcp-leases {nat_name}")
        if self.use_macvtap:
            physical_if = self.macvtap_config.get("physical_interface", "")
            print(f"   - Macvtap interface:   ip link show {physical_if}")
            print(f"   - Macvtap stats:       ip -s link show {physical_if}")
        print("   - Edit config:         vi vm_config.yaml")
        print("===============================================")

    def list_created_vms(self):
        """List all VMs that match our naming convention."""
        try:
            result = subprocess.run(['virsh', 'list', '--all', '--name'], 
                                  capture_output=True, text=True, check=True)
            all_vms = [vm.strip() for vm in result.stdout.split('\n') if vm.strip()]
            
            # Filter VMs that match our naming convention from the config
            created_vms = []
            for vm_config in self.config.get('vms', []):
                vm_name = vm_config.get('name')
                if vm_name and vm_name in all_vms:
                    created_vms.append(vm_name)
            
            return created_vms
        except subprocess.CalledProcessError as e:
            print(f"Failed to list VMs: {e}")
            return []
    
    def destroy_vm(self, vm_name):
        """Destroy a single VM and its associated resources."""
        print(f"Destroying VM: {vm_name}")
        
        # First, try to shutdown gracefully, then force destroy
        try:
            subprocess.run(['virsh', 'shutdown', vm_name], 
                         capture_output=True, text=True, check=False)
            # Wait a moment for graceful shutdown
            time.sleep(5)
        except:
            pass
        
        # Force destroy if still running
        try:
            subprocess.run(['virsh', 'destroy', vm_name], 
                         capture_output=True, text=True, check=False)
        except:
            pass
        
        # Undefine the domain
        try:
            result = subprocess.run(['virsh', 'undefine', vm_name, '--remove-all-storage'], 
                                  capture_output=True, text=True, check=False)
            if result.returncode == 0:
                print(f"Successfully undefined VM: {vm_name}")
            else:
                print(f"Warning: Failed to undefine VM {vm_name}: {result.stderr}")
        except Exception as e:
            print(f"Error undefining VM {vm_name}: {e}")
    
    def cleanup_networks(self):
        """Clean up networks created by this configuration."""
        networking = self.config.get('networking', {})
        
        # Cleanup libvirt networks
        if networking.get('mode') == 'libvirt':
            network_name = networking.get('libvirt_network', 'default')
            if network_name != 'default':  # Don't destroy the default network
                self.cleanup_libvirt_network(network_name)
        
        # Cleanup bridge networks
        elif networking.get('mode') == 'bridge':
            bridge_name = networking.get('bridge_name')
            if bridge_name:
                self.cleanup_bridge_network(bridge_name)
        
        # Cleanup NAT networks
        elif networking.get('mode') == 'nat':
            nat_config = networking.get('nat', {})
            network_name = nat_config.get('name', 'vm-nat')
            if network_name != 'default':  # Don't destroy the default network
                self.cleanup_libvirt_network(network_name)
    
    def cleanup_libvirt_network(self, network_name):
        """Remove a libvirt network."""
        try:
            # Check if network exists
            result = subprocess.run(['virsh', 'net-list', '--all'], 
                                  capture_output=True, text=True, check=True)
            if network_name not in result.stdout:
                print(f"Network {network_name} does not exist")
                return
            
            # Destroy and undefine network
            subprocess.run(['virsh', 'net-destroy', network_name], 
                         capture_output=True, text=True, check=False)
            subprocess.run(['virsh', 'net-undefine', network_name], 
                         capture_output=True, text=True, check=False)
            print(f"Cleaned up libvirt network: {network_name}")
        except Exception as e:
            print(f"Warning: Failed to cleanup network {network_name}: {e}")
    
    def cleanup_bridge_network(self, bridge_name):
        """Remove a bridge network."""
        try:
            # Check if bridge exists
            result = subprocess.run(['ip', 'link', 'show', bridge_name], 
                                  capture_output=True, text=True, check=False)
            if result.returncode != 0:
                print(f"Bridge {bridge_name} does not exist")
                return
            
            # Bring down and delete bridge
            subprocess.run(['sudo', 'ip', 'link', 'set', bridge_name, 'down'], 
                         capture_output=True, text=True, check=False)
            subprocess.run(['sudo', 'brctl', 'delbr', bridge_name], 
                         capture_output=True, text=True, check=False)
            print(f"Cleaned up bridge network: {bridge_name}")
        except Exception as e:
            print(f"Warning: Failed to cleanup bridge {bridge_name}: {e}")
    
    def destroy_all_vms(self, force=False):
        """Destroy all VMs and cleanup associated resources."""
        created_vms = self.list_created_vms()
        
        if not created_vms:
            print("No VMs found matching the configuration.")
            return
        
        print(f"Found {len(created_vms)} VMs to destroy:")
        for vm in created_vms:
            print(f"  - {vm}")
        
        if not force:
            response = input("\nAre you sure you want to destroy ALL these VMs? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("Operation cancelled.")
                return
        
        print(f"\nDestroying {len(created_vms)} VMs...")
        for vm_name in created_vms:
            self.destroy_vm(vm_name)
        
        # Cleanup networks
        print("\nCleaning up networks...")
        self.cleanup_networks()
        
        print(f"\nCleanup completed. Destroyed {len(created_vms)} VMs and cleaned up networks.")


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
    parser.add_argument(
        "--list-interfaces",
        action="store_true",
        help="List available network interfaces for bridge configuration"
    )
    parser.add_argument(
        "--check-virt",
        action="store_true",
        help="Check virtualization capabilities and requirements"
    )
    parser.add_argument(
        "--destroy-all",
        action="store_true",
        help="Destroy and cleanup all VMs created by this configuration"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompts (use with --destroy-all)"
    )
    
    args = parser.parse_args()
    
    # Handle list interfaces option
    if args.list_interfaces:
        print("Available network interfaces:")
        try:
            result = subprocess.run(["ip", "link", "show"], capture_output=True, text=True, check=True)
            for line in result.stdout.splitlines():
                if ": " in line and not line.strip().startswith("lo:"):
                    parts = line.split(":")
                    if len(parts) >= 2:
                        interface = parts[1].strip().split("@")[0]
                        if interface != "lo":
                            # Get interface status
                            status = "UP" if "UP" in line else "DOWN"
                            print(f"  - {interface} ({status})")
        except Exception as e:
            print(f"Error listing interfaces: {e}")
        sys.exit(0)
    
    # Handle virtualization check option
    if args.check_virt:
        print("Virtualization Diagnostics:")
        print("=" * 40)
        
        # Check CPU virtualization features
        try:
            result = subprocess.run(["lscpu"], capture_output=True, text=True, check=True)
            for line in result.stdout.splitlines():
                if "Virtualization" in line:
                    print(f"CPU Virtualization: {line.split(':')[1].strip()}")
                    break
            else:
                print("CPU Virtualization: Not detected")
        except:
            print("CPU Virtualization: Unable to check")
        
        # Check KVM
        kvm_exists = Path("/dev/kvm").exists()
        print(f"KVM Device (/dev/kvm): {'Available' if kvm_exists else 'Not found'}")
        
        if kvm_exists:
            try:
                result = subprocess.run(["ls", "-la", "/dev/kvm"], capture_output=True, text=True, check=True)
                print(f"KVM Permissions: {result.stdout.strip()}")
            except:
                pass
        
        # Check libvirt
        try:
            result = subprocess.run(["virsh", "version"], capture_output=True, text=True, check=True)
            print("Libvirt: Available")
        except:
            print("Libvirt: Not available or not accessible")
        
        # Check QEMU
        try:
            result = subprocess.run(["qemu-system-x86_64", "--version"], capture_output=True, text=True, check=True)
            version = result.stdout.split('\n')[0]
            print(f"QEMU: {version}")
        except:
            print("QEMU: Not available")
        
        # Check user groups
        try:
            result = subprocess.run(["groups"], capture_output=True, text=True, check=True)
            groups = result.stdout.strip().split()
            relevant_groups = [g for g in groups if g in ['kvm', 'libvirt', 'qemu']]
            if relevant_groups:
                print(f"User Groups: {', '.join(relevant_groups)}")
            else:
                print("User Groups: No virtualization groups found")
                print("Suggestion: sudo usermod -a -G kvm,libvirt $USER")
        except:
            print("User Groups: Unable to check")
        
        sys.exit(0)
    
    # Handle destroy all option
    if args.destroy_all:
        try:
            vm_manager = VMManager(config_file=args.config)
            vm_manager.destroy_all_vms(force=args.force)
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: {e}")
            sys.exit(1)
        sys.exit(0)
    
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