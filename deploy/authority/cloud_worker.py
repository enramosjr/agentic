"""Standalone disposable-host worker. Inputs/results stay outside candidate mounts."""
from __future__ import annotations

import base64
import hashlib
import gzip
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import sys
import tarfile
import tempfile
import time
from urllib import request
from urllib.parse import unquote, urlsplit

LIMIT = 64 * 1024 * 1024


def ensure(condition, message):
    if not condition:
        raise ValueError(message)


def unpack(raw, destination):
    ensure(isinstance(raw, bytes) and len(raw) <= LIMIT, 'archive input exceeds limit')
    destination = Path(destination)
    ensure(not destination.exists(), 'fresh archive destination required')
    if raw.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            raw = stream.read(LIMIT + 1)
        ensure(len(raw) <= LIMIT, 'expanded archive exceeds limit')
    # Bound the complete tar stream BEFORE parsing PAX or other hidden metadata.
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as source:
        entries, names, roots, total = [], set(), set(), 0
        for member in source:
            path = PurePosixPath(member.name)
            ensure(member.name and not path.is_absolute() and '\\' not in member.name and
                   not any(p in ('.', '..') for p in member.name.rstrip('/').split('/')),
                   'unsafe archive path')
            ensure(all(p.lower() != '.git' and ':' not in p and p.rstrip(' .') == p and
                   not re.search(r'[\x00-\x1f\x7f<>"|?*]', p) and
                   p.split('.')[0].upper() not in {'CON', 'PRN', 'AUX', 'NUL',
                     *('COM' + str(n) for n in range(1, 10)), *('LPT' + str(n) for n in range(1, 10))}
                   for p in path.parts), 'nonportable archive path')
            ensure(member.isdir() or member.isfile(), 'archive links and devices refused')
            total += member.size
            ensure(member.size >= 0 and total <= LIMIT and len(entries) < 20000, 'expanded archive exceeds limit')
            normalized = path.as_posix().casefold()
            ensure(normalized not in names, 'duplicate archive path')
            names.add(normalized)
            roots.add(path.parts[0])
            ensure(len(path.parts) > 1 or member.isdir(), 'directory archive root required')
            entries.append((member, path))
        ensure(len(roots) == 1, 'single archive root required')
        destination.mkdir(mode=0o700)
        for member, path in entries:
            if len(path.parts) == 1:
                continue
            target = destination.joinpath(*path.parts[1:])
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as stream, target.open('xb') as output:
                    while True:
                        block = stream.read(65536)
                        if not block:
                            break
                        output.write(block)
                target.chmod(0o555 if member.mode & 0o111 else 0o444)
    return destination


def materialize(lease, bundle, candidate, directory):
    ensure(lease['objects']['bundle']['sha256'] == lease['deployment']['resources']['bundle_sha'],
           'trusted bundle differs from approved deployment')
    for name, raw in (('bundle', bundle), ('candidate', candidate)):
        ensure(hashlib.sha256(raw).hexdigest() == lease['objects'][name]['sha256'], 'input digest mismatch')
    directory = Path(directory)
    directory.mkdir(mode=0o700)
    trusted = unpack(bundle, directory / 'authority')
    source = unpack(candidate, directory / 'candidate')
    # Only this tree is bind-mounted at /source for UID 65534. Its enclosing
    # host directory and the independently loaded authority remain private.
    source.chmod(0o755)
    for path in source.rglob('*'):
        if path.is_dir():
            path.chmod(0o755)
    return trusted, source


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def transfer(lease, name, data=None):
    item = lease['objects'][name]
    url = urlsplit(item['url'])
    ensure(url.scheme == 'https' and url.hostname == lease['deployment']['resources']['artifact_host'] and
           url.port in (None, 443) and not url.username and not url.fragment and
           unquote(url.path) == '/jobs/' + lease['id'] + '/' +
             {'bundle': 'bundle.tgz', 'candidate': 'candidate.tgz', 'report': 'report.json'}[name],
           'storage scope mismatch')
    headers = {'Content-Type': 'application/json'} if data is not None else {}
    if data is not None and lease['deployment']['adapter'] == 'azure':
        headers['x-ms-blob-type'] = 'BlockBlob'
    req = request.Request(item['url'], data=data, headers=headers, method='PUT' if data is not None else 'GET')
    with request.build_opener(NoRedirect()).open(req, timeout=30) as response:
        raw = response.read(LIMIT + 1 if data is None else 8193)
        ensure(len(raw) <= (LIMIT if data is None else 8192), 'storage response exceeds limit')
        return raw


def verify(lease, trusted, candidate):
    sys.path.insert(0, str(trusted / '.ai/scripts'))
    sys.path.insert(0, str(trusted / 'deploy/authority'))
    import authority_release
    authority_release.authorize('hosted-execute')
    from authority_jobs import result, validate_lease
    from trusted_ci_controller import verify as controller
    from trusted_ci_sandbox import Sandbox, command
    from disk import WorkDisk
    validate_lease(lease, int(time.time()))
    p = lease['deployment']['policy']
    code, _ = command(['docker', 'pull', p['image']], seconds=120)
    ensure(code == 0, 'approved runtime image unavailable')
    with WorkDisk('agentic-' + secrets.token_hex(12), p['limits']['disk_mb'],
                  formatter_image=p['image']) as disk:
        with Sandbox(candidate, p, runtime='docker', work_volume=disk.name) as box:
            outcomes = controller(box, p, lease['snapshot'], capture_failure=True)['outcomes']
    validate_lease(lease, int(time.time()))
    return result(lease, outcomes)


def main(argv=None):
    try:
        # An ordinary invocation of this held source build must stop before any
        # network or privileged setup. Remote bootstrap imports its policy from
        # the digest-checked trusted bundle before admission to the controller.
        if '__file__' in globals():
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai/scripts'))
            import authority_release
            authority_release.authorize('hosted-execute')
        args = sys.argv[1:] if argv is None else argv
        ensure(len(args) == 1, 'one encoded job request required')
        raw = base64.b64decode(args[0], validate=True)
        ensure(len(raw) <= 65536, 'job request exceeds limit')
        lease = json.loads(raw)
        ensure(lease['issued'] <= int(time.time()) < lease['expires'], 'job lease expired')
        bundle, candidate = transfer(lease, 'bundle'), transfer(lease, 'candidate')
        with tempfile.TemporaryDirectory(prefix='agentic-cloud-job-') as folder:
            trusted, source = materialize(lease, bundle, candidate, Path(folder) / 'input')
            value = verify(lease, trusted, source)
            payload = json.dumps(value, sort_keys=True, allow_nan=False).encode()
            ensure(len(payload) <= 1024 * 1024, 'report exceeds limit')
            transfer(lease, 'report', payload)
        # The transport completed; success/failure comes from the complete report,
        # not this exit status. The parent validates every critical outcome.
        return 0
    except Exception:
        print('{"state":"blocked","enforcement_active":false,"error":"worker did not certify execution"}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
