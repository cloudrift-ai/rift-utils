# VM Backup & Restore Scripts

Scripts for backing up and restoring libvirt/virsh VMs with zero (or minimal) downtime.

## Backup (`vm-backup.sh`)

Creates a tarball for each running VM containing:
- Domain XML configuration
- All disk images (including backing chain)
- Metadata YAML tracking original paths

**Features:**
- Uses snapshots for zero-downtime backup when possible
- Falls back to brief VM pause if snapshots fail
- Preserves sparse files
- Handles backing chains (qcow2 overlays)

### Usage

```bash
# Backup all running VMs to default location (/tmp/vm-backups)
./vm-backup.sh

# Backup to custom directory
./vm-backup.sh /path/to/backups
```

### Output

Creates `<vm-name>-<timestamp>.tar` for each running VM.

---

## Restore (`vm-restore.sh`)

Restores a VM from a backup tarball to its original paths.

**Features:**
- Restores files in correct order (base images before overlays)
- Handles existing VMs (prompts for confirmation)
- Optionally starts VM after restore

### Usage

```bash
# Basic restore (starts VM after)
./vm-restore.sh /path/to/backup.tar

# Restore without starting
./vm-restore.sh /path/to/backup.tar --no-start

# Overwrite existing files
./vm-restore.sh /path/to/backup.tar --overwrite
```

### Options

| Option | Description |
|--------|-------------|
| `--overwrite` | Overwrite existing files (default: skip) |
| `--no-start` | Don't start VM after restore |

---

## Quick Reference

```bash
# Backup
./vm-backup.sh /backups

# List backups
ls -lh /backups/*.tar

# Restore
./vm-restore.sh /backups/myvm-20250120-153000.tar

# Check VM status
virsh list --all

# Connect to restored VM
virsh console <vm-name>
```
