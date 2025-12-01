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

# Ceph cluster configuration (required for config file generation)
ceph_fsid: ""
ceph_mon_hosts: []
ceph_client_name: "client.admin"
ceph_client_key: ""
```

### Required Variables

To generate Ceph configuration files, you must set:
- `ceph_fsid` - Your Ceph cluster FSID
- `ceph_mon_hosts` - List of monitor host addresses
- `ceph_client_key` - Ceph client authentication key (store in vault)

## Dependencies

None.

## Example Playbook

```yaml
- hosts: virsh_hosts
  become: yes
  vars:
    ceph_fsid: "12345678-1234-1234-1234-123456789abc"
    ceph_mon_hosts:
      - "[v2:10.0.0.1:3300/0,v1:10.0.0.1:6789/0]"
      - "[v2:10.0.0.2:3300/0,v1:10.0.0.2:6789/0]"
      - "[v2:10.0.0.3:3300/0,v1:10.0.0.3:6789/0]"
    ceph_client_key: "{{ vault_ceph_client_key }}"
  roles:
    - ceph
```

## Configuration Files

This role generates:
- `/etc/ceph/ceph.conf` - Ceph cluster configuration
- `/etc/ceph/ceph.{{ ceph_client_name }}.keyring` - Client authentication keyring (mode 0600)
  - Default: `/etc/ceph/ceph.client.admin.keyring`

## License

MIT

## Author Information

CloudRift AI
