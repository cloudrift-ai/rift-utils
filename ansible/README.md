# Virsh Ceph Dependencies Playbook

This playbook installs the necessary dependencies for using virsh/libvirt with Ceph RBD volumes.

## Structure

- `inventory.ini` - Ansible inventory file defining target hosts
- `playbook.yml` - Main playbook for installing virsh and Ceph dependencies
- `roles/ceph/` - Ansible role containing all Ceph-related tasks and configuration
- `roles/libvirt/` - Ansible role containing all libvirt/virsh installation and configuration

## Prerequisites

- Ansible installed on control machine
- SSH access to target hosts
- Sudo privileges on target hosts

## Usage

1. **Edit the inventory file** (`inventory.ini`) to add your target hosts:
   ```ini
   [virsh_hosts]
   myhost ansible_host=192.168.1.10 ansible_user=root
   ```

2. **Run the playbook**:
   ```bash
   ansible-playbook -i inventory.ini playbook.yml
   ```

3. **With SSH key**:
   ```bash
   ansible-playbook -i inventory.ini playbook.yml --private-key=/path/to/key
   ```

4. **With password prompt**:
   ```bash
   ansible-playbook -i inventory.ini playbook.yml --ask-pass --ask-become-pass
   ```

## What Gets Installed

### Ceph Packages
- `ceph-common` - Common Ceph utilities and client tools

### Libvirt Packages
- `qemu-kvm` - KVM virtualization
- `qemu-block-extra` - Extra QEMU block drivers including RBD support
- `libvirt-daemon-system` - Libvirt daemon
- `libvirt-daemon-driver-storage-rbd` - Libvirt RBD storage driver

## Supported Operating Systems

- Debian/Ubuntu

## Verification

Check that libvirt can access RBD:
```bash
virsh pool-capabilities | grep -A 5 rbd
```
