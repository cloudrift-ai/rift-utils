# Libvirt Role

Ansible role for installing libvirt/virsh with Ceph RBD support.

## Requirements

- Ansible 2.9 or higher
- Target hosts running Debian/Ubuntu

## Role Variables

Available variables are listed below, along with default values (see `defaults/main.yml`):

```yaml
libvirt_packages:
  - qemu-kvm
  - qemu-block-extra
  - libvirt-daemon-system
  - libvirt-daemon-driver-storage-rbd

libvirt_service_name: libvirtd
```

## Dependencies

None.

## Example Playbook

```yaml
- hosts: virsh_hosts
  become: yes
  roles:
    - libvirt
```

## What This Role Does

1. Installs QEMU/KVM with RBD block driver support
2. Installs libvirt daemon and RBD storage driver
3. Enables and starts the libvirtd service
4. Adds the ansible user to the libvirt group (if not root)

## License

MIT

## Author Information

CloudRift AI
