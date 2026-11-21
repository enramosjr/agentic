"""Closed managed-coding profile and byte-safe source/export primitives.

Public execution remains held. The trusted parent owns admission, engine/disk
lifetime and submission; candidate bytes cannot choose mounts or executables.
"""
import copy
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

sys.path[:0] = [str(Path(__file__).resolve().parent),
                str(Path(__file__).resolve().parents[2] / '.ai/scripts')]
import authority_release
from codex_harness import profile
from coding_transport import capture_export, ENGINE_ENVIRONMENT
import submission
from trusted_ci_policy import loads, require
import trusted_ci_sandbox as sandbox


def materialize(raw, root):
    files = submission.read_export(raw)
    root = Path(root)
    require(not root.exists() and not root.is_symlink() and root.parent.is_dir() and not root.parent.is_symlink(),
            'fresh plain worker workspace required')
    root.mkdir(mode=0o755)
    for name, item in files.items():
        target = root.joinpath(*submission.path_parts(name))
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0),
                             0o755 if item['executable'] else 0o644)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(item['content'])


def export_tree(root):
    """Read only a stopped workspace; never execute candidate commands/Git config."""
    root = Path(root)
    require(root.is_dir() and not root.is_symlink() and
            not getattr(root.lstat(), 'st_file_attributes', 0) & 0x400, 'plain stopped worker export root required')
    files, total = {}, 0
    def unreadable(error):
        raise error
    for parent, directories, names in os.walk(root, followlinks=False, onerror=unreadable):
        for name in directories:
            value = (Path(parent) / name).lstat()
            require(stat.S_ISDIR(value.st_mode) and not getattr(value, 'st_file_attributes', 0) & 0x400,
                    'export directory links refused')
        directories[:] = [name for name in directories if name.casefold() != '.git']
        for name in names:
            path = Path(parent) / name
            relative = path.relative_to(root).as_posix()
            parts = submission.path_parts(relative, allow_git=True)
            if any(part.casefold() == '.git' for part in parts):
                continue
            before = path.lstat()
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                    not getattr(before, 'st_file_attributes', 0) & 0x400 and
                    len(files) < submission.MAX_FILES and before.st_size <= submission.MAX_BYTES - total,
                    'export links, special files or size limit refused')
            descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            with os.fdopen(descriptor, 'rb') as stream:
                opened = os.fstat(stream.fileno())
                require((opened.st_dev, opened.st_ino, opened.st_size) ==
                        (before.st_dev, before.st_ino, before.st_size), 'export file changed before open')
                raw = stream.read(before.st_size + 1)
                after = os.fstat(stream.fileno())
            require(len(raw) == before.st_size and (after.st_size, after.st_mtime_ns) ==
                    (before.st_size, before.st_mtime_ns), 'export changed during read')
            total += len(raw)
            files[relative] = dict(content=raw, executable=bool(before.st_mode & 0o111))
    return submission.pack_export(files)


