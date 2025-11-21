# VM Manager - Python Version

A Python-based VM management tool that creates and configures virtual machines using libvirt and cloud-init.

## Features

- **YAML Configuration**: All settings are loaded from `vm_config.yaml`
- **Multiple VM Support**: Define multiple VMs with different specifications
- **Flexible Networking**: Supports libvirt networks, Linux bridges (with auto-creation), macvtap (high performance), and NAT networks  
- **Cloud-init Integration**: Automatic VM provisioning with SSH keys, packages, and configuration
- **Image Management**: Automatic download and CoW backing file creation
- **Error Handling**: Comprehensive validation and error reporting

## Prerequisites

- Python 3.7+
- PyYAML library
- libvirt and related tools (virsh, virt-install, etc.)
- qemu-img, cloud-localds, wget

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure libvirt tools are installed:
```bash
# Ubuntu/Debian
sudo apt install libvirt-daemon-system libvirt-clients qemu-kvm virt-manager cloud-image-utils

# RHEL/CentOS/Fedora  
sudo dnf install libvirt qemu-kvm virt-install virt-manager cloud-utils
```

## Configuration

The script uses `vm_config.yaml` for all configuration. Key sections:

### Networking

The networking section supports multiple modes:

- **`mode`**: Network configuration mode
  - `auto`: Try libvirt → bridge → macvtap → NAT (default)
  - `libvirt`: Use existing libvirt network (must exist)
  - `bridge`: Use Linux bridge (must exist)
  - `macvtap`: Use macvtap (high performance direct interface access)
  - `nat`: Create/use NAT network
- **`libvirt_net_name`**: Libvirt network name
- **`linux_bridge_name`**: Linux bridge name (for existing bridges)
- **`bridge`**: Bridge creation configuration (see Bridge Network section)
- **`macvtap`**: Macvtap configuration (see Macvtap Network section)
- **`nat`**: NAT network configuration (see NAT Network section)

### VMs
Define VMs in the `vms` section:
```yaml
vms:
  - name: "my-vm"
    vcpus: 4
    ram_gb: 8
    disk_gb: 40
    description: "My custom VM"
```

### SSH Access
- `public_key`: SSH public key (leave empty for auto-detection)
- `public_key_file`: Path to SSH public key file

### Cloud-init
- `timezone`: Default timezone for VMs
- `packages`: List of packages to install
- `default_user`: Default user account name

## Usage

### Basic Usage
```bash
# Interactive setup (recommended for beginners)
./launch_vm.py --interactive

# Use default configuration (vm_config.yaml)
./launch_vm.py

# Use custom configuration file
./launch_vm.py --config /path/to/custom_config.yaml
```

### Command Line Options
- `-c, --config`: Path to YAML configuration file
- `--interactive`: Interactive setup mode - ask simple questions to create basic configuration
- `--dry-run`: Load and validate configuration without creating VMs
- `--list-interfaces`: List available network interfaces for bridge configuration
- `--check-virt`: Check virtualization capabilities and requirements
- `--destroy-all`: Destroy and cleanup all VMs created by this configuration
- `--force`: Skip confirmation prompts (use with --destroy-all)
- `--no-start`: Override config and don't start any VMs (define only)
- `--force-start`: Override config and start all VMs regardless of initial_state setting
- `-h, --help`: Show help message

### Environment Variables
- `SSH_PUBKEY`: Override SSH public key from environment

### VM Cleanup
```bash
# Destroy all VMs and cleanup networks (with confirmation)
./launch_vm.py --destroy-all

# Force destroy without confirmation prompts
./launch_vm.py --destroy-all --force

# Check what would be destroyed (dry run first)
./launch_vm.py --dry-run  # Shows which VMs would be created
```

## Interactive Mode

The interactive mode provides a simple wizard for creating VM configurations:

```bash
./launch_vm.py --interactive
```

### Interactive Setup Example
```
=== VM Manager Interactive Setup ===
This wizard will help you create a basic VM configuration.
Press Enter to accept default values in [brackets].

VM name [ubuntu-vm]: web-server
CPU cores [2]: 4
Memory in GB [4]: 8
Disk size in GB [20]: 50

Network configuration:
1. DHCP (automatic IP)
2. Static IP
Choose network type [1]: 2
Static IP address [192.168.1.100]: 192.168.1.200
Gateway [192.168.1.1]: 

Start VM automatically after creation? [Y/n]: 

=== Configuration Summary ===
VM Name: web-server
Resources: 4 CPU cores, 8GB RAM, 50GB disk
Network: Static IP 192.168.1.200
Auto-start: Yes

Save configuration to vm_config.yaml? [Y/n]: y
```

This creates a complete configuration file and optionally starts the VM creation process.

## Examples

### Adding a New VM
Edit `vm_config.yaml`:
```yaml
vms:
  - name: "database-vm"
    vcpus: 8
    ram_gb: 16 
    disk_gb: 100
    description: "Database server"
```

### Custom SSH Key
```yaml
ssh:
  public_key: "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... your-key"
```

### VM Initial State Control
```yaml
# Global default for all VMs
hardware:
  default_initial_state: "start"  # or "stop"

# Per-VM configuration
vms:
  - name: "web-server"
    vcpus: 4
    ram_gb: 8
    disk_gb: 50
    initial_state: "start"    # Start automatically after creation
    
  - name: "backup-server"  
    vcpus: 2
    ram_gb: 4
    disk_gb: 100
    initial_state: "stop"     # Define only, don't start automatically
```

### Command Line Overrides
```bash
# Define all VMs but don't start any (useful for batch operations)
./launch_vm.py --no-start

# Force start all VMs regardless of their initial_state setting
./launch_vm.py --force-start

# Check configuration including start behavior
./launch_vm.py --dry-run --no-start
```

### Custom Storage Location
```yaml
storage:
  root_dir: "/var/lib/vms"  # Absolute path
  # or
  root_dir: "custom_vms"    # Relative to home directory
```

### NAT Network Configuration
```yaml
networking:
  mode: "nat"  # Use NAT network mode
  nat:
    network_name: "vm-nat"
    subnet: "192.168.100.0/24"
    gateway: "192.168.100.1"
    dhcp_start: "192.168.100.10"
    dhcp_end: "192.168.100.100"
    forward_mode: "nat"  # or "route"
    forward_dev: ""      # auto-detect if empty
```

### Bridge Network Configuration
```yaml
networking:
  mode: "bridge"  # Use bridge network mode
  bridge:
    bridge_name: "vmbr0"
    physical_interface: "enp0s3"  # Your actual interface name
    use_dhcp: true               # Or set static IP below
    ip_address: ""               # e.g., "192.168.1.100/24"
    gateway: ""                  # e.g., "192.168.1.1"
    dns_servers: []              # e.g., ["8.8.8.8", "1.1.1.1"]
    use_netplan: true            # Use netplan (recommended)
```

### Macvtap Network Configuration (High Performance)
```yaml
networking:
  mode: "macvtap"  # Use macvtap for near-native performance
  macvtap:
    physical_interface: "enp0s3"  # Physical interface to attach to
    mode: "bridge"               # bridge, vepa, private, or passthru
    auto_create: true            # Automatically create macvtap interface
    interface_prefix: "macvtap"  # Interface name prefix
```

#### Macvtap Modes
- **`bridge`**: VMs can communicate with each other and external networks (most common)
- **`vepa`**: VMs communicate via external switch (VEPA-capable switch required)  
- **`private`**: VMs isolated from each other and host, external only
- **`passthru`**: Exclusive access to physical interface (one VM only)

### Mixed Network Setup (Auto Mode)
```yaml
networking:
  mode: "auto"  # Try libvirt → bridge → macvtap → NAT
  libvirt_net_name: "bridge"
  linux_bridge_name: "br0"
  bridge:
    bridge_name: "vmbr0"
    physical_interface: "eth0"
    use_dhcp: true
  macvtap:
    physical_interface: "eth0"
    mode: "bridge"
    auto_create: true
  nat:
    network_name: "fallback-nat"
    subnet: "192.168.200.0/24"
```

## VM Management

After VMs are created:

```bash
# List all VMs
virsh list --all

# Get VM IP addresses
virsh domifaddr vm-name

# Connect to VM console
virsh console vm-name  # (Press Ctrl-] to exit)

# SSH to VM (once IP is known)
ssh ubuntu@VM_IP

# Stop a VM
virsh shutdown vm-name

# Start a VM
virsh start vm-name

# Delete a VM completely
virsh destroy vm-name
virsh undefine --remove-all-storage vm-name
```

## Troubleshooting

### Common Issues

1. **PyYAML not found**: Install with `pip install PyYAML`
2. **Config file not found**: Ensure `vm_config.yaml` exists in script directory
3. **SSH key not found**: Set `SSH_PUBKEY` environment variable or configure in YAML
4. **Network issues**: Verify libvirt network or Linux bridge exists
5. **Permission errors**: Ensure user is in `libvirt` group: `sudo usermod -a -G libvirt $USER`

### Debug Mode
The script shows configuration summary at startup. Check that all values are correct.

### Log Files
- libvirt logs: `/var/log/libvirt/`
- VM console logs: Check with `virsh console vm-name`

## Differences from Bash Version

- **YAML Configuration**: Externalized all configuration
- **Better Error Handling**: More descriptive error messages
- **Modular Design**: Object-oriented structure for easier maintenance
- **Type Safety**: Full type annotations
- **Command Line Interface**: Argument parsing with help
- **Configuration Validation**: Validates YAML structure and required fields

## License

Same as parent project.