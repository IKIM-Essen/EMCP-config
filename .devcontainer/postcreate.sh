#!/usr/bin/env sh
set -eu

SCRIPTDIR="$(dirname "$(readlink -fn "$0" )")"
DEPS_DIR="$SCRIPTDIR/../ansible/deps"
META_DIR="$SCRIPTDIR/../ansible/meta"

# Check out the upstream repo.
if [ ! -d "$DEPS_DIR" ]; then
	mkdir "$DEPS_DIR"
fi
cd "$DEPS_DIR"

if [ -d "rke2-ansible" ]; then
	cd "rke2-ansible"
	git pull
else
	git clone "https://github.com/rancherfederal/rke2-ansible.git"
fi

# Install upstream dependencies.
ansible-galaxy collection install -r "$DEPS_DIR/rke2-ansible/requirements.yml"

# Install dependencies.
ansible-galaxy collection install -r "$META_DIR/requirements.yml"
