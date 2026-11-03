"""Keep test fixtures off system temporary storage, which scratch.py refuses.

Import before creating temporary directories. Leaves an acceptable temp dir alone.
"""
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scratch  # noqa: E402

try:
    scratch.require_disk(Path(tempfile.gettempdir()))
except ValueError:
    ROOT = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "okf-tests"
    ROOT.mkdir(parents=True, exist_ok=True)
    scratch.require_disk(ROOT)
    os.environ.update(TMPDIR=str(ROOT), TMP=str(ROOT), TEMP=str(ROOT))
    tempfile.tempdir = str(ROOT)


def remove_tree(path):
    """Remove an owned test fixture, including Windows read-only Git objects."""
    target = Path(path).resolve()
    temporary = Path(tempfile.gettempdir()).resolve()
    if target == temporary or temporary not in target.parents:
        raise ValueError(f'fixture cleanup must stay below {temporary}: {target}')

    def retry(function, name, failure):
        if not isinstance(failure[1], PermissionError):
            raise failure[1]
        candidate = Path(name).resolve()
        if candidate != target and target not in candidate.parents:
            raise ValueError(f'cleanup escaped fixture: {candidate}')
        os.chmod(name, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        function(name)

    shutil.rmtree(target, onerror=retry)


def directory_link(link, target):
    """Use a native directory alias without requiring Windows symlink privilege."""
    link, target = Path(link), Path(target).resolve()
    if os.name == 'nt':
        subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(link), str(target)],
                       check=True, capture_output=True, timeout=10)
    else:
        link.symlink_to(target, target_is_directory=True)