class CodingSandbox(sandbox.Sandbox):
    def __init__(self, deployment, work_volume, relay_directory, runtime='docker'):
        self.deployment = copy.deepcopy(deployment)
        self.resources = profile(self.deployment)
        directory = Path(relay_directory)
        require(directory.is_absolute() and directory.is_dir() and not directory.is_symlink() and
                ',' not in str(directory), 'plain relay directory required')
        self.relay_directory = directory.resolve()
        super().__init__(directory, self.deployment['policy'], runtime=runtime, work_volume=work_volume)
        self.container_id = None
        self.stopped = False

    def create_arguments(self):
        return sandbox.creation_controls(self.runtime, self.name, self.work, self.policy,
            self.resources['coding_image']) + [
            '--mount', 'type=bind,src=' + str(self.relay_directory) + ',dst=/run/agentic-model,readonly',
            '--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777',
            '--tmpfs=/home/agentic:rw,noexec,nosuid,nodev,size=16m,mode=0700,uid=65534,gid=65534',
            '--workdir=/work', '--entrypoint=python3', self.resources['coding_image'],
            '-I', '-c', 'import time; time.sleep(900)']

    def __enter__(self):
        authority_release.authorize('protected-run')
        return self._enter()

    def _enter(self):
        require(sys.platform == 'linux' and self.relay_directory.name.startswith('agentic-model-') and
                set(path.name for path in self.relay_directory.iterdir()) == {'relay.sock'} and
                stat.S_ISSOCK((self.relay_directory / 'relay.sock').lstat().st_mode) and
                self.relay_directory.stat().st_uid == os.geteuid(), 'owned Linux relay socket required')
        field = '{{.Host.OS}}' if self.runtime == 'podman' else '{{.OSType}}'
        code, info = sandbox.command([self.runtime, 'info', '--format', field], seconds=30)
        require(code == 0 and info.strip() == 'linux', 'Linux engine required')
        require(sandbox.command([self.runtime, 'volume', 'inspect', self.work])[0] == 0,
                'independently provisioned work volume required')
        try:
            code, identity = sandbox.command(self.create_arguments(), seconds=60)
            require(code == 0, 'coding container creation failed')
            self.created_container = True
            require(re.fullmatch('[0-9a-f]{64}', identity.strip()), 'created coding container identity unavailable')
            self.container_id = identity.strip()
            require(sandbox.command([self.runtime, 'start', self.container_id], seconds=30)[0] == 0, 'coding container start failed')
            self.inspect()
            require(self.run(['python3', '-I', '-c', sandbox.effective_probe(self.policy)], cwd='/work')[0] == 0,
                    'effective coding controls were not established')
            code, filesystem = self.run(['stat', '-f', '-c', '%T', '/work'], cwd='/work')
            require(code == 0 and filesystem.strip() in ('ext2/ext3', 'ext4', 'xfs', 'btrfs'), 'disk-backed work volume required')
            capacity = ('import os,pathlib; s=os.statvfs("/work"); '
                'assert s.f_blocks*s.f_frsize<=' + str(self.policy['limits']['disk_mb'] * 1024 * 1024) + '; '
                'assert not [p for p in pathlib.Path("/work").iterdir() if p.name!="lost+found"]')
            require(self.run(['python3', '-I', '-c', capacity], cwd='/work')[0] == 0, 'fresh hard-sized work volume required')
            return self
        except BaseException:
            self.close()
            raise

    def inspect(self):
        require(self.container_id is not None, 'owned coding container identity required')
        code, raw = sandbox.command([self.runtime, 'inspect', '--format', '{{json .}}', self.container_id])
        require(code == 0, 'coding container readback unavailable')
        value = loads(raw)
        require(isinstance(value, dict) and value.get('State', {}).get('Running') is True and
                value.get('Config', {}).get('Image') == self.resources['coding_image'] and
                value.get('Config', {}).get('User') == '65534:65534', 'coding image/user/readiness differs')
        identity = value.get('Id')
        require(isinstance(identity, str) and re.fullmatch('[0-9a-f]{64}', identity) and
                self.container_id in (None, identity), 'coding container identity differs')
        host = value.get('HostConfig', {})
        require(host.get('ReadonlyRootfs') is True and host.get('Privileged') is False and
                host.get('NetworkMode') == 'none' and host.get('PidMode', '') in ('', 'private'),
                'coding container host isolation differs')
        mounts = value.get('Mounts')
        require(isinstance(mounts, list), 'coding mount readback required')
        entries = [item for item in mounts if item.get('Type') != 'tmpfs']
        data = {item['Destination']: item for item in entries}
        require(len(data) == len(entries) == 2 and set(data) == {'/work', '/run/agentic-model'} and
                data['/work'].get('Type') == 'volume' and data['/work'].get('Name') == self.work and data['/work'].get('RW') is True and
                data['/run/agentic-model'].get('Type') == 'bind' and data['/run/agentic-model'].get('RW') is False and
                data['/run/agentic-model'].get('Source') == str(self.relay_directory), 'coding mounts differ')
        self.container_id = identity
        return value

    def run(self, argv, cwd='/work/project'):
        require(self.created_container and not self.stopped and self.container_id is not None and
                isinstance(argv, list) and argv and all(isinstance(a, str) and '\0' not in a for a in argv) and
                cwd in ('/work', '/work/project'), 'owned coding execution required')
        code, output = sandbox.command([self.runtime, 'exec', '--workdir', cwd,
            '--env', 'HOME=/home/agentic', '--env', 'TMPDIR=/tmp', '--env', 'PYTHONDONTWRITEBYTECODE=1',
            self.container_id, *argv], seconds=self.policy['limits']['seconds'])
        require(code < 125, 'coding transport or executable unavailable')
        return code, output

    def _attach(self):
        require(self.created_container and not self.stopped and self.container_id is not None,
                'running owned coding container required')
        self.inspect()
        return subprocess.Popen([self.runtime, 'exec', '-i', '--workdir', '/work',
            '--env', 'HOME=/home/agentic', '--env', 'TMPDIR=/tmp', '--env', 'PYTHONDONTWRITEBYTECODE=1',
            self.container_id, 'python3', '-I', '/opt/agentic/deploy/authority/coding_stdio.py', '--stdio'],
            env=ENGINE_ENVIRONMENT,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True, close_fds=True, bufsize=0)

    def stop(self):
        require(self.created_container and self.container_id is not None, 'owned coding stop identity required')
        if not self.stopped:
            require(sandbox.command([self.runtime, 'stop', '--time', '0', self.container_id], seconds=30)[0] == 0,
                    'coding container stop failed')
        code, raw = sandbox.command([self.runtime, 'inspect', '--format', '{{json .}}', self.container_id], seconds=30)
        require(code == 0, 'coding stop readback unavailable')
        state = loads(raw)
        require(state.get('Id') == self.container_id and state.get('State', {}).get('Running') is False and
                state.get('State', {}).get('Status') in ('exited', 'stopped'),
                'owned coding container termination not confirmed')
        self.stopped = True

    def _export(self, guard):
        self.stop()
        self.close()  # Release the reservation only after whole-container exit.
        guard()
        arguments = sandbox.creation_controls(self.runtime, self.name, self.work, self.policy,
                                               self.resources['coding_image'])
        arguments[-1] += ',ro'
        arguments += ['--entrypoint=python3', self.resources['coding_image'], '-I',
                      '/opt/agentic/deploy/authority/coding_stdio.py', '--export']
        code, raw = sandbox.command(arguments, seconds=30)
        require(code == 0 and re.fullmatch('[0-9a-f]{64}', raw.strip()),
                'exporter creation identity uncertain; trusted inspection required')
        identity = raw.strip()
        removed = False
        def remove():
            nonlocal removed
            if not removed:
                require(sandbox.command([self.runtime, 'rm', '--force', identity], seconds=30)[0] == 0,
                        'owned exporter removal failed')
                removed = True
        try:
            code, raw = sandbox.command([self.runtime, 'inspect', '--format', '{{json .}}', identity], seconds=30)
            require(code == 0, 'exporter readback unavailable')
            value = loads(raw)
            require(value.get('Id') == identity and value.get('Config', {}).get('User') == '65534:65534' and
                    value.get('Config', {}).get('Image') == self.resources['coding_image'] and
                    value.get('HostConfig', {}).get('ReadonlyRootfs') is True and
                    value.get('HostConfig', {}).get('Privileged') is False and
                    value.get('HostConfig', {}).get('NetworkMode') == 'none' and
                    isinstance(value.get('Mounts'), list) and len(value['Mounts']) == 1 and
                    value['Mounts'][0].get('Type') == 'volume' and value['Mounts'][0].get('Name') == self.work and
                    value['Mounts'][0].get('Destination') == '/work' and value['Mounts'][0].get('RW') is False,
                    'readonly owned exporter controls differ')
            result = capture_export([self.runtime, 'start', '--attach', identity], guard, remove)
            submission.read_export(result)
            return result
        finally:
            remove()

    def close(self):
        if self.created_container:
            require(self.container_id is not None, 'coding creation uncertain; trusted inspection required')
            require(sandbox.command([self.runtime, 'rm', '--force', self.container_id], seconds=30)[0] == 0,
                    'owned coding cleanup failed; trusted inspection required')
            self.created_container = False
