"""Keep test fixtures off system temporary storage, which scratch.py refuses.

Import before creating temporary directories. Leaves an acceptable temp dir alone.
"""
import os
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
