# SSH Keys Role

Manages team SSH public keys in authorized_keys for remote access.

## Usage

Add team members' public SSH keys to `files/team_keys.pub`, one per line.

## What This Role Does

- Creates `.ssh` directory with proper permissions (700)
- Adds all keys from `team_keys.pub` to the user's `authorized_keys`
- Uses `exclusive: false` to preserve existing keys

## Example

```yaml
- hosts: all
  become: yes
  roles:
    - ssh_keys
```
