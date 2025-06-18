# CloudRift Utilities

## Client Setup Script

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