#!/bin/bash
set -e

# Script to configure macvlan interface for host-to-VM connectivity
# This allows the GPU host to communicate with VMs using macvtap networking
# Works on Ubuntu 22.04+ with netplan
#
# Subnet and route values are hardcoded and need to be adjusted for new DCs.
#
# Usage: sudo ./setup-macvlan-host-vm-connectivity.sh

echo "=== Setting up macvlan interface for host-VM connectivity ==="

# Configuration
MACVLAN_INTERFACE="macvlan0"
SUBNET_MASK="24"
VM_SUBNET="10.21.106"
SETUP_SCRIPT="/usr/local/bin/setup-macvlan.sh"
SERVICE_FILE="/etc/systemd/system/macvlan-setup.service"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "Error: This script must be run as root (use sudo)"
   exit 1
fi

# Auto-discover parent interface by finding which interface has the VM subnet
echo "Auto-discovering parent interface..."
PARENT_INTERFACE=$(ip -4 addr show | grep -B 2 "inet ${VM_SUBNET}\." | grep -oP '^\d+: \K[^:@]+' | head -1)

if [[ -z "$PARENT_INTERFACE" ]]; then
    echo "Error: Could not auto-discover parent interface for subnet ${VM_SUBNET}.0/24"
    echo "Please check your network configuration with: ip addr show"
    exit 1
fi

# Auto-assign macvlan IP based on host's primary IP
# If host is 10.21.106.7, macvlan will be 10.21.106.207 (200 + last octet)
# This ensures each host gets a unique macvlan IP
HOST_IP=$(ip -4 addr show | grep "inet ${VM_SUBNET}\." | awk '{print $2}' | cut -d'/' -f1 | head -1)
LAST_OCTET=$(echo $HOST_IP | cut -d'.' -f4)
MACVLAN_IP="${VM_SUBNET}.$((200 + LAST_OCTET))"

echo "✓ Detected parent interface: $PARENT_INTERFACE"
echo "✓ Host IP: $HOST_IP"
echo "✓ Macvlan interface: $MACVLAN_INTERFACE"
echo "✓ Macvlan IP: $MACVLAN_IP/$SUBNET_MASK"
echo ""

# Create the setup script that will run on boot
echo "Creating macvlan setup script..."
cat > $SETUP_SCRIPT <<EOF
#!/bin/bash
set -e

# Wait for parent interface to be ready
sleep 2

# Remove existing macvlan interface if it exists
ip link delete $MACVLAN_INTERFACE 2>/dev/null || true

# Create macvlan interface
ip link add link $PARENT_INTERFACE name $MACVLAN_INTERFACE type macvlan mode bridge
ip addr add $MACVLAN_IP/$SUBNET_MASK dev $MACVLAN_INTERFACE
ip link set $MACVLAN_INTERFACE up

# Add routes for VM pool (10.21.106.50-180)
ip route add 10.21.106.50/31 dev $MACVLAN_INTERFACE 2>/dev/null || true
ip route add 10.21.106.52/30 dev $MACVLAN_INTERFACE 2>/dev/null || true
ip route add 10.21.106.56/29 dev $MACVLAN_INTERFACE 2>/dev/null || true
ip route add 10.21.106.64/26 dev $MACVLAN_INTERFACE 2>/dev/null || true
ip route add 10.21.106.128/27 dev $MACVLAN_INTERFACE 2>/dev/null || true
ip route add 10.21.106.160/28 dev $MACVLAN_INTERFACE 2>/dev/null || true
ip route add 10.21.106.176/30 dev $MACVLAN_INTERFACE 2>/dev/null || true
ip route add 10.21.106.180/32 dev $MACVLAN_INTERFACE 2>/dev/null || true

echo "Macvlan interface $MACVLAN_INTERFACE configured successfully"
EOF

chmod +x $SETUP_SCRIPT
echo "✓ Created: $SETUP_SCRIPT"

# Create systemd service
echo "Creating systemd service..."
cat > $SERVICE_FILE <<EOF
[Unit]
Description=Setup macvlan interface for VM connectivity
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=$SETUP_SCRIPT
ExecStop=/usr/sbin/ip link delete $MACVLAN_INTERFACE

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Created: $SERVICE_FILE"

# Enable and start the service
echo ""
echo "Enabling and starting macvlan-setup service..."
systemctl daemon-reload
systemctl enable macvlan-setup.service
systemctl start macvlan-setup.service

# Wait a moment for the interface to come up
sleep 2

# Verify the interface exists
echo ""
echo "Verifying macvlan interface..."
if ip link show $MACVLAN_INTERFACE &> /dev/null; then
    echo "✓ Interface $MACVLAN_INTERFACE created successfully"
    echo ""
    ip addr show $MACVLAN_INTERFACE
else
    echo "✗ Error: Interface $MACVLAN_INTERFACE not found"
    echo "Check service status: sudo systemctl status macvlan-setup.service"
    exit 1
fi

# Show routes
echo ""
echo "Routes through $MACVLAN_INTERFACE:"
ip route show | grep $MACVLAN_INTERFACE

echo ""
echo "=== Setup complete! ==="
echo ""
echo "✓ Macvlan interface is configured and will persist across reboots"
echo "✓ All VMs in the range 10.21.106.50-180 are now reachable from the host"
echo ""
echo "Service management:"
echo "  sudo systemctl status macvlan-setup.service"
echo "  sudo systemctl restart macvlan-setup.service"
echo "  sudo journalctl -u macvlan-setup.service"
