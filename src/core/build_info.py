"""Which commit is actually serving this process.

The production QA workflow fires on push and connects to the app before
Streamlit Cloud has finished swapping builds, so it could test the PREVIOUS
commit and report the new one red. That happened to c151597, whose QA started
two seconds after the push.

A timeout would only hide it. Publishing the revision the app is really
running lets the probe verify it is looking at the build it means to test,
and say so plainly when it is not.

The revision is read straight from the git metadata on disk. No subprocess:
the security audit established this codebase shells out nowhere, and reading
two small files keeps it that way.
"""

from __future__ import annotations

import os

from src.core.config import BASE_DIR


def _read(path: str) -> str | None:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def deployed_revision(base_dir: str | None = None) -> str | None:
    """Full commit SHA this checkout is on, or None if it cannot be determined.

    Returns None rather than guessing. A wrong revision is worse than an
    absent one, because the probe would then trust a mismatch it invented.
    """
    root = base_dir or BASE_DIR
    git_dir = os.path.join(root, ".git")

    # A worktree or submodule stores a pointer file instead of a directory.
    if os.path.isfile(git_dir):
        pointer = _read(git_dir) or ""
        if pointer.startswith("gitdir:"):
            git_dir = pointer.split(":", 1)[1].strip()

    head = _read(os.path.join(git_dir, "HEAD"))
    if not head:
        return None

    if not head.startswith("ref:"):
        return head or None  # detached HEAD already holds the SHA

    ref = head.split(":", 1)[1].strip()

    direct = _read(os.path.join(git_dir, ref))
    if direct:
        return direct

    # Fall back to packed-refs, which is how a fresh clone often stores them.
    packed = _read(os.path.join(git_dir, "packed-refs"))
    if packed:
        for line in packed.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split()
            if len(parts) == 2 and parts[1] == ref:
                return parts[0]
    return None


def short_revision(base_dir: str | None = None) -> str | None:
    rev = deployed_revision(base_dir)
    return rev[:7] if rev else None
