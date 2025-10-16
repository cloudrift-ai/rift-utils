# CloudRift Utilities

This repository contains a collection of scripts to configure a server for use with the CloudRift datacenter service.

## Configuration System

The configuration system provides flexible workflow-based setup for CloudRift servers with support for both built-in and custom YAML workflows.

### Quick Start

**Recommended: Using Makefile (handles all dependencies automatically)**
```bash
sudo make configure
```

This single command will:
1. Install system dependencies (python3, python3-venv, python3-pip)
2. Create a Python virtual environment
3. Install required Python dependencies
4. Run the configure script with sudo

**Alternative: Manual Python execution**
```bash
sudo python3 python/configure/configure.py
```

It will display a list of available workflows and prompt you to select one.

**List Available Options:**
```bash
# List all available workflows
./python/configure/configure.py --list-workflows

# List all available commands
./python/configure/configure.py --list-commands
```

### YAML Workflows

Create custom workflows using YAML configuration files for maximum flexibility.

#### YAML Workflow Format
```yaml
---
name: "Custom Workflow Name"
description: "Description of what this workflow does"
commands:
  - name: "CheckVirtualizationCmd"
  - name: "AptInstallCmd"
    environment: 
      packages:
        - "qemu-kvm"
        - "libvirt-daemon-system"
        - "genisoimage"
        - "whois"
        - "mdadm"
      - "docker.io"
  - name: "InstallNvidiaDriverCmd"
```

#### Execute YAML Workflows
```bash
# Execute a custom YAML workflow
sudo ./python/configure/configure.py --yaml-workflow workflows/custom-setup.yaml

# Use provided example workflows
sudo ./python/configure/configure.py --yaml-workflow workflows/nvidia-setup.yaml
```

### Individual Commands

Execute specific configuration commands independently:

```bash
# Execute a specific command by number
sudo ./python/configure/configure.py --command 5

# Execute a command by name
sudo ./python/configure/configure.py --command "Install NVIDIA Driver"
```

### Requirements

**Option 1: Using Makefile (recommended)**
```bash
make install
```

**Option 2: Manual installation**
```bash
pip3 install -r python/requirements.txt
```

### Available Makefile Commands

- `make configure` - Complete setup: installs system deps, creates venv, installs Python deps, and runs configure script (requires sudo)
- `make system-deps` - Install system dependencies (python3, python3-venv, python3-pip) only - requires sudo
- `make venv` - Create Python virtual environment only
- `make install` - Install Python dependencies in venv only
- `make clean` - Remove virtual environment
- `make help` - Display available commands

### Client Setup Script

This script facilitates machine setup for the CloudRift datacenter service.

It updates the `apt` cache and installs packages required by the CloudRift service.

**Usage:**  
`sudo ./client_setup.sh [--nvidia-driver-version=<version>] [--only=<component>]`

**Arguments:**

| Argument                           | Description                              | Example                              |
|------------------------------------|------------------------------------------|--------------------------------------|
| `--nvidia-driver-version=<version>`| Install specific NVIDIA driver version   | `--nvidia-driver-version=570-server` |
| `--only=<component>`               | Install only the specified component     | `--only=nvidia`                      |

**Available components to install:**
- **docker** – Docker from [docker.com](https://www.docker.com)
- **nvidia** – NVIDIA driver and container toolkit
- **driver** – Only the NVIDIA driver
- **rift** – CloudRift service and CLI client
- **vm** – libvirt virtualization software

If no component is specified, all packages will be installed.

> **Note:** Run this script with root privileges (e.g., using `sudo`).

## Contributing

When adding new configuration commands:

1. Create a new command class inheriting from `BaseCmd`
2. Implement the required methods: `name()`, `description()`, and `execute()`
3. Place the command file in `python/configure/commands/`
4. The command will be automatically discovered and available in workflows

## Troubleshooting

### Common Issues

**Permission Errors:**
- Ensure you're running with `sudo` for system configuration commands

**Missing Dependencies:**
```bash
pip3 install -r python/requirements.txt
```

**YAML Syntax Errors:**
- Validate your YAML files with an online YAML validator
- Check indentation (use spaces, not tabs)
- Ensure all required fields are present

**Command Not Found:**
- Use `--list-commands` to see available commands
- Check command name spelling in YAML files

### Getting Help

```bash
# Show all available options
./python/configure/configure.py --help

# List available workflows and commands
./python/configure/configure.py --list-workflows
./python/configure/configure.py --list-commands
```