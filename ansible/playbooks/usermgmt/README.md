# User-management playbook

A playbook for managing centralized users in FreeIPA.

The accounts created this way are separate from the local accounts created in the `site.yaml` playbook via the `localadmins` role, therefore it's recommended that users pick different usernames if they wish to have both an admin account and a centralized one.

## Requirements
Before executing the playbook, change directory to the parent of the `playbooks` directory so that Ansible can locate the required roles.

Define the variables `userglob` and/or `groupglob` by assigning a YAML file path or a glob expression that expands to YAML paths. The expansion is carried out by the [Python glob module][python-glob]. The file format is described below.

## File format

### User files

| Field | Type | Description |
| ----- | ---- | ----------- |
| **username** | string | The username |
| **first_name** | string | First name |
| **last_name** | string | Last name |
| **email** | list of strings | The email addresses |
| **ssh_public_key** (optional) | list of strings | The ssh public keys. Default: empty |
| **manager** (optional) | string | Username of this user's manager. If specified, the manager must exist in FreeIPA. Default: none |
| **expiration** (optional) | [FreeIPA datetime][freeipa-params] | The point in time when this user will be automatically disabled in FreeIPA. Default: never |
| **useradmin** (optional) | bool | Whether this user can manage (create, modify, delte) other users. Default: `false` |
| **desired_state** (optional) | bool | Accepted values: `present`, `absent`, `enabled`, `disabled`. Default: `present` |

### Group files

| Field | Type | Description |
| ----- | ---- | ----------- |
| **groupname** | string | The name of the group |
| **is_project** (optional) | bool | If true, a project directory is created on NFS. Default: `false` |
| **is_group** (optional) | bool | If true, a group directory is created on NFS. Default: `false` |
| **members** (optional) | list of strings | Usernames of the group members. Default: empty |
| **desired_state** (optional) | bool | Accepted values: `present`, `absent`. Default: `present` |

## Examples

### Create a group and the member users from a directory

Contents of `users/alice.yml`:

```yaml
username: alice
first_name: Alice
last_name: Professor
desired_state: enabled
ssh_public_key: ['ssh-keytype key comment']
email: ['alice@example.org']
```

Contents of `users/bob.yml`:

```yaml
username: bob
first_name: Bob
last_name: Student
desired_state: enabled
ssh_public_key: ['ssh-keytype key comment']
email: ['bob@example.org']
manager: alice
expiration: 2001-01-01Z
```

Contents of `groups/research.yml`:

```yaml
groupname: research
is_project: true
members: ['alice', 'bob']
desired_state: present
```

Ansible command:

```sh
ansible-playbook playbooks/usermgmt/create-users-groups.yml -i inventory.yml -e userglob='users/*.yml' -e groupglob=groups/research.yml
```

[python-glob]: https://docs.python.org/3/library/glob.html
[freeipa-params]: https://github.com/freeipa/freeipa/blob/master/ipalib/parameters.py
