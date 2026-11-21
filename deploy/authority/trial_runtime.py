"""Required source-local critical acceptance using existing isolated execution."""
import json
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

from trusted_ci_policy import require, sha


def archive(files):
    from trial_specimen import manifest
    manifest(files)
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as stream:
        for name, item in sorted(files.items()):
            entry = tarfile.TarInfo('candidate/'+name)
            entry.size = len(item['content'])
            entry.mode = 0o755 if item['executable'] else 0o644
            stream.addfile(entry, io.BytesIO(item['content']))
    return output.getvalue()


def preflight(image, runtime):
    require(sys.platform == 'linux' and os.geteuid() == 0, 'strict acceptance requires a Linux root host')
    require(runtime in ('docker', 'podman') and shutil.which(runtime), 'existing Linux container engine required')
    require(isinstance(image, str) and re.fullmatch(r'[A-Za-z0-9._/:-]+@sha256:[0-9a-f]{64}', image),
            'independently pinned acceptance image required')
    result = subprocess.run([runtime, 'image', 'inspect', '--format', '{{json .RepoDigests}}', image],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            encoding='utf-8', timeout=30, check=False)
    require(result.returncode == 0, 'approved cached image is unavailable; no pull is authorized')
    values = json.loads(result.stdout)
    require(isinstance(values, list) and image in values, 'exact approved cached image digest unavailable')


def pinned_kit(root, pin):
    """Read an immutable source commit, never the contaminated physical tree."""
    import install
    from submission import read_export
    require(sha(pin), 'immutable fixture source commit required')
    root = Path(root).resolve()
    def git(*args):
        result = subprocess.run(['git', '-C', str(root), *args], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
        require(result.returncode == 0, 'immutable fixture source read failed')
        return result.stdout
    require(git('rev-parse', pin+'^{commit}').decode().strip() == pin, 'exact fixture source commit unavailable')
    files = read_export(git('archive', '--format=tar', pin))
    with tempfile.TemporaryDirectory(prefix='agentic-pinned-kit-') as directory:
        target = Path(directory)
        for name, item in files.items():
            path = target.joinpath(*name.split('/'))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(item['content'])
        names = install.kit_files(target)
        require(names and all(name in files for name in names), 'complete immutable KIT inventory required')
        return {name: files[name] for name in names}


def verify(source, deployment, snapshot, job, guard, clock, runtime='docker'):
    """No injected Box, disk, controller or command results can establish success."""
    import service
    image = deployment['policy']['image']
    preflight(image, runtime)
    def cached(d, before):
        require(d['policy']['image'] == image, 'acceptance image changed after admission')
        before(); preflight(image, runtime); before()
    return service._verify_actions(source, deployment, snapshot, job, guard, clock,
                                   image_loader=cached, runtime=runtime)
