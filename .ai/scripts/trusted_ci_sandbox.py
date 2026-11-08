"""Linux candidate execution. The trusted controller and result stay on the host."""
from __future__ import annotations

import io
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import threading
import re

from trusted_ci_policy import Refusal, require, validate_policy


def creation_controls(runtime, name, work, policy, image=None):
    """Shared fixed controls; callers add only their closed profile's mounts."""
    image = policy['image'] if image is None else image
    validate_policy(dict(policy, image=image))
    require(runtime in ('docker', 'podman') and isinstance(work, str) and
            re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', work) and
            name == 'agentic-candidate-' + work, 'owned OCI reservation required')
    limits = policy['limits']
    return [runtime, 'create', '--name', name, '--pull=never',
            '--user=65534:65534', '--read-only', '--network=none', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--pids-limit=' + str(limits['processes']),
            '--memory=' + str(limits['memory_mb']) + 'm', '--memory-swap=' + str(limits['memory_mb']) + 'm',
            '--cpus=1', '--log-driver=none', '--volume', work + ':/work:nocopy']


def effective_probe(policy):
    """Shared trusted pre-candidate kernel, namespace and resource assertions."""
    validate_policy(policy)
    limits = policy['limits']
    return ('import os,pathlib; '
             'assert os.getuid()==65534; '
             'assert os.statvfs("/").f_flag & os.ST_RDONLY; '
             'status=pathlib.Path("/proc/self/status").read_text(); '
             'assert "NoNewPrivs:\\t1" in status; assert "Seccomp:\\t2" in status; '
             'assert "CapEff:\\t0000000000000000" in status; '
             'assert sorted(p.name for p in pathlib.Path("/sys/class/net").iterdir())==["lo"]; '
             'assert int(pathlib.Path("/sys/fs/cgroup/memory.max").read_text())==' +
             str(limits['memory_mb'] * 1024 * 1024) + '; '
             'assert int(pathlib.Path("/sys/fs/cgroup/pids.max").read_text())==' +
             str(limits['processes']) + '; '
             'cpu=pathlib.Path("/sys/fs/cgroup/cpu.max").read_text().split(); '
             'assert cpu[0]!="max" and 0<int(cpu[0])<=int(cpu[1]); '
             'assert not any(k in os.environ for k in '
             '["GITHUB_TOKEN","GH_TOKEN","AGENTIC_READ_TOKEN","AGENTIC_ISSUER_TOKEN",'
             '"ACTIONS_RUNTIME_TOKEN","GITHUB_OUTPUT","GITHUB_ENV"]); '
             'assert not pathlib.Path("/var/run/docker.sock").exists()')


def command(argv, seconds=120, limit=1024 * 1024):
    """Capture untrusted output as bounded data, never relay Actions commands."""
    with subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT) as process:
        chunks, size, overflow = [], [0], threading.Event()

        def read():
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                size[0] += len(chunk)
                if size[0] > limit:
                    overflow.set()
                    process.kill()
                    break
                chunks.append(chunk)
        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        try:
            process.wait(timeout=seconds)
        except subprocess.TimeoutExpired as error:
            process.kill()
            process.wait()
            raise Refusal('execution deadline exceeded') from error
        finally:
            reader.join(timeout=5)
        require(not reader.is_alive(), 'output pipe did not close')
        require(not overflow.is_set(), 'output limit exceeded')
        return process.returncode, b''.join(chunks).decode('utf-8', errors='replace')


def extract(raw, destination, max_bytes=64 * 1024 * 1024):
    """Extract GitHub's one-root tarball after checking every entry, without links."""
    require(isinstance(raw, bytes) and len(raw) <= max_bytes, 'archive download limit exceeded')
    destination = Path(destination)
    require(not destination.exists(), 'extraction destination must be new')
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:*') as tar:
            members, seen, total = [], set(), 0
            for item in tar:
                path = PurePosixPath(item.name)
                require(item.name and path.parts and not path.is_absolute() and '\\' not in item.name and
                        all(x not in ('..', '.git') and ':' not in x for x in path.parts), 'unsafe archive path')
                reserved = {'CON', 'PRN', 'AUX', 'NUL', *('COM' + str(n) for n in range(1, 10)),
                            *('LPT' + str(n) for n in range(1, 10))}
                require(all(part.rstrip(' .') == part and part.split('.')[0].upper() not in reserved and
                            not re.search(r'[\x00-\x1f\x7f<>"|?*]', part) for part in path.parts),
                        'nonportable or device archive path')
                require(item.isfile() or item.isdir(), 'links and special archive entries refused')
                require(item.size >= 0, 'negative archive size')
                total += item.size
                require(total <= max_bytes and len(members) < 20000, 'expanded archive limit exceeded')
                normalized = path.as_posix().casefold()
                require(normalized not in seen, 'duplicate archive path')
                seen.add(normalized)
                members.append((item, path))
            roots = {p.parts[0] for _, p in members if p.parts}
            require(len(roots) == 1, 'single archive root required')
            destination.mkdir(parents=True)
            for item, path in members:
                if len(path.parts) == 1:
                    require(item.isdir(), 'archive root must be directory')
                    continue
                target = destination.joinpath(*path.parts[1:])
                if item.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with tar.extractfile(item) as source, target.open('xb') as output:
                        shutil.copyfileobj(source, output, length=64 * 1024)
                    target.chmod(0o555 if item.mode & 0o111 else 0o444)
    except (tarfile.TarError, OSError) as error:
        raise Refusal('invalid candidate archive: ' + str(error)) from error
    return destination


class Sandbox:
    def __init__(self, source, policy, runtime=None, work_volume=None):
        validate_policy(policy)
        self.source, self.policy = Path(source).resolve(), policy
        self.work = work_volume or os.environ.get('AGENTIC_WORK_VOLUME', '')
        require(isinstance(self.work, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', self.work),
                'externally provisioned AGENTIC_WORK_VOLUME required')
        # Atomic engine name reservation prevents two executions sharing a volume.
        self.name = 'agentic-candidate-' + self.work
        self.runtime = runtime or ('docker' if shutil.which('docker') else 'podman')
        require(self.runtime in ('docker', 'podman'), 'supported OCI runtime required')
        self.created_container = False

    def __enter__(self):
        require(shutil.which(self.runtime), 'Docker or Podman Linux engine required for trusted execution')
        info_field = '{{.Host.OS}}' if self.runtime == 'podman' else '{{.OSType}}'
        code, info = command([self.runtime, 'info', '--format', info_field], seconds=30)
        require(code == 0 and info.strip() == 'linux', 'reachable Linux container engine required')
        require(self.source.is_dir() and not self.source.is_symlink(), 'candidate directory required')
        require(',' not in str(self.source), 'unsupported mount path')
        limits = self.policy['limits']
        code, _ = command([self.runtime, 'volume', 'inspect', self.work])
        require(code == 0, 'work volume must be independently provisioned; implicit creation refused')
        # No Docker build, host environment, writable host mounts or privileged mode.
        argv = creation_controls(self.runtime, self.name, self.work, self.policy) + [
                '--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777',
                '--workdir=/work', '--entrypoint=python3', self.policy['image'],
                '-I', '-c', 'import time; time.sleep(900)']
        if self.runtime == 'docker':
            # Docker refuses archive copy into a read-only rootfs. Expose only
            # the isolated candidate snapshot, never the authority checkout.
            argv[2:2] = ['--mount', 'type=bind,src=' + str(self.source) + ',dst=/source,readonly']
        try:
            code, _ = command(argv, seconds=60)
            require(code == 0, 'container creation failed; approved image must be pre-provisioned')
            self.created_container = True
            if self.runtime == 'podman':
                # Podman can populate a stopped container's read-only rootfs.
                # This also avoids sharing Windows host paths with its backend.
                code, _ = command([self.runtime, 'cp', str(self.source) + '/.', self.name + ':/source'], seconds=60)
                require(code == 0, 'candidate copy failed')
            code, _ = command([self.runtime, 'start', self.name], seconds=30)
            require(code == 0, 'container start failed')
            code, fstype = self.run(['stat', '-f', '-c', '%T', '/work'], cwd='/work')
            require(code == 0 and fstype.strip() in ('ext2/ext3', 'ext4', 'xfs', 'btrfs'),
                    'work volume must be disk-backed')
            script = ('import os,pathlib; s=os.statvfs("/work"); '
                      'assert s.f_blocks*s.f_frsize<=' + str(limits['disk_mb'] * 1024 * 1024) + '; '
                      'assert not [p for p in pathlib.Path("/work").iterdir() if p.name!="lost+found"]')
            require(self.run(['python3', '-I', '-c', script], cwd='/work')[0] == 0,
                    'work volume must be empty and hard-sized within policy limit')
            probe = effective_probe(self.policy)
            require(self.run(['python3', '-I', '-c', probe], cwd='/work')[0] == 0,
                    'effective isolation/resource controls were not established')
            return self
        except BaseException:
            self.close()
            raise

    def run(self, argv, cwd='/work/project'):
        require(isinstance(argv, list) and argv and all(isinstance(a, str) and '\0' not in a for a in argv),
                'argv required')
        require(cwd in ('/work', '/work/project'), 'unsupported sandbox workdir')
        code, output = command([self.runtime, 'exec', '--workdir', cwd,
                        '--env', 'HOME=/work', '--env', 'TMPDIR=/tmp',
                        '--env', 'PYTHONDONTWRITEBYTECODE=1', self.name, *argv],
                       seconds=self.policy['limits']['seconds'])
        require(code < 125, 'container transport or executable unavailable')
        return code, output

    def close(self):
        errors = []
        if self.created_container:
            code, _ = command([self.runtime, 'rm', '--force', self.name], seconds=30)
            if code:
                errors.append('container')
            else:
                self.created_container = False
        require(not errors, 'owned infrastructure cleanup failed; operator inspection required')

    def __exit__(self, *exc):
        self.close()
