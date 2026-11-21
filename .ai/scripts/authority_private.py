"""Shared stdlib owner-only setup storage, outside the modifying checkout.

This protects bytes from other OS users. It does not attest that a same-user
coding process is absent; trusted bootstrap context remains a separate gate.
Windows uses protected native DACLs, not chmod as an ACL substitute.
"""
import contextlib
import json
import os
from pathlib import Path
import secrets
import stat

from trusted_ci_policy import Refusal, loads, object_fields, positive, require

MAX_STATE = 128 * 1024
CHECKOUT = Path(__file__).resolve().parents[2]


def _plain(path, directory):
    value = path.lstat()
    require(not stat.S_ISLNK(value.st_mode) and not getattr(value, 'st_file_attributes', 0) & 0x400 and
            (stat.S_ISDIR(value.st_mode) if directory else stat.S_ISREG(value.st_mode) and value.st_nlink == 1),
            'plain owned setup storage required')
    return value


def _windows(path, directory, harden=False, parent=False):
    import ctypes as c
    from ctypes import wintypes as w
    api, kernel = c.WinDLL('advapi32', use_last_error=True), c.WinDLL('kernel32', use_last_error=True)
    pointer = c.c_void_p
    out = c.POINTER(pointer)
    api.OpenProcessToken.argtypes = (w.HANDLE, w.DWORD, c.POINTER(w.HANDLE))
    api.OpenProcessToken.restype = w.BOOL
    api.GetTokenInformation.argtypes = (w.HANDLE, c.c_int, pointer, w.DWORD, c.POINTER(w.DWORD))
    api.GetTokenInformation.restype = w.BOOL
    api.ConvertSidToStringSidW.argtypes = (pointer, out)
    api.ConvertSidToStringSidW.restype = w.BOOL
    api.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = (w.LPCWSTR, w.DWORD, out, c.POINTER(w.DWORD))
    api.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = w.BOOL
    api.GetNamedSecurityInfoW.argtypes = (w.LPCWSTR, c.c_int, w.DWORD, out, out, out, out, out)
    api.GetNamedSecurityInfoW.restype = w.DWORD
    api.SetNamedSecurityInfoW.argtypes = (w.LPWSTR, c.c_int, w.DWORD, pointer, pointer, pointer, pointer)
    api.SetNamedSecurityInfoW.restype = w.DWORD
    api.GetSecurityDescriptorDacl.argtypes = (pointer, c.POINTER(w.BOOL), out, c.POINTER(w.BOOL))
    api.GetSecurityDescriptorDacl.restype = w.BOOL
    api.GetSecurityDescriptorControl.argtypes = (pointer, c.POINTER(w.WORD), c.POINTER(w.DWORD))
    api.GetSecurityDescriptorControl.restype = w.BOOL
    api.GetAclInformation.argtypes = (pointer, pointer, w.DWORD, c.c_int)
    api.GetAclInformation.restype = w.BOOL
    api.GetAce.argtypes = (pointer, w.DWORD, out)
    api.GetAce.restype = w.BOOL
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = (w.HANDLE,)
    kernel.LocalFree.argtypes = (pointer,)
    kernel.LocalFree.restype = pointer

    def sid_text(value):
        text = pointer()
        require(api.ConvertSidToStringSidW(value, c.byref(text)), 'setup SID readback failed')
        try: return c.wstring_at(text.value)
        finally: kernel.LocalFree(text)

    token, size = w.HANDLE(), w.DWORD()
    require(api.OpenProcessToken(kernel.GetCurrentProcess(), 8, c.byref(token)), 'setup owner token unavailable')
    try:
        api.GetTokenInformation(token, 1, None, 0, c.byref(size))
        require(0 < size.value <= 65536, 'bounded setup owner required')
        buffer = c.create_string_buffer(size.value)
        require(api.GetTokenInformation(token, 1, buffer, size, c.byref(size)), 'setup owner unavailable')
        current_sid = sid_text(c.cast(buffer, c.POINTER(pointer))[0])
    finally: kernel.CloseHandle(token)

    if harden:
        descriptor, acl = pointer(), pointer()
        present, defaulted = w.BOOL(), w.BOOL()
        inheritance = 'OICI' if directory else ''
        require(api.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            'D:P(A;' + inheritance + ';FA;;;' + current_sid + ')', 1, c.byref(descriptor), None),
            'private setup DACL creation failed')
        try:
            require(api.GetSecurityDescriptorDacl(descriptor, c.byref(present), c.byref(acl), c.byref(defaulted)) and
                    present.value and acl.value, 'private setup DACL unavailable')
            require(api.SetNamedSecurityInfoW(str(path), 1, 0x80000004, None, None, acl, None) == 0,
                    'private setup DACL installation failed')
        finally: kernel.LocalFree(descriptor)

    owner, acl, descriptor = pointer(), pointer(), pointer()
    require(api.GetNamedSecurityInfoW(str(path), 1, 5, c.byref(owner), None, c.byref(acl), None,
                                     c.byref(descriptor)) == 0, 'setup DACL readback failed')
    try:
        control, revision = w.WORD(), w.DWORD()
        owner_sid = sid_text(owner)
        require(acl.value and api.GetSecurityDescriptorControl(descriptor, c.byref(control), c.byref(revision)),
                'setup DACL control unavailable')
        class AclSize(c.Structure):
            _fields_ = [('count', w.DWORD), ('used', w.DWORD), ('free', w.DWORD)]
        size_info = AclSize()
        require(api.GetAclInformation(acl, c.byref(size_info), c.sizeof(size_info), 2) and size_info.count <= 1024,
                'bounded setup DACL required')
        if parent:
            trusted = {current_sid, 'S-1-5-18', 'S-1-5-32-544',
                       'S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464'}
            require(owner_sid in trusted, 'setup ancestor owner is outside the trusted OS boundary')
            for index in range(size_info.count):
                ace = pointer()
                require(api.GetAce(acl, index, c.byref(ace)), 'setup ancestor ACE unavailable')
                header = (c.c_ubyte * 4).from_address(ace.value)
                if header[1] & 8: continue  # Inherit-only: does not authorize this directory.
                require(header[0] in (0, 1), 'unsupported setup ancestor access policy')
                if header[0] == 1: continue  # A deny does not grant substitution access.
                subject = sid_text(pointer(ace.value + 8))
                if subject in trusted or subject == 'S-1-3-4': continue  # Owner Rights, with trusted owner above.
                mask = c.c_uint32.from_address(ace.value + 4).value
                dangerous = 0x10000000 | 0x40000000 | 0x40000 | 0x80000 | 0x40 | 0x100
                if path.parent != path: dangerous |= 0x10000  # Deleting this ancestor also substitutes the path.
                require(not mask & dangerous, 'another OS user can replace setup storage through an ancestor')
            return
        require(owner_sid == current_sid and control.value & 0x1000 and size_info.count == 1,
                'protected single-owner setup DACL required')
        ace = pointer()
        require(api.GetAce(acl, 0, c.byref(ace)), 'setup ACE unavailable')
        header = (c.c_ubyte * 4).from_address(ace.value)
        mask = c.c_uint32.from_address(ace.value + 4).value
        require(header[0] == 0 and header[1] == (3 if directory else 0) and mask == 0x1F01FF and
                sid_text(pointer(ace.value + 8)) == current_sid, 'setup access extends beyond its owner')
    finally: kernel.LocalFree(descriptor)


