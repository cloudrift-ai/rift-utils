#!/bin/bash
set -e

# VM Backup Script
# Creates a tarball per running VM with:
# - Domain XML
# - All disk images (with backing chain)
# - Metadata YAML tracking original paths

BACKUP_DIR="${1:-/tmp/vm-backups}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

mkdir -p "$BACKUP_DIR"

echo "=== VM Backup Script ==="
echo "Backup directory: $BACKUP_DIR"
echo ""

# List running VMs
RUNNING_VMS=$(virsh list --name | grep -v '^$' || true)

if [ -z "$RUNNING_VMS" ]; then
    echo "No running VMs found."
    exit 0
fi

echo "Running VMs:"
echo "$RUNNING_VMS"
echo ""

for VM_NAME in $RUNNING_VMS; do
    echo "========================================"
    echo "Backing up: $VM_NAME"
    echo "========================================"
    
    WORK_DIR=$(mktemp -d)
    TARBALL="$BACKUP_DIR/${VM_NAME}-${TIMESTAMP}.tar"
    METADATA_FILE="$WORK_DIR/metadata.yaml"
    
    # Export domain XML
    echo "  Exporting domain XML..."
    virsh dumpxml "$VM_NAME" > "$WORK_DIR/domain.xml"
    
    # Get all file-based devices (disks, cdroms, floppies, etc.)
    echo "  Finding all storage files..."
    ALL_DEVICES=$(virsh domblklist "$VM_NAME" --details | grep -E '\s+file\s+' | awk '{print $2, $4}')
    
    # Start metadata file
    cat > "$METADATA_FILE" << EOF
vm_name: $VM_NAME
backup_timestamp: $TIMESTAMP
backup_host: $(hostname)
files:
EOF
    
    FILE_INDEX=0
    declare -A BACKED_UP_FILES
    
    # Process each device (use process substitution to avoid subshell)
    while read -r DEVICE_TYPE FILE_PATH; do
        [ -z "$FILE_PATH" ] && continue
        
        if [ ! -f "$FILE_PATH" ]; then
            echo "  WARNING: File not found: $FILE_PATH"
            continue
        fi
        
        # Skip if already backed up (only for non-disk devices, disks handle this in the chain loop)
        if [ -n "${BACKED_UP_FILES[$FILE_PATH]}" ]; then
            echo "  Skipping (already backed up): $FILE_PATH"
            continue
        fi
        
        echo "  Processing $DEVICE_TYPE: $FILE_PATH"
        
        # Get the target device (vda, sda, etc)
        TARGET=$(virsh domblklist "$VM_NAME" | grep "$FILE_PATH" | awk '{print $1}')
        
        # For disk devices (not cdrom/floppy), try snapshot for zero-downtime
        if [ "$DEVICE_TYPE" = "disk" ]; then
            SNAP_FILE="/tmp/snap-${VM_NAME}-${TARGET}-$$.qcow2"
            echo "    Creating snapshot..."
            if virsh snapshot-create-as "$VM_NAME" "backup-snap-${TARGET}" \
                --disk-only \
                --atomic \
                --diskspec "${TARGET},snapshot=external,file=${SNAP_FILE}" \
                --no-metadata 2>/dev/null; then
                SNAPSHOT_CREATED=1
                echo "    Snapshot created, original disk now unlocked"
            else
                echo "    Snapshot failed, pausing VM briefly for consistent copy"
                virsh suspend "$VM_NAME"
                SNAPSHOT_CREATED=0
                VM_PAUSED=1
            fi
            
            # Collect the disk and its entire backing chain
            # Now that snapshot exists (or VM is paused), the original disk is unlocked
            CURRENT_FILE="$FILE_PATH"
            CHAIN_INDEX=0
            
            echo "    DEBUG: Starting chain walk from $CURRENT_FILE"
            echo "    DEBUG: File exists? $([ -f "$CURRENT_FILE" ] && echo yes || echo no)"
            
            while [ -n "$CURRENT_FILE" ] && ([ -e "$CURRENT_FILE" ] || sudo test -e "$CURRENT_FILE"); do
                echo "    DEBUG: Processing chain level $CHAIN_INDEX: $CURRENT_FILE"
                # Get backing file BEFORE we might skip this file (need it for next iteration)
                BACKING=$(sudo qemu-img info "$CURRENT_FILE" 2>/dev/null | grep "backing file:" | sed 's/backing file: //' | awk '{print $1}')
                echo "    DEBUG: Backing file for $CURRENT_FILE: '$BACKING'"
                
                if [ -z "${BACKED_UP_FILES[$CURRENT_FILE]}" ]; then
                    BACKED_UP_FILES[$CURRENT_FILE]=1
                    
                    FILE_FILENAME=$(basename "$CURRENT_FILE")
                    ARCHIVE_NAME="file-${FILE_INDEX}-chain-${CHAIN_INDEX}-${FILE_FILENAME}"
                    
                    echo "    Copying: $CURRENT_FILE"
                    if [ -r "$CURRENT_FILE" ]; then
                        cp --sparse=always "$CURRENT_FILE" "$WORK_DIR/$ARCHIVE_NAME"
                    else
                        echo "    (using sudo for root-owned file)"
                        sudo cp --sparse=always "$CURRENT_FILE" "$WORK_DIR/$ARCHIVE_NAME"
                        sudo chown "$(id -u):$(id -g)" "$WORK_DIR/$ARCHIVE_NAME"
                    fi
                    
                    # Add to metadata
                    cat >> "$METADATA_FILE" << EOF
  - archive_name: $ARCHIVE_NAME
    original_path: $CURRENT_FILE
    device_type: $DEVICE_TYPE
    target_device: $TARGET
    chain_level: $CHAIN_INDEX
