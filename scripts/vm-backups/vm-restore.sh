#!/bin/bash
set -e

# VM Restore Script
# Restores a VM from a backup tarball created by vm-backup.sh
# Files are restored to their original paths

# Parse arguments
TARBALL=""
START_VM="yes"
OVERWRITE="no"

while [[ $# -gt 0 ]]; do
    case $1 in
        --overwrite)
            OVERWRITE="yes"
            shift
            ;;
        --no-start)
            START_VM="no"
            shift
            ;;
        -*)
            echo "Unknown option: $1"
            exit 1
            ;;
        *)
            TARBALL="$1"
            shift
            ;;
    esac
done

if [ -z "$TARBALL" ] || [ ! -f "$TARBALL" ]; then
    echo "Usage: $0 <backup.tar.gz> [options]"
    echo ""
    echo "Options:"
    echo "  --overwrite    Overwrite existing files (default: skip if exists)"
    echo "  --no-start     Don't start the VM after restore"
    echo ""
    echo "Example:"
    echo "  $0 /tmp/vm-backups/myvm-20250120-153000.tar.gz"
    echo "  $0 /tmp/vm-backups/myvm-20250120-153000.tar.gz --overwrite"
    echo "  $0 /tmp/vm-backups/myvm-20250120-153000.tar.gz --no-start"
    exit 1
fi

echo "=== VM Restore Script ==="
echo "Tarball: $TARBALL"
echo ""

# Extract to temp directory
WORK_DIR=$(mktemp -d)
echo "Extracting backup..."
tar -xf "$TARBALL" -C "$WORK_DIR"

# Read metadata
METADATA_FILE="$WORK_DIR/metadata.yaml"
if [ ! -f "$METADATA_FILE" ]; then
    echo "ERROR: metadata.yaml not found in tarball"
    rm -rf "$WORK_DIR"
    exit 1
fi

VM_NAME=$(grep "^vm_name:" "$METADATA_FILE" | awk '{print $2}')
BACKUP_TIMESTAMP=$(grep "^backup_timestamp:" "$METADATA_FILE" | awk '{print $2}')
BACKUP_HOST=$(grep "^backup_host:" "$METADATA_FILE" | awk '{print $2}')

echo "VM Name: $VM_NAME"
echo "Backup from: $BACKUP_TIMESTAMP on $BACKUP_HOST"
echo ""

# Check if VM already exists
if virsh dominfo "$VM_NAME" &>/dev/null; then
    echo "WARNING: VM '$VM_NAME' already exists!"
    read -p "Do you want to replace it? (yes/no): " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "Aborting."
        rm -rf "$WORK_DIR"
        exit 1
    fi
    
    echo "Stopping and undefining existing VM..."
    virsh destroy "$VM_NAME" 2>/dev/null || true
    virsh undefine "$VM_NAME" 2>/dev/null || true
fi

# Restore all files to original paths
echo "Restoring files..."

# Parse metadata and restore files
# We need to restore base images (higher chain_level) before overlays (lower chain_level)
# So we sort by chain_level descending

# Extract file entries and sort by chain level (descending)
awk '/^  - archive_name:/{name=$3} /original_path:/{path=$2} /chain_level:/{level=$2; print level, name, path}' "$METADATA_FILE" | \
    sort -rn | while read -r CHAIN_LEVEL ARCHIVE_NAME ORIGINAL_PATH; do
    
    [ -z "$ARCHIVE_NAME" ] && continue
    [ -z "$ORIGINAL_PATH" ] && continue
    
    # Check if archive file exists in work dir
    if [ ! -f "$WORK_DIR/$ARCHIVE_NAME" ]; then
        echo "  WARNING: Archive file not found: $ARCHIVE_NAME"
        continue
    fi
    
    # Create parent directory if needed
    PARENT_DIR=$(dirname "$ORIGINAL_PATH")
    if [ ! -d "$PARENT_DIR" ]; then
        echo "  Creating directory: $PARENT_DIR"
        mkdir -p "$PARENT_DIR"
    fi
    
    # Check if file already exists
    if [ -f "$ORIGINAL_PATH" ] || sudo test -f "$ORIGINAL_PATH"; then
        if [ "$OVERWRITE" = "yes" ]; then
            echo "  File exists, overwriting: $ORIGINAL_PATH"
        else
            echo "  Skipping (file exists): $ORIGINAL_PATH"
            continue
        fi
    fi
    
    echo "  Restoring: $ARCHIVE_NAME -> $ORIGINAL_PATH"
    if [ -w "$PARENT_DIR" ]; then
        cp --sparse=always "$WORK_DIR/$ARCHIVE_NAME" "$ORIGINAL_PATH"
    else
        echo "    (using sudo for root-owned path)"
        sudo cp --sparse=always "$WORK_DIR/$ARCHIVE_NAME" "$ORIGINAL_PATH"
    fi
done

# Define the VM
echo ""
echo "Defining VM..."
DOMAIN_XML="$WORK_DIR/domain.xml"

if [ ! -f "$DOMAIN_XML" ]; then
    echo "ERROR: domain.xml not found in tarball"
    rm -rf "$WORK_DIR"
    exit 1
fi

virsh define "$DOMAIN_XML"

# Start the VM if requested
if [ "$START_VM" = "yes" ]; then
    echo "Starting VM..."
    virsh start "$VM_NAME"
    echo ""
    echo "VM '$VM_NAME' is now running."
    echo "Connect with: virsh console $VM_NAME"
else
    echo ""
    echo "VM '$VM_NAME' defined but not started."
    echo "Start with: virsh start $VM_NAME"
fi

# Cleanup
rm -rf "$WORK_DIR"

echo ""
echo "=== Restore Complete ==="