def verify(path, directory):
    path = Path(path)
    before = _plain(path, directory)
    if os.name == 'nt': _windows(path, directory)
    else:
        require(before.st_uid == os.geteuid() and before.st_mode & 0o777 == (0o700 if directory else 0o600),
                'owner-only setup permissions required; exposed storage cannot be repaired silently')
    after = _plain(path, directory)
    require((before.st_dev, before.st_ino) == (after.st_dev, after.st_ino), 'setup storage identity changed')


def _harden_new(path, directory):
    _plain(path, directory)
    if os.name == 'nt': _windows(path, directory, harden=True)
    else: os.chmod(path, 0o700 if directory else 0o600)
    verify(path, directory)


def replace(source, target):
    """Same-directory replacement with platform persistence completion."""
    require(source.parent == target.parent, 'same-directory setup replacement required')
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.MoveFileExW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD)
        kernel.MoveFileExW.restype = wintypes.BOOL
        if not kernel.MoveFileExW(str(source), str(target), 0x9):
            raise OSError('private setup replacement unavailable')
    else:
        os.replace(source, target)
        fd = os.open(source.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0))
        try: os.fsync(fd)
        finally: os.close(fd)


def _trusted_parents(root):
    """Exclude rename/reparse substitution by non-administrative OS users."""
    for ancestor in reversed((root, *root.parents)):
        if not (ancestor.exists() or ancestor.is_symlink()): continue
        value = _plain(ancestor, directory=True)
        if os.name == 'nt': _windows(ancestor, directory=True, parent=True)
        else:
            require(value.st_uid in (0, os.geteuid()) and
                    (not value.st_mode & 0o022 or value.st_mode & stat.S_ISVTX),
                    'setup ancestors must exclude another OS user replacing the path')