EOF
                    ((FILE_INDEX++)) || true
                fi
                
                CURRENT_FILE="$BACKING"
                ((CHAIN_INDEX++)) || true
            done
            
            # Merge snapshot back or resume VM
            if [ "$SNAPSHOT_CREATED" = "1" ]; then
                echo "    Merging snapshot back..."
                virsh blockcommit "$VM_NAME" "$TARGET" --active --pivot --shallow --wait 2>/dev/null || {
                    echo "    blockcommit failed, trying blockpull..."
                    virsh blockpull "$VM_NAME" "$TARGET" --wait
                }
                rm -f "$SNAP_FILE" 2>/dev/null || sudo rm -f "$SNAP_FILE" 2>/dev/null || echo "    Warning: Could not remove snapshot file $SNAP_FILE"
            fi
            if [ "$VM_PAUSED" = "1" ]; then
                echo "    Resuming VM..."
                virsh resume "$VM_NAME"
                unset VM_PAUSED
            fi
        else
            # For cdrom/floppy, just copy the file directly (no backing chain)
            FILE_FILENAME=$(basename "$FILE_PATH")
            ARCHIVE_NAME="file-${FILE_INDEX}-${DEVICE_TYPE}-${FILE_FILENAME}"
            
            echo "    Copying: $FILE_PATH"
            cp --sparse=always "$FILE_PATH" "$WORK_DIR/$ARCHIVE_NAME"
            
            cat >> "$METADATA_FILE" << EOF
  - archive_name: $ARCHIVE_NAME
    original_path: $FILE_PATH
    device_type: $DEVICE_TYPE
    target_device: $TARGET
    chain_level: 0
EOF
            ((FILE_INDEX++)) || true
        fi
    done <<< "$ALL_DEVICES"
    
    # Create tarball (no compression - qcow2 is already compressed)
    echo "  Creating tarball: $TARBALL"
    tar -cf "$TARBALL" -C "$WORK_DIR" .
    
    # Cleanup
    rm -rf "$WORK_DIR"
    
    TARBALL_SIZE=$(du -h "$TARBALL" | cut -f1)
    echo "  Done! Backup size: $TARBALL_SIZE"
    echo ""
done

echo "=== Backup Complete ==="
echo "Backups stored in: $BACKUP_DIR"
ls -lh "$BACKUP_DIR"/*.tar 2>/dev/null || true
