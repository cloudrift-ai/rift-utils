# Virsh Ceph Dependencies Playbook

This playbook installs the necessary dependencies for using virsh/libvirt with Ceph RBD volumes.

## Structure

- `inventory.ini` - Ansible inventory file defining target hosts
- `playbook.yml` - Main playbook for installing virsh and Ceph dependencies
- `ansible.cfg` - Ansible configuration (vault password file location)
- `group_vars/` - Group-specific variables and encrypted vault files
- `roles/ceph/` - Ansible role containing all Ceph-related tasks and configuration
- `roles/libvirt/` - Ansible role containing all libvirt/virsh installation and configuration

## Prerequisites

- Ansible installed on control machine
- SSH access to target hosts
- Sudo privileges on target hosts

## Usage

1. **Edit the inventory file** (`inventory.ini`) to add your target hosts:
   ```ini
   [us_east_nc_nr_1]
   myhost ansible_host=192.168.1.10 ansible_user=root
   
   [us_east_nc_nr_1:vars]
   ansible_python_interpreter=/usr/bin/python3
   ```

2. **Configure Ceph cluster variables** in `group_vars/us_east_nc_nr_1.yml`:
   - Set `ceph_fsid` to your cluster's FSID
   - Set `ceph_mon_hosts` to your monitor hosts list
   
3. **Configure vault password**:
   - Create vault password file: `mkdir -p ~/.ansible && echo "your_password" > ~/.ansible/vault_pass`
   - Secure the file: `chmod 600 ~/.ansible/vault_pass`
   - Create `ansible.cfg` in the project directory:
     ```ini
     [defaults]
     vault_password_file = $HOME/.ansible/vault_pass
     ```

4. **Store sensitive data** in `group_vars/us_east_nc_nr_1_vault.yml`:
   - Set `vault_ceph_client_key` to your Ceph client key
   - Encrypt the file: `ansible-vault encrypt group_vars/us_east_nc_nr_1_vault.yml`
   - To edit encrypted vault: `ansible-vault edit group_vars/us_east_nc_nr_1_vault.yml`
   - To view encrypted vault: `ansible-vault view group_vars/us_east_nc_nr_1_vault.yml`

6. **Run the playbook**:
   ```bash
   ansible-playbook -i inventory.ini playbook.yml
   ```

7. **With SSH key**:
   ```bash
   ansible-playbook -i inventory.ini playbook.yml --private-key=/path/to/key
   ```

8. **Without ansible.cfg** (manual vault password):
   ```bash
   ansible-playbook -i inventory.ini playbook.yml --ask-vault-pass
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
