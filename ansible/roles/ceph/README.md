# Ceph Role

Ansible role for installing Ceph client dependencies needed for virsh/libvirt to bind Ceph RBD volumes.

## Requirements

- Ansible 2.9 or higher
- Target hosts running Debian/Ubuntu

## Role Variables

Available variables are listed below, along with default values (see `defaults/main.yml`):

```yaml
ceph_packages:
  - ceph-common

ceph_config_dir: /etc/ceph
ceph_conf_file: "{{ ceph_config_dir }}/ceph.conf"
ceph_keyring_file: "{{ ceph_config_dir }}/ceph.client.admin.keyring"
```

## Dependencies

None.

## Example Playbook

```yaml
- hosts: virsh_hosts
  become: yes
  roles:
    - ceph
```

## Post-Installation

After running this role, you need to:

1. Copy your Ceph cluster configuration to `/etc/ceph/ceph.conf`
2. Copy your Ceph keyring to `/etc/ceph/ceph.client.admin.keyring`
3. Ensure proper permissions on keyring file (chmod 600)

## License

MIT

## Author Information

CloudRift AI
