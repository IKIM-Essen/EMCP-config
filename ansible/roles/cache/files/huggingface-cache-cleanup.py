#!/usr/bin/env python3

from datetime import datetime
from huggingface_hub import scan_cache_dir

expiry = 21  # in days
now = datetime.now()
cache_info = scan_cache_dir()

to_clean = []
for repo in cache_info.repos:
    delta = now - datetime.fromtimestamp(repo.last_accessed)
    if delta.days >= expiry:
        print(f"{repo.size_on_disk_str:>8}", f"{delta.days:>4} days", repo.repo_id)
        to_clean += [revision.commit_hash for revision in repo.revisions]

delete_strategy = cache_info.delete_revisions(*to_clean)
print(f"Will free {delete_strategy.expected_freed_size_str}.")
delete_strategy.execute()
