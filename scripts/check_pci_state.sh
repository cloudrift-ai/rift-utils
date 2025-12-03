#!/usr/bin/env bash

echo "Scanning NVIDIA GPUs..."
echo "--------------------------------------------------------------------------------------------"
printf "%-15s %-20s %-20s %-15s\n" "PCI Address" "Power State (sysfs)" "Power State (setpci)" "Vendor ID"
echo "--------------------------------------------------------------------------------------------"

# Find NVIDIA PCI devices
for dev in $(lspci | grep -i nvidia | awk '{print $1}'); do
    sys_path="/sys/bus/pci/devices/0000:$dev/power_state"

    if [[ -f "$sys_path" ]]; then
        state=$(cat "$sys_path")
    else
        state="N/A"
    fi

    # Read PCI PM control/status register (bits 1:0 indicate power state)
    pci_state=$(sudo setpci -s "$dev" CAP_PM+4.w 2>/dev/null)
    if [[ -n "$pci_state" ]]; then
        # Extract lower 2 bits to get power state
        pm_bits=$((0x$pci_state & 0x3))
        case $pm_bits in
            0) pci_state="D0" ;;
            1) pci_state="D1" ;;
            2) pci_state="D2" ;;
            3) pci_state="D3" ;;
        esac
    else
        pci_state="N/A"
    fi

    # Read vendor ID from config space offset 0
    vendor_id=$(sudo setpci -s "$dev" 0.w 2>/dev/null)
    if [[ -z "$vendor_id" ]]; then
        vendor_id="N/A"
    else
        vendor_id="0x$vendor_id"
    fi

    printf "%-15s %-20s %-20s %-15s\n" "$dev" "$state" "$pci_state" "$vendor_id"
done

echo "--------------------------------------------------------------------------------------------"
