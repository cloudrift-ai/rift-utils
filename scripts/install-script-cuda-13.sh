set -e

# Machine architecture
ARCH=$(uname -m | grep -q -e 'x86_64' && echo 'x86_64' || echo 'sbsa')

# OS Version
UBUNTU_VERSION=$(awk -F= '/^VERSION_ID/{gsub(/"/, "", $2); print $2}' /etc/os-release)
OS_VERSION=$(dpkg --compare-versions "$UBUNTU_VERSION" "ge" "24.04" && echo "ubuntu2404" || echo "ubuntu2204")

wget https://developer.download.nvidia.com/compute/cuda/repos/${OS_VERSION}/${ARCH}/cuda-keyring_1.1-1_all.deb -P /tmp
sudo dpkg -i /tmp/cuda-keyring_1.1-1_all.deb
rm /tmp/cuda-keyring_1.1-1_all.deb
sudo apt-get update
# 13.x is supported by driver 580
sudo apt-get install -y cuda-toolkit-13