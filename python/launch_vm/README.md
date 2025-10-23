# VM Manager - Python Version

A Python-based VM management tool that creates and configures virtual machines using libvirt and cloud-init. This is the Python version of `launch_vm.sh` with YAML-based configuration.

## Features

- **YAML Configuration**: All settings are loaded from `vm_config.yaml`
- **Multiple VM Support**: Define multiple VMs with different specifications
- **Flexible Networking**: Supports both libvirt networks and Linux bridges  
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
- `libvirt_net_name`: Preferred libvirt network name
- `linux_bridge_name`: Fallback Linux bridge name

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
# Use default configuration (vm_config.yaml)
./launch_vm.py

# Use custom configuration file
./launch_vm.py --config /path/to/custom_config.yaml
```

### Command Line Options
- `-c, --config`: Path to YAML configuration file
- `-h, --help`: Show help message

### Environment Variables
- `SSH_PUBKEY`: Override SSH public key from environment

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

### Custom Storage Location
```yaml
storage:
  root_dir: "/var/lib/vms"  # Absolute path
  # or
  root_dir: "custom_vms"    # Relative to home directory
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