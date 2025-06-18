#!/bin/sh

# exit on error
set -e

# Check if the script is run as root
if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root. Use 'sudo' or run as root."
    exit 1
fi

NVIDIA_DRIVER_VERSION="570-server"
ONLY_COMPONENT=""

for arg in "$@"
do
    case $arg in
        --nvidia-driver-version=*)
        NVIDIA_DRIVER_VERSION="${arg#*=}"
        shift
        ;;
        --only=*)
        ONLY_COMPONENT="${arg#*=}"
        shift
        ;;
        *)
        echo "Invalid argument: $arg"
        echo "Usage: $0 [--nvidia-driver-version=<version>] [--only=<component>]"
        exit 1
        ;;
    esac
done

install_base_packages() {
    echo "Installing base packages..."
    apt install -y curl
}

install_vm_packages() {
    echo "Installing VM packages..."
    apt install -y qemu-kvm libvirt-daemon-system genisoimage whois
}

install_rift_packages() {
    echo "Installing Rift service..."
    curl -L https://cloudrift.ai/install-rift-service.sh | sh

    echo "Installing Rift CLI..."
    curl -L https://cloudrift.ai/install-rift.sh | sh
}

setup_rift_credentials() {
    echo "Setting up Rift credentials..."
    rift configure

    systemctl restart rift
    systemctl status rift
}

check_rift_service_status() {
    if systemctl is-active --quiet rift; then
        echo "Rift service is running."
    else
        echo "Rift service is not running."
        exit 1
    fi
}

install_docker() {
    echo "Installing Docker..."

    #uninstall conflicting packages
    for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do sudo apt-get remove $pkg; done

    #setup repository
    # Add Docker's official GPG key:
    apt-get install ca-certificates curl
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc

    # Add the repository to Apt sources:
    echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update

    #install docker
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

install_nvidia_driver() {
    echo "Installing NVIDIA driver $NVIDIA_DRIVER_VERSION..."

    apt-get install -y nvidia-driver-$NVIDIA_DRIVER_VERSION nvidia-utils-$NVIDIA_DRIVER_VERSION
}

install_nvidia_container_toolkit() {
    echo "Installing NVIDIA Container Toolkit..."
    # Configure the repository
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    tee /etc/apt/sources.list.d/nvidia-container-toolkit.list    
    
    # Install the NVIDIA Container Toolkit
    sudo apt-get update
    sudo apt-get install -y nvidia-container-toolkit

    # Configure
    nvidia-ctk runtime configure --runtime=docker

    # Restart Docker
    systemctl restart docker
}

apt-get update

if [ -n "$ONLY_COMPONENT" ]; then
    case $ONLY_COMPONENT in
        docker)
        install_docker
        exit 0
        ;;
        nvidia)
        install_nvidia_driver
        install_nvidia_container_toolkit
        exit 0
        ;;
        driver)
        install_nvidia_driver
        exit 0
        ;;
        rift)
        install_base_packages
        install_rift_packages
        setup_rift_credentials
        check_rift_service_status
        exit 0
        ;;
        vm)
        install_vm_packages
        exit 0
        ;;
        *)
        echo "Invalid component specified: $ONLY_COMPONENT"
        echo "Valid components: docker, nvidia, driver, rift"
        exit 1
        ;;
    esac
fi

install_base_packages
install_vm_packages
install_rift_packages
setup_rift_credentials
check_rift_service_status
install_docker
install_nvidia_driver
install_nvidia_container_toolkit