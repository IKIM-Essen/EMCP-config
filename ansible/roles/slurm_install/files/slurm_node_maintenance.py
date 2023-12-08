#!/usr/bin/env python3

"""A script for cleaning up local storage on slurm nodes."""
import argparse
from collections.abc import Sequence
from pathlib import Path
import time
import subprocess
import socket
import shutil
import sys

THRESHOLD_DEFAULT=0.2
_STATE_IDLE = 'idle'
_STATE_DOWN = 'down'
_STATE_DRAIN = 'drain'
_STATE_DRAINING = 'drng'
_STATE_MAINT = 'maint'
_STATE_RESUME = 'resume'
_STATE_UNDRAIN = 'undrain'
_SINFO = '/usr/bin/sinfo'
_SCONTROL = '/usr/bin/scontrol'
_SQUEUE = '/usr/bin/squeue'
_APTGET = '/usr/bin/apt-get'
_DURATION_ONE_HOUR = 3600  # in seconds
_DELTA_ONE_WEEK = 604800  # in seconds
_NOW = int(time.time())  # in seconds, with the fractional part discarded
_HOSTNAME = socket.getfqdn().split('.', maxsplit=1)[0]

def main() -> int:
    """Define the command-line parameters and execute the maintenance logic.

    The unattended maintenance takes place only if the cluster is in a healthy
    state. It consists of the following steps:
      1. A slurm command to drain the local node is issued in order to prevent
         the node from accepting jobs.
      2  Cache and local storage are cleaned up if needed.
      3. OS package upgrades are carried out.
      4. If necessary to complete the upgrades, the node is rebooted, otherwise
         a slurm command to undrain is issued.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--threshold',
        type=float,
        default=THRESHOLD_DEFAULT,
        help="the desired free space expressed as a fraction of the partition size")
    parser.add_argument(
        '--userdir-root',
        action='append',
        default=[],
        help="user directory root to clean up. It must contain subdirectories named after users.")
    parser.add_argument(
        '--globaldir',
        action='append',
        default=[],
        help="general-purpose directory to clean up")
    parser.add_argument(
        '--ctime-delta',
        type=int,
        default=_DELTA_ONE_WEEK,
        help="delete subdirectories only if their ctime is older than this delta (in seconds)")
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="don't actually perform the actions listed in the output")
    args = parser.parse_args()

    if is_cluster_healthy():
        drain(dry_run=args.dry_run)
        cleanup(
            userdir_roots=args.userdir_root,
            globaldirs=args.globaldir,
            threshold=args.threshold,
            ctime_delta=args.ctime_delta,
            dry_run=args.dry_run)
        upgrade_pkgs(dry_run=args.dry_run)
        undrain_or_reboot(dry_run=args.dry_run)
    else:
        print("Some nodes are drained, down or in maintenance. Skipping unattended maintenance.")

    return 0

def is_cluster_healthy() -> bool:
    """Determine whether the slurm cluster in a healthy state.

    The cluster is considered healthy if no nodes are in any of the following
    states:
      - drain
      - draining
      - down
      - reservation with the maintenance flag
    """
    unhealthy_states = set((
        _STATE_DRAIN,
        _STATE_DRAINING,
        _STATE_DOWN,
        _STATE_MAINT))
    sinfo = _run([
        _SINFO,
        '--noheader',
        '--format=%t'])
    states = set(sinfo.stdout.splitlines())
    return states.isdisjoint(unhealthy_states)

def drain(dry_run: bool = False) -> None:
    """Issue a drain command via slurm."""
    _set_node_state(_STATE_DRAIN, dry_run=dry_run)

def cleanup(
    userdir_roots: Sequence[str],
    globaldirs: Sequence[str],
    threshold: int = THRESHOLD_DEFAULT,
    ctime_delta: int = _DELTA_ONE_WEEK,
    dry_run: bool = False
) -> None:
    """Clean up local storage on the current node.

    If the available space is less than the specified threshold, an attempt to
    recover space is made as follows:
      - if processing a user directory, it is cleaned up only if the user
        has no jobs in the current node's queue;
      - if processing a general-purpose directory, it is cleaned up only if
        the node has no running jobs.

    The specified paths must represent real directories. Symbolic links are not
    followed.
    """
    print('Evaluating the available space...')
    userdir_roots_to_process = [
        root for root in userdir_roots
        if _is_real_dir(root) and (_get_free_space(root) < threshold)]
    globaldirs_to_process = [
        path for path in globaldirs
        if _is_real_dir(path) and (_get_free_space(path) < threshold)]
    if userdir_roots_to_process or globaldirs_to_process:
        print('The available space is below the configured threshold. Starting cleanup...')
        clean_user_dirs(userdir_roots_to_process, ctime_delta=ctime_delta, dry_run=dry_run)
        clean_global_dirs(globaldirs_to_process, ctime_delta=ctime_delta, dry_run=dry_run)
    else:
        print('The available space meets the configured threshold. Nothing to do.')

def clean_user_dirs(
    roots: Sequence[str],
    ctime_delta: int = _DELTA_ONE_WEEK,
    dry_run: bool = False
) -> None:
    """Delete user directories in the specified root paths.

    The specified paths must contain subdirectories named after users.
    For example, given path == '/local/cache', the directory
    structure must be as follows:
    /local/cache/
    |- alice/
    |- bob/
    |- ...

    The deletion of a user directory might be skipped if any of the following
    conditions hold:
      - the user has a job in the slurm queue on the current node
      - the ctime of the directory is more recent than ctime_delta ago
    """
    for root in roots:
        print(f'Cleaning up {root}...')
        for userdir in Path(root).iterdir():
            if not _has_job_in_queue(userdir.name):
                _rmr(userdir, ctime_delta=ctime_delta, dry_run=dry_run)
            else:
                print(f'User {userdir.name} has a job scheduled. Skipping {userdir}.')

def clean_global_dirs(
    paths: Sequence[str],
    ctime_delta: int = _DELTA_ONE_WEEK,
    dry_run: bool = False
) -> None:
    """Delete the contents of the specified paths (not the paths themselves).

    The ctime of the immediate children of each path is compared to the current
    time: if the item is more recent than ctime_delta, the deletion is skipped.

    If the node is not in a drained or idle state, the operation is skipped.
    """
    if _get_node_state() in (_STATE_DRAIN, _STATE_IDLE):
        for path in paths:
            print(f'Cleaning up {path}...')
            for child in Path(path).iterdir():
                _rmr(child, ctime_delta=ctime_delta, dry_run=dry_run)
    else:
        print("The node is not idle. Skipping global directories.")

def upgrade_pkgs(dry_run: bool = False) -> None:
    """Carry out OS package upgrades.

    The operation takes place only if the node is idle.
    """
    if _get_node_state() in (_STATE_DRAIN, _STATE_IDLE):
        upgrade_cmd = [_APTGET, '-y', 'dist-upgrade']
        autoremove_cmd = [_APTGET, '-y', 'autoremove']
        if dry_run:
            upgrade_cmd.append('--dry-run')
            autoremove_cmd.append('--dry-run')
        print(f'Upgrading packages...')
        _run([_APTGET, 'update'])
        _run(upgrade_cmd)
        _run(autoremove_cmd)
    else:
        print("The node is not idle. Skipping package upgrades.")

def undrain_or_reboot(dry_run: bool = False) -> None:
    """Reboot if needed to complete an upgrade, otherwise undrain.

    The operation takes place only if the node is idle.
    """
    if not dry_run and Path('/run/reboot-required').exists():
        if _get_node_state() in (_STATE_DRAIN, _STATE_IDLE):
            print(f'Rebooting to apply upgrades...')
            scontrol = _run([
                _SCONTROL,
                'reboot',
                f'nextstate={_STATE_RESUME}',
                'reason=Apply upgrades',
                f'{_HOSTNAME}'])
        else:
            print("The node is not idle. Skipping reboot.")
    else:
        _set_node_state(_STATE_UNDRAIN, dry_run=dry_run)

def _get_free_space(path: str = '/') -> float:
    """Query the ratio of free to total space."""
    usage = shutil.disk_usage(path)
    return usage.free / usage.total

def _get_ctime(path: str) -> int:
    """Obtain ctime from stat() and discard the fractional part."""
    ctime = Path(path).lstat().st_ctime
    return int(ctime)

def _get_node_state() -> str:
    """Query the slurm state of the current node."""
    sinfo = _run([
        _SINFO,
        '--noheader',
        '--Node',
        f'--nodes={_HOSTNAME}',
        '--format=%t'])
    return sinfo.stdout.strip()

def _set_node_state(state: str, dry_run: bool = False) -> int:
    """Assign the specified slurm state to the current node."""
    print(f'Putting the node in {state} state...')
    if not dry_run:
        scontrol = _run([
            _SCONTROL,
            'update',
            f'nodename={_HOSTNAME}',
            f'state={state}',
            'reason=Automated maintenance'])
        return scontrol.returncode
    return 0

def _has_job_in_queue(user: str) -> bool:
    """Determine whether the specified user has a slurm job in the current node's queue."""
    sinfo = _run([
        _SQUEUE,
        '--noheader',
        f'--nodelist={_HOSTNAME}',
        f'--user={user}'])
    return sinfo.stdout.strip()

