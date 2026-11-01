"""Immutable pre-change source oracles distributed with installed qualification."""
import hashlib
import json
from pathlib import Path


DIRECTORY = Path(__file__).with_name('fixtures') / 'qualification-baselines'
HEAD_BASELINE = '43091ae42693646b25f09110d0e860b4f0560b99'
MANIFEST_SHA256 = '67dcad6eba6e0ad916abf2b10ef524fffbdf2549805057c844dfda28c95e97d6'


def read_baseline(revision, source_path, *, directory=DIRECTORY):
    """Read an independently pinned oracle, refusing absent or modified data."""
    try:
        raw = (directory / 'manifest.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
            raise ValueError('compatibility baseline manifest hash mismatch')
        manifest = json.loads(raw)
        matches = [entry for entry in manifest['sources']
                   if entry['revision'] == revision and entry['path'] == source_path]
        if len(matches) != 1:
            raise ValueError('compatibility baseline revision/path not pinned')
        entry = matches[0]
        if Path(entry['file']).name != entry['file']:
            raise ValueError('compatibility baseline file must be local')
        data = (directory / entry['file']).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('compatibility baseline content hash mismatch')
        blob = b'blob ' + str(len(data)).encode('ascii') + b'\0' + data
        if hashlib.sha1(blob).hexdigest() != entry['git_blob']:
            raise ValueError('compatibility baseline Git blob mismatch')
        return data.decode('utf-8')
    except (OSError, UnicodeError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError('compatibility baseline missing or invalid') from error
