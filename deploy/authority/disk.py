"""Trusted Linux host-only, hard-sized per-job disk provisioning and cleanup."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai' / 'scripts'))
from trusted_ci_policy import Refusal, positive, require
from trusted_ci_sandbox import command


def checked(argv):
    code, output = command(argv, seconds=60)
    require(code == 0, 'trusted host operation failed: ' + argv[0])
    return output.strip()


class WorkDisk:
    def __init__(self, name, megabytes, runtime='docker', runner=checked, formatter_image=None):
        require(isinstance(name, str) and re.fullmatch('agentic-[a-z0-9-]{1,48}', name),
                'job-specific agentic volume name required')
        require(positive(megabytes) and 64 <= megabytes <= 1024, 'disk size must be 64..1024 MiB')
        require(runtime in ('docker', 'podman'), 'supported host runtime required')
        require(formatter_image is None or isinstance(formatter_image, str) and
                re.fullmatch(r'[A-Za-z0-9._/:-]+@sha256:[0-9a-f]{64}', formatter_image),
                'digest-pinned formatter image required')
        self.formatter_image = formatter_image
        self.name, self.megabytes, self.runtime = name, megabytes, runtime
        self.run = runner
        self.directory = None
        self.loop = None
        self.owned_volume = False
        self.mounted = False
        self.lock = None
        self.lock_descriptor = None

    def __enter__(self):
        require(sys.platform == 'linux' and os.geteuid() == 0, 'trusted Linux root host setup required')
        require(self.directory is None, 'disk lease cannot be reused')
        self.lock = Path('/run/lock') / ('agentic-disk-' + self.name)
        try:
            self.lock_descriptor = os.open(str(self.lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                                           getattr(os, 'O_NOFOLLOW', 0), 0o600)
        except FileExistsError as error:
            raise Refusal('another trusted host operation owns this disk name') from error
        try:
            existing = self.run([self.runtime, 'volume', 'ls', '--format', '{{.Name}}',
                                 '--filter', 'name=^' + self.name + '$'])
            require(not existing.strip(), 'preexisting work volume refused')
            self.directory = Path(tempfile.mkdtemp(prefix='agentic-host-disk-'))
            image = self.directory / 'work.img'
            descriptor = os.open(str(image), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.truncate(self.megabytes * 1024 * 1024)
            if shutil.which('mkfs.ext4'):
                self.run(['mkfs.ext4', '-q', '-F', '-m', '0', str(image)])
            else:
                require(self.formatter_image, 'host mkfs.ext4 or approved formatter image required')
                self.run([self.runtime, 'run', '--rm', '--pull=never', '--read-only',
                          '--network=none', '--user=0:0', '--cap-drop=ALL',
                          '--security-opt=no-new-privileges', '--memory=256m', '--pids-limit=32',
                          '--volume', str(image) + ':/work.img:Z', '--entrypoint=/usr/sbin/mkfs.ext4',
                          self.formatter_image, '-q', '-F', '-m', '0', '/work.img'])
            loop = self.run(['losetup', '--find', '--show', '--nooverlap', str(image)])
            require(re.fullmatch('/dev/loop[0-9]+', loop), 'unexpected loop-device allocation')
            self.loop = loop
            mount = self.directory / 'mount'
            mount.mkdir()
            self.run(['mount', '-o', 'nodev,nosuid,noexec', self.loop, str(mount)])
            self.mounted = True
            os.chown(str(mount), 65534, 65534)
            os.chmod(str(mount), 0o700)
            self.run(['umount', str(mount)])
            self.mounted = False
            result = self.run([self.runtime, 'volume', 'create', '--driver=local',
                               '--opt=type=ext4', '--opt=device=' + self.loop,
                               '--opt=o=nodev,nosuid', '--label=agentic.host-owned=true', self.name])
            self.owned_volume = True
            require(result.strip() == self.name, 'unexpected volume provisioning response')
            return self
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.owned_volume:
            self.run([self.runtime, 'volume', 'rm', self.name])
            self.owned_volume = False
        if self.mounted:
            self.run(['umount', str(self.directory / 'mount')])
            self.mounted = False
        if self.loop:
            # Do not detach a device that no longer maps to our own image.
            require(self.directory is not None, 'owned disk directory unavailable')
            observed = self.run(['losetup', '--noheadings', '--output', 'BACK-FILE', self.loop])
            require(Path(observed).resolve() == (self.directory / 'work.img').resolve(),
                    'loop ownership changed; cleanup refused')
            self.run(['losetup', '--detach', self.loop])
            self.loop = None
        if self.directory:
            image = self.directory / 'work.img'
            if image.exists():
                image.unlink()
            mount = self.directory / 'mount'
            if mount.exists():
                mount.rmdir()
            self.directory.rmdir()
            self.directory = None
        if self.lock_descriptor is not None:
            os.close(self.lock_descriptor)
            self.lock_descriptor = None
            self.lock.unlink()
            self.lock = None

    def __exit__(self, *args):
        self.close()