def _is_real_dir(path: str) -> bool:
    """Determine whether the specified path points to a directory and not a symlink."""
    path_obj = Path(path)
    return path_obj.is_dir() and not path_obj.is_symlink()

def _run(args: Sequence[str], timeout: int = _DURATION_ONE_HOUR) -> subprocess.CompletedProcess:
    """A convenience wrapper around subprocess.run."""
    return subprocess.run(args, timeout=timeout, capture_output=True, check=True, encoding="utf-8")

def _rmr(path: str, ctime_delta: int = None, dry_run: bool = False) -> None:
    """Delete the specified file or directory recursively.

    Symbolic links are not followed.

    ctime_delta can be passed as a number of seconds. If it is specified and the
    latest medatadata change on the target path is more recent than ctime_delta,
    the operation is skipped. For example, ctime_delta == 3600 causes the
    operation to be skipped if the ctime of path is more recent than an hour ago.
    """
    if (not ctime_delta) or ((_NOW - _get_ctime(path)) > ctime_delta):
        print(f'Deleting {path}...')
        if not dry_run:
            if _is_real_dir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                Path(path).unlink(missing_ok=True)
    else:
        print(f'The ctime of {path} is more recent than the specified delta. Skipping.')

if __name__ == '__main__':
    sys.exit(main())
