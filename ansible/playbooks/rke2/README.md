# RKE2

A playbook for provisioning RKE2 cluster. It uses the upstream roles from [rke2-ansible][rke2-ansible] with pre and post-installation additions.

## Getting started
This repository contains a Dev Container initialization script which carries out the preparation steps (checking out the upstream playbook and installing the dependencies) automatically. To execute this step manually:

```sh
.devcontainer/postcreate.sh
```

The inventory must be configured using specific group names. See [rke2-ansible][rke2-ansible] for details.

The following playbooks are available:

- `install.yml`
- `uninstall.yml`

## Adding manifests

The directories [`{{ bootstrap_manifest_template_dir }}`][rke2-prep-role] and [`{{ postinstall_manifest_template_dir }}`][rke2-prep-role] accept plain Kubernetes manifests as `*.yml` files or Jinja2 templates as `*.j2` files. They are deployed to the RKE2 cluster at specific points in the workflow:

- Bootstrap manifests: immediately before starting up the first RKE2 server.
- Post-installation manifests: after all nodes have joined the cluster.

[rke2-ansible]: https://github.com/rancherfederal/rke2-ansible
[rke2-prep-role]: ../../roles/rke2_prep/defaults/main.yml
