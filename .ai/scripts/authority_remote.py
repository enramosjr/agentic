"""Stdlib routing to an independently pinned optional native setup release.

The installed release supplies the origin, immutable revision and exact file
inventory. Neither candidate configuration nor a command argument can replace it.
"""
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
from urllib import error, request
from urllib.parse import urlsplit
import zipfile

import authority_release
import authority_private
from trusted_ci_github import NoRedirect
from trusted_ci_policy import Refusal, loads, object_fields, positive, require, sha

CHECKOUT = Path(__file__).resolve().parents[2]
ENTRY = 'deploy/authority/operator_setup.py'
REQUIREMENTS = 'deploy/authority/requirements-auth.txt'
MAX_ARCHIVE = 64 * 1024 * 1024


def fetch(route, binary=False):
    require(isinstance(route, str) and re.fullmatch(
        r'/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/(?:commits|zipball)/[0-9a-f]{40})?', route),
        'fixed release API route required')
    url = 'https://api.github.com' + route
    opener = request.build_opener(NoRedirect())
    try:
        for _ in range(3):
            try:
                with opener.open(request.Request(url, headers={'User-Agent': 'AGENTIC-release-client',
                    'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}), timeout=30) as response:
                    raw = response.read((MAX_ARCHIVE if binary else 1024 * 1024) + 1)
                require(len(raw) <= (MAX_ARCHIVE if binary else 1024 * 1024), 'release response exceeds limit')
                return raw if binary else loads(raw)
            except error.HTTPError as exc:
                try:
                    location = exc.headers.get('Location', '')
                    target = urlsplit(location)
                    require(binary and exc.code in (301, 302, 303, 307) and
                            target.scheme == 'https' and target.hostname == 'codeload.github.com' and
                            target.port in (None, 443) and not target.username and not target.password,
                            'release origin or download refused')
                    url = location
                finally: exc.close()
    except (error.URLError, OSError, ValueError):
        raise Refusal('pinned release unavailable') from None
    raise Refusal('release redirect limit exceeded')


def obtain(pin, root, api=fetch):
    object_fields(pin, ('repository', 'repository_id', 'revision', 'archive_sha256', 'files'), 'trusted bootstrap release')
    require(isinstance(pin['repository'], str) and re.fullmatch(
        '[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', pin['repository']) and
        all(v not in ('.', '..') for v in pin['repository'].split('/')) and
        positive(pin['repository_id']) and sha(pin['revision']) and
        isinstance(pin['archive_sha256'], str) and re.fullmatch('[0-9a-f]{64}', pin['archive_sha256']) and
        isinstance(pin['files'], dict) and 0 < len(pin['files']) <= 500 and
        {ENTRY, REQUIREMENTS} <= set(pin['files']), 'independently pinned bootstrap release required')
    for name, fingerprint in pin['files'].items():
        require(isinstance(name, str) and str(PurePosixPath(name)) == name and
                not PurePosixPath(name).is_absolute() and '\\' not in name and
                all(re.fullmatch('[A-Za-z0-9_.-]+', part) and part not in ('.', '..') for part in name.split('/')) and
                name.startswith(('.ai/scripts/', '.ai/trusted-ci/', '.ai/docs/', 'deploy/authority/')) and
                isinstance(fingerprint, str) and re.fullmatch('[0-9a-f]{64}', fingerprint), 'fixed release file inventory required')
    route = '/repos/' + pin['repository']
    repository = api(route)
    require(repository.get('id') == pin['repository_id'] and repository.get('full_name') == pin['repository'],
            'trusted release repository identity changed')
    require(api(route + '/commits/' + pin['revision']).get('sha') == pin['revision'], 'trusted release revision differs')
    raw = api(route + '/zipball/' + pin['revision'], binary=True)
    require(isinstance(raw, bytes) and len(raw) <= MAX_ARCHIVE and
            hashlib.sha256(raw).hexdigest() == pin['archive_sha256'], 'trusted release archive differs')
    selected = {}
    expanded = 0
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            require(len(entries) <= 20000 and len({v.filename for v in entries}) == len(entries),
                    'bounded unique release archive required')
            for entry in entries:
                name = entry.filename.partition('/')[2]
                if name not in pin['files']: continue
                require(name not in selected and entry.file_size <= 1024 * 1024 and
                        not entry.is_dir() and stat.S_IFMT(entry.external_attr >> 16) in (0, stat.S_IFREG),
                        'plain bounded release file required')
                expanded += entry.file_size
                require(expanded <= MAX_ARCHIVE, 'expanded bootstrap release exceeds limit')
                value = archive.read(entry)
                require(hashlib.sha256(value).hexdigest() == pin['files'][name], 'trusted release file differs')
                selected[name] = value
    except (zipfile.BadZipFile, RuntimeError, OSError):
        raise Refusal('invalid pinned release archive') from None
    require(set(selected) == set(pin['files']) and sum(map(len, selected.values())) <= MAX_ARCHIVE,
            'complete bounded bootstrap release required')
    root = Path(root)
    require(root.is_absolute() and '..' not in root.parts and not root.is_relative_to(CHECKOUT) and not root.exists(),
            'fresh release directory outside coding checkout required')
    authority_private._trusted_parents(root)
    root.mkdir(mode=0o700)
    authority_private._harden_new(root, directory=True)
    for name, value in selected.items():
        path = root / name
        for parent in reversed(path.parents):
            if parent == root or not parent.is_relative_to(root): continue
            if not parent.exists():
                parent.mkdir(mode=0o700)
                authority_private._harden_new(parent, directory=True)
            authority_private.verify(parent, directory=True)
        with path.open('xb') as stream:
            authority_private._harden_new(path, directory=False)
            stream.write(value)
    return root


def environment():
    # Normal gh/browser authentication belongs only to this trusted operator
    # process. No service-purpose root or Python import override is inherited.
    keys = ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'PATH', 'HOME', 'USERPROFILE',
            'APPDATA', 'LOCALAPPDATA', 'DISPLAY', 'WAYLAND_DISPLAY', 'XDG_RUNTIME_DIR',
            'DBUS_SESSION_BUS_ADDRESS', 'LANG')
    return {key: os.environ[key] for key in keys if key in os.environ}


def execute(root, command):
    require(sys.version_info >= (3, 11), 'optional native setup requires Python 3.11 or newer; local clients support 3.9')
    env = environment()
    authority_private._trusted_parents(Path(root))
    authority_private.verify(Path(root), directory=True)
    virtual = Path(root).parent / 'environment'
    try:
        subprocess.run([sys.executable, '-I', '-m', 'venv', str(virtual)], env=env,
                       cwd=root, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        python = virtual / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        subprocess.run([str(python), '-I', '-m', 'pip', 'install', '--disable-pip-version-check', '--no-input',
                        '--isolated', '-r', str(Path(root) / REQUIREMENTS)], env=env, cwd=root, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
        return subprocess.run([str(python), '-I', str(Path(root) / ENTRY), *command],
                              env=env, cwd=root, check=False).returncode
    except (OSError, subprocess.SubprocessError):
        raise Refusal('optional pinned setup runtime unavailable') from None


def route(command, arguments):
    require(command in ('connect', 'setup') and not arguments,
            'this remote operation has no native route; candidate file arguments are not accepted')
    pin = authority_release.BOOTSTRAP_RELEASE
    require(pin is not None, 'no independently approved bootstrap release is published in this build')
    with tempfile.TemporaryDirectory(prefix='agentic-native-release-', dir=str(Path.home())) as temporary:
        authority_private._harden_new(Path(temporary), directory=True)
        root = obtain(pin, Path(temporary) / 'release', fetch)
        return execute(root, [command])
