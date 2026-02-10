"""
Git operations for committing content to the MMTUK repo.

Supports batched publishing: content mutations use commit_locally() to
accumulate commits, and push_to_remote() sends them all at once.
"""

import logging
import threading
from pathlib import Path

import git
from django.conf import settings

logger = logging.getLogger(__name__)

# Module-level lock to serialise git operations
_git_lock = threading.Lock()


def _repo_url():
    """Build the authenticated repo URL."""
    token = settings.GITHUB_TOKEN
    repo = settings.GITHUB_REPO
    return f'https://{token}@github.com/{repo}.git'


def _get_repo():
    """Return the git.Repo object for the clone directory (must already exist)."""
    clone_dir = Path(settings.REPO_CLONE_DIR)
    return git.Repo(str(clone_dir))


def has_unpushed_commits():
    """
    Check if there are local commits not yet pushed to origin/branch.
    Returns True if there are unpushed commits.
    """
    clone_dir = Path(settings.REPO_CLONE_DIR)
    if not clone_dir.exists():
        return False

    try:
        repo = _get_repo()
        branch = settings.GITHUB_BRANCH
        local_sha = repo.head.commit.hexsha
        remote_sha = repo.remotes.origin.refs[branch].commit.hexsha
        if local_sha == remote_sha:
            return False
        # Check if local is ahead of remote
        ahead = list(repo.iter_commits(f'origin/{branch}..{branch}'))
        return len(ahead) > 0
    except Exception:
        return False


def ensure_repo():
    """
    Ensure an up-to-date clone of the repo exists.
    Clones if missing. If local unpushed commits exist, fetches and rebases
    to preserve them. Otherwise does a hard reset to origin/branch.
    """
    clone_dir = Path(settings.REPO_CLONE_DIR)
    branch = settings.GITHUB_BRANCH

    if not clone_dir.exists():
        logger.info('Cloning repo to %s', clone_dir)
        repo = git.Repo.clone_from(
            _repo_url(),
            str(clone_dir),
            branch=branch,
        )
        return repo

    repo = git.Repo(str(clone_dir))
    origin = repo.remotes.origin

    # Update remote URL in case token changed
    origin.set_url(_repo_url())

    logger.info('Fetching latest from origin/%s', branch)
    origin.fetch()
    repo.git.checkout(branch)

    # Check for unpushed local commits
    try:
        ahead = list(repo.iter_commits(f'origin/{branch}..{branch}'))
    except Exception:
        ahead = []

    if ahead:
        # Preserve local commits by rebasing onto latest remote
        logger.info('Found %d unpushed local commits, rebasing onto origin/%s', len(ahead), branch)
        try:
            repo.git.rebase(f'origin/{branch}')
        except git.GitCommandError:
            logger.warning('Rebase failed, aborting and resetting')
            try:
                repo.git.rebase('--abort')
            except Exception:
                pass
            repo.git.reset('--hard', f'origin/{branch}')
    else:
        repo.git.reset('--hard', f'origin/{branch}')

    return repo


def write_file_to_repo(relative_path, content_bytes):
    """
    Write a file into the cloned repo at the given relative path.
    Creates parent directories as needed.
    content_bytes can be str (for markdown) or bytes (for images).
    """
    clone_dir = Path(settings.REPO_CLONE_DIR)
    full_path = clone_dir / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(content_bytes, str):
        full_path.write_text(content_bytes, encoding='utf-8')
    else:
        full_path.write_bytes(content_bytes)

    logger.info('Wrote file: %s', relative_path)


def write_file_to_output(relative_path, content_bytes):
    """
    Write a file to the local output/ directory (for DEBUG mode).
    """
    output_dir = Path(settings.OUTPUT_DIR)
    full_path = output_dir / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(content_bytes, str):
        full_path.write_text(content_bytes, encoding='utf-8')
    else:
        full_path.write_bytes(content_bytes)

    logger.info('Wrote output file: %s', relative_path)


def read_file_from_repo(relative_path):
    """
    Read a file from the cloned repo. Returns the file content as a string,
    or None if the file doesn't exist.
    """
    clone_dir = Path(settings.REPO_CLONE_DIR)
    full_path = clone_dir / relative_path

    if not full_path.exists():
        # In DEBUG mode, also check output dir
        if settings.DEBUG:
            output_path = Path(settings.OUTPUT_DIR) / relative_path
            if output_path.exists():
                return output_path.read_text(encoding='utf-8')
        return None

    return full_path.read_text(encoding='utf-8')


