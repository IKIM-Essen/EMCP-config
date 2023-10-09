#!/usr/bin/env python3

"""A script for cleaning up local storage on slurm nodes."""
import argparse
from collections.abc import Sequence
from pathlib import Path
import subprocess
import socket
import shutil
import sys

THRESHOLD_DEFAULT=0.2
_STATE_UNDRAIN = 'undrain'
_STATE_DRAIN = 'drain'
_STATE_IDLE = 'idle'
_SINFO = '/usr/bin/sinfo'
_SCONTROL = '/usr/bin/scontrol'
_SQUEUE = '/usr/bin/squeue'
_HOSTNAME = socket.getfqdn().split('.', maxsplit=1)[0]

def main() -> int:
    """Define the command-line parameters and invoke the cleanup function."""
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
        '--dry-run',
        action='store_true',
        help="don't actually perform the actions listed in the output")
    args = parser.parse_args()
    cleanup(
        userdir_roots=args.userdir_root,
        globaldirs=args.globaldir,
        threshold=args.threshold,
        dry_run=args.dry_run)
    return 0

def cleanup(
    userdir_roots: Sequence[str],
    globaldirs: Sequence[str],
    threshold: int = THRESHOLD_DEFAULT,
    dry_run: bool = False
) -> None:
    """Clean up local storage on the current node.

    For each directory to clean up, if the available space is less than the
    specified threshold, the following steps take place:
      1. A slurm command to drain the local node is issued in order to prevent
         the node from accepting jobs while the cleanup takes place.
      2a. If processing a user directory, it is cleaned up only if the user
          has no jobs in the current node's queue.
      2b. If processing a general-purpose directory, it is cleaned up only if
          the current node has no running jobs.
      3. A slurm command to put the node back into service is issued.
    """
    userdir_roots_to_process = [root for root in userdir_roots if _get_free_space(root) < threshold]
    globaldirs_to_process = [path for path in globaldirs if _get_free_space(path) < threshold]
    if userdir_roots_to_process or globaldirs_to_process:
        _set_node_state(_STATE_DRAIN, dry_run=dry_run)
        clean_user_dirs(userdir_roots_to_process, dry_run=dry_run)
        clean_global_dirs(globaldirs_to_process, dry_run=dry_run)
        _set_node_state(_STATE_UNDRAIN, dry_run=dry_run)
    else:
        print('Sufficient disk space. Nothing to do.')

def clean_user_dirs(roots: Sequence[str], dry_run: bool = False) -> None:
    """Delete user directories in the specified paths.

    The specified paths must contain subdirectories named after users.
    For example, given path == '/local/cache', the directory
    structure must be as follows:
    /local/cache/
    |- alice/
    |- bob/
    |- ...

    If a user has a job in the slurm queue on the current node, their
    directories are skipped.
    """
    for root in roots:
        print(f'Cleaning up {root}...')
        for userdir in Path(root).iterdir():
            if _has_job_in_queue(userdir.name):
                print(f'User {userdir.name} has a job scheduled. Skipping {userdir}.')
            else:
                _rmr(userdir, dry_run=dry_run)

def clean_global_dirs(paths: Sequence[str], dry_run: bool = False) -> None:
    """Delete the contents of the specified paths.

    The specified paths themselves are not deleted.

    If the node is not in a drained or idle state, the operation is skipped.
    """
    if _get_node_state() in (_STATE_DRAIN, _STATE_IDLE):
        for path in paths:
            print(f'Cleaning up {path}...')
            for child in Path(path).iterdir():
                _rmr(child, dry_run=dry_run)
    else:
        print("The node is not idle. Skipping global directories.")

def _get_free_space(path: str = '/') -> float:
    """Query the ratio of free to total space."""
    usage = shutil.disk_usage(path)
    return usage.free / usage.total

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
            'reason=Local storage cleanup'])
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

def _run(args: Sequence[str], timeout: int = 10) -> subprocess.CompletedProcess:
    """Convenience wrapper around subprocess.run"""
    return subprocess.run(args, timeout=timeout, capture_output=True, check=True, encoding="utf-8")

def _rmr(path: str, dry_run: bool = False) -> None:
    """Delete the specified file or directory recursively."""
    path_obj = Path(path)
    print(f'Deleting {path_obj}...')
    if not dry_run:
        if path_obj.is_dir():
            shutil.rmtree(path=path_obj, ignore_errors=True)
        else:
            path_obj.unlink(missing_ok=True)

if __name__ == '__main__':
    sys.exit(main())