class Store:
    def __init__(self, root):
        root = Path(root)
        require(root.is_absolute() and '..' not in root.parts and not root.is_relative_to(CHECKOUT),
                'private setup must be outside the modifying checkout')
        _trusted_parents(root)
        try: root.mkdir(mode=0o700)
        except FileExistsError: verify(root, directory=True)
        else: _harden_new(root, directory=True)
        self.root, self.path = root, root / 'model-setup.json'

    def _open(self, path, flags):
        _trusted_parents(self.root)
        verify(self.root, directory=True)
        if path.exists() or path.is_symlink(): verify(path, directory=False)
        fd = os.open(path, flags | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        return fd

    def read(self):
        try: fd = self._open(self.path, os.O_RDONLY)
        except FileNotFoundError: return None
        with os.fdopen(fd, 'rb') as stream:
            verify(self.path, directory=False)
            opened, named = os.fstat(stream.fileno()), self.path.lstat()
            require((opened.st_dev, opened.st_ino) == (named.st_dev, named.st_ino), 'setup file changed during open')
            raw = stream.read(MAX_STATE + 1)
        require(0 < len(raw) <= MAX_STATE, 'bounded private setup record required')
        value = loads(raw)
        object_fields(value, ('schema_version', 'generation', 'value'), 'private setup record')
        require(type(value['schema_version']) is int and value['schema_version'] == 1 and
                positive(value['generation']) and isinstance(value['value'], dict), 'private setup generation differs')
        return value

    @contextlib.contextmanager
    def _lock(self):
        path = self.root / 'model-setup.lock'
        try:
            fd = self._open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL)
            try:
                _harden_new(path, directory=False)
                os.write(fd, b'0')
                os.fsync(fd)
            except Exception:
                os.close(fd)
                raise
        except FileExistsError: fd = self._open(path, os.O_RDWR)
        try:
            if os.name == 'nt':
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        except OSError:
            raise Refusal('private setup operation busy or unavailable') from None
        finally: os.close(fd)  # Kernel locking survives no process crash.

    def write(self, expected, value):
        require(isinstance(value, dict), 'private setup object required')
        document = dict(schema_version=1, generation=1 if expected is None else expected['generation'] + 1, value=value)
        raw = (json.dumps(document, sort_keys=True, allow_nan=False) + '\n').encode()
        require(len(raw) <= MAX_STATE, 'private setup state exceeds limit')
        with self._lock():
            require(self.read() == expected, 'private setup changed; do not repeat an exchange')
            temporary = self.root / (secrets.token_hex(16) + '.tmp')
            fd = self._open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            owned = os.fstat(fd)
            try:
                _harden_new(temporary, directory=False)
                with os.fdopen(fd, 'wb') as stream:
                    fd = None
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                try: replace(temporary, self.path)
                except OSError:
                    # Visibility after rename cannot prove its persistence flush.
                    # Preserve whatever state exists, but never proceed to a grant.
                    raise Refusal('private setup persistence uncertain; stop this exchange') from None
                observed = self.read()
                require(observed == document, 'private setup readback differs; do not repeat an exchange')
                return observed  # Independent committed snapshot, never caller-owned mutable data.
            finally:
                if fd is not None: os.close(fd)
                if temporary.exists():
                    current = _plain(temporary, directory=False)
                    require((current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino), 'setup temporary identity changed')
                    temporary.unlink()