def list_files_in_directory(relative_dir, pattern='*.md'):
    """
    List files matching a glob pattern in a directory within the cloned repo.
    Returns a list of relative paths (strings) from the repo root.
    """
    clone_dir = Path(settings.REPO_CLONE_DIR)
    dir_path = clone_dir / relative_dir

    if not dir_path.exists():
        return []

    files = []
    for f in dir_path.glob(pattern):
        if f.is_file():
            files.append(str(f.relative_to(clone_dir)).replace('\\', '/'))
    return sorted(files)


def delete_file_from_repo(relative_path):
    """
    Delete a file from the cloned repo.
    Returns True if the file was deleted, False if it didn't exist.
    """
    clone_dir = Path(settings.REPO_CLONE_DIR)
    full_path = clone_dir / relative_path

    if not full_path.exists():
        return False

    full_path.unlink()
    logger.info('Deleted file: %s', relative_path)
    return True


def commit_locally(files, commit_message, author_name='MMTUK CMS', author_email='cms@mmtuk.org'):
    """
    Stage and commit files locally without pushing to the remote.
    files: list of relative paths within the repo (use None for deletions
           that are already staged via git rm).
    Returns the commit SHA on success.

    In DEBUG mode, skips git operations entirely.
    """
    with _git_lock:
        if settings.DEBUG:
            logger.info('DEBUG mode: skipping git commit. Files: %s', files)
            return 'debug-no-push'

        clone_dir = Path(settings.REPO_CLONE_DIR)
        repo = git.Repo(str(clone_dir))

        # Stage files
        for f in files:
            full_path = clone_dir / f
            if full_path.exists():
                repo.index.add([f])
            else:
                # File was deleted — stage the removal
                try:
                    repo.index.remove([f])
                except Exception:
                    logger.warning('Could not stage removal of %s', f)

        # Commit
        actor = git.Actor(author_name, author_email)
        commit = repo.index.commit(commit_message, author=actor, committer=actor)
        sha = commit.hexsha
        logger.info('Created local commit %s: %s', sha[:8], commit_message)

        return sha


def push_to_remote():
    """
    Push all local commits to the remote.
    Returns the number of commits that were pushed.

    In DEBUG mode, returns 0.
    """
    with _git_lock:
        if settings.DEBUG:
            logger.info('DEBUG mode: skipping push')
            return 0

        clone_dir = Path(settings.REPO_CLONE_DIR)
        if not clone_dir.exists():
            return 0

        repo = git.Repo(str(clone_dir))
        branch = settings.GITHUB_BRANCH

        # Count commits ahead of remote
        try:
            ahead = list(repo.iter_commits(f'origin/{branch}..{branch}'))
            count = len(ahead)
        except Exception:
            count = 0

        if count == 0:
            logger.info('No unpushed commits to push')
            return 0

        # Push (retry once with rebase on failure)
        try:
            repo.remotes.origin.push()
        except git.GitCommandError:
            logger.warning('Push failed, pulling with rebase and retrying...')
            repo.git.pull('--rebase')
            repo.remotes.origin.push()

        logger.info('Pushed %d commit(s) to origin/%s', count, branch)
        return count


def get_unpushed_changes():
    """
    Return a list of unpushed commits as dicts with sha, message, author, date.
    Returns an empty list in DEBUG mode or if no unpushed commits exist.
    """
    if settings.DEBUG:
        return []

    clone_dir = Path(settings.REPO_CLONE_DIR)
    if not clone_dir.exists():
        return []

    try:
        repo = git.Repo(str(clone_dir))
        branch = settings.GITHUB_BRANCH

        # Fetch to make sure we have latest remote state
        repo.remotes.origin.fetch()

        ahead = list(repo.iter_commits(f'origin/{branch}..{branch}'))
        return [
            {
                'sha': c.hexsha[:8],
                'message': c.message.strip(),
                'author': str(c.author),
                'date': c.committed_datetime.isoformat(),
            }
            for c in ahead
        ]
    except Exception:
        logger.exception('Failed to get unpushed changes')
        return []


def commit_and_push(files, commit_message, author_name='MMTUK CMS', author_email='cms@mmtuk.org'):
    """
    Stage, commit, and push files to the remote repo.
    files: list of relative paths within the repo.
    Returns the commit SHA on success.

    In DEBUG mode, skips the push and writes to output/ instead.

    This is kept for backward compatibility (e.g. approval workflow where
    immediate publish makes sense). Internally uses commit_locally + push_to_remote.
    """
    sha = commit_locally(files, commit_message, author_name, author_email)
    if sha != 'debug-no-push':
        push_to_remote()
    return sha
