"""Native process lifetime and locking primitives shared by framework tools."""
from __future__ import annotations

from contextlib import contextmanager
import errno
import os
from pathlib import Path
import time
import subprocess
import uuid
import sys
import shutil


def python_hint(*, as_argument: bool = False) -> str:
    """Copyable human guidance only; never transform recorded/executed argv."""
    if os.name == 'nt':
        return ('' if as_argument else '& ') + "'" + sys.executable.replace("'", "''") + "'"
    return 'python3'


def configure_windows_environment() -> None:
    """Use UTF-8 CLI streams and discover Windows tools without global PATH edits."""
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if reconfigure is not None:
            reconfigure(encoding='utf-8')
    if os.name != 'nt':
        return
    if shutil.which('git'):
        return
    bases = [os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)')]
    local = os.environ.get('LOCALAPPDATA')
    if local:
        bases.append(str(Path(local) / 'Programs'))
    for base in bases:
        if not base:
            continue
        executable = Path(base) / 'Git/cmd/git.exe'
        if executable.is_file():
            os.environ['PATH'] = str(executable.parent) + os.pathsep + os.environ.get('PATH', '')
            return


def _windows_handle_state(kernel, handle) -> tuple[str, bool]:
    import ctypes
    from ctypes import wintypes
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    created, exited, system, user = (wintypes.FILETIME() for _ in range(4))
    if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                  ctypes.byref(system), ctypes.byref(user)):
        raise ctypes.WinError(ctypes.get_last_error())
    state = kernel.WaitForSingleObject(handle, 0)
    if state == 0xffffffff:
        raise ctypes.WinError(ctypes.get_last_error())
    birth = str((created.dwHighDateTime << 32) | created.dwLowDateTime)
    return birth, state == 258  # WAIT_TIMEOUT, including a real exit code of 259.


def _windows_state(pid: int) -> tuple[str, bool]:
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x00101000, False, pid)  # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:  # ERROR_INVALID_PARAMETER: the process no longer exists.
            raise ProcessLookupError(pid)
        if error == 5:
            raise PermissionError(pid)
        raise ctypes.WinError(error)
    try:
        return _windows_handle_state(kernel, handle)
    finally:
        kernel.CloseHandle(handle)


def identity(pid: int | None = None) -> dict:
    pid = os.getpid() if pid is None else pid
    if not isinstance(pid, int) or pid <= 0:
        raise ProcessLookupError(pid)
    if os.name == 'nt':
        birth, running = _windows_state(pid)
        if not running:
            raise ProcessLookupError(pid)
    else:
        try:
            fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
            if fields[0] == 'Z':
                raise ProcessLookupError(pid)
            birth = fields[19]
        except FileNotFoundError as error:
            raise ProcessLookupError(pid) from error
    return {'pid': pid, 'birth': birth}


def alive(pid: int, birth: str | None = None) -> bool:
    try:
        current = identity(pid)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Access denied is not proof that a protected process has stopped.
        return True
    return birth is None or current['birth'] == birth


@contextmanager
def file_lock(path: Path, *, blocking: bool = True):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if os.name == 'nt':
            import msvcrt
            if not stream.tell():
                stream.write(b'\0')
                stream.flush()
            while True:
                stream.seek(0)
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as error:
                    if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    if not blocking:
                        raise BlockingIOError(errno.EWOULDBLOCK, 'lock is already held', str(path)) from error
                    time.sleep(0.01)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        try:
            yield stream
        finally:
            if os.name == 'nt':
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def detached_options() -> dict:
    """A supervisor must not share its caller's console/process group."""
    if os.name == 'nt':
        return {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
    return {'start_new_session': True}


def _job_api():
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                wintypes.DWORD, ctypes.c_void_p]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    return kernel


def _resume_primary(pid: int) -> None:
    import ctypes
    from ctypes import wintypes

    class ThreadEntry(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('usage', wintypes.DWORD), ('thread', wintypes.DWORD),
                    ('owner', wintypes.DWORD), ('base', wintypes.LONG), ('delta', wintypes.LONG),
                    ('flags', wintypes.DWORD)]

    kernel = _job_api()
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry)]
    kernel.Thread32Next.argtypes = kernel.Thread32First.argtypes
    kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenThread.restype = wintypes.HANDLE
    kernel.ResumeThread.argtypes = [wintypes.HANDLE]
    kernel.ResumeThread.restype = wintypes.DWORD
    snapshot = kernel.CreateToolhelp32Snapshot(4, 0)  # TH32CS_SNAPTHREAD
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = ThreadEntry()
        entry.size = ctypes.sizeof(entry)
        found = kernel.Thread32First(snapshot, ctypes.byref(entry))
        while found:
            if entry.owner == pid:
                thread = kernel.OpenThread(2, False, entry.thread)  # THREAD_SUSPEND_RESUME
                if not thread:
                    raise ctypes.WinError(ctypes.get_last_error())
                try:
                    if kernel.ResumeThread(thread) == 0xffffffff:
                        raise ctypes.WinError(ctypes.get_last_error())
                    return
                finally:
                    kernel.CloseHandle(thread)
            found = kernel.Thread32Next(snapshot, ctypes.byref(entry))
        raise ProcessLookupError(pid)
    finally:
        kernel.CloseHandle(snapshot)


class ProcessTree:
    """Own a child tree before its first instruction and reap it on owner death."""
    def __init__(self):
        self.process = None
        self.job = None
        self.descriptor = None

    def start(self, command, *, before_launch=None, before_resume=None, **kwargs):
        if before_launch is not None and before_resume is not None:
            raise ValueError('provide only one process-publication callback')
        before_resume = before_launch if before_launch is not None else before_resume
        if self.process is not None:
            raise ValueError('process tree already started')
        if os.name != 'nt':
            if before_resume is not None:
                raise ValueError('before_resume requires the Windows suspended-process adapter')
            kwargs['start_new_session'] = True
            self.process = subprocess.Popen(command, **kwargs)
            self.descriptor = {'group': self.process.pid}
            return self.process
        import ctypes
        from ctypes import wintypes

        class BasicLimits(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                        ('flags', wintypes.DWORD), ('minimum', ctypes.c_size_t),
                        ('maximum', ctypes.c_size_t), ('processes', wintypes.DWORD),
                        ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD),
                        ('scheduling', wintypes.DWORD)]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in ('read_ops', 'write_ops', 'other_ops',
                                                           'read_bytes', 'write_bytes', 'other_bytes')]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [('basic', BasicLimits), ('io', IoCounters),
                        ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                        ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]

        kernel = _job_api()
        name = 'Local\\AGENTIC-' + uuid.uuid4().hex
        self.job = kernel.CreateJobObjectW(None, name)
        if not self.job:
            raise ctypes.WinError(ctypes.get_last_error())
        self.descriptor = {'job': name}
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        try:
            if not kernel.SetInformationJobObject(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise ctypes.WinError(ctypes.get_last_error())
            kwargs.pop('start_new_session', None)
            # CREATE_NO_WINDOW otherwise discards the console's implicit handles.
            # Explicit fds make Popen duplicate the real redirected/native streams.
            for stream, descriptor in (('stdin', 0), ('stdout', 1), ('stderr', 2)):
                if kwargs.get(stream) is None:
                    kwargs[stream] = descriptor
            kwargs['creationflags'] = (kwargs.get('creationflags', 0) | 0x00000004 |  # CREATE_SUSPENDED
                                       subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW)
            self.process = subprocess.Popen(command, **kwargs)
            if not kernel.AssignProcessToJobObject(self.job, int(self.process._handle)):
                raise ctypes.WinError(ctypes.get_last_error())
            if before_resume is not None:
                before_resume(self.descriptor)
            _resume_primary(self.process.pid)
            return self.process
        except BaseException:
            if self.process is not None:
                self.process.kill()
                self.process.wait()
            self.close()
            raise

    def stop(self):
        if os.name == 'nt':
            if self.job:
                import ctypes
                if not _job_api().TerminateJobObject(self.job, 1):
                    raise ctypes.WinError(ctypes.get_last_error())
        elif self.process is not None:
            import signal
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def close(self):
        self.stop()
        if os.name == 'nt' and self.job:
            _job_api().CloseHandle(self.job)
            self.job = None


def tree_stopped(descriptor: dict) -> bool:
    if 'group' in descriptor and os.name != 'nt':
        try:
            os.killpg(descriptor['group'], 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        return False
    name = descriptor.get('job', '')
    if os.name != 'nt' or not name.startswith('Local\\AGENTIC-') or len(name) != 46:
        raise ValueError('invalid owned process-tree descriptor')
    import ctypes
    from ctypes import wintypes

    class Accounting(ctypes.Structure):
        _fields_ = [(key, ctypes.c_int64) for key in ('user', 'kernel', 'period_user', 'period_kernel')]
        _fields_ += [(key, wintypes.DWORD) for key in ('faults', 'total', 'active', 'terminated')]

    kernel = _job_api()
    handle = kernel.OpenJobObjectW(4, False, name)  # JOB_OBJECT_QUERY
    if not handle:
        if ctypes.get_last_error() == 2:
            return True
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        value = Accounting()
        if not kernel.QueryInformationJobObject(handle, 1, ctypes.byref(value), ctypes.sizeof(value), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return value.active == 0
    finally:
        kernel.CloseHandle(handle)


def terminate_tree(pid: int, birth: str | None = None) -> None:
    """Explicit recovery for test-owned/detached groups; avoid reused PIDs."""
    if birth is None:
        try:
            birth = identity(pid)['birth']
        except ProcessLookupError:
            return
    if os.name == 'nt':
        # Detached supervisors own kill-on-close Jobs. Terminate their verified
        # process handle; closing its handles reaps the command descendants.
        import ctypes
        from ctypes import wintypes
        kernel = _job_api()
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        # The same held handle must authorize and execute termination. A separate
        # PID liveness probe intentionally treats access denied conservatively;
        # that uncertainty is never permission to terminate a process.
        handle = kernel.OpenProcess(0x00101001, False, pid)  # SYNCHRONIZE | QUERY_LIMITED_INFORMATION | TERMINATE
        if not handle:
            if ctypes.get_last_error() == 87:  # ERROR_INVALID_PARAMETER: absent PID.
                return
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            current_birth, running = _windows_handle_state(kernel, handle)
            if not running or current_birth != birth:
                return
            if not kernel.TerminateProcess(handle, 1):
                raise ctypes.WinError(ctypes.get_last_error())
            if kernel.WaitForSingleObject(handle, 10000) != 0:
                raise OSError('owned supervisor did not terminate')
        finally:
            kernel.CloseHandle(handle)
    else:
        if not alive(pid, birth):
            return
        import signal
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def process_info(pid: int) -> dict:
    """Return actual OS ancestry and argv; environment claims are not evidence."""
    before = identity(pid)
    if os.name != 'nt':
        process = Path(f'/proc/{pid}')
        fields = (process / 'stat').read_text().rsplit(')', 1)[1].split()
        argv = [os.fsdecode(word) for word in (process / 'cmdline').read_bytes().split(b'\0') if word]
        value = {'parent': int(fields[1]), 'argv': argv}
    else:
        import ctypes
        from ctypes import wintypes

        class BasicInfo(ctypes.Structure):
            _fields_ = [('reserved', ctypes.c_void_p), ('peb', ctypes.c_void_p),
                        ('reserved2', ctypes.c_void_p * 2), ('pid', ctypes.c_size_t),
                        ('parent', ctypes.c_size_t)]

        class UnicodeString(ctypes.Structure):
            _fields_ = [('length', wintypes.USHORT), ('maximum', wintypes.USHORT),
                        ('buffer', ctypes.c_void_p)]

        kernel = _job_api()
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        native = ctypes.WinDLL('ntdll')
        query = native.NtQueryInformationProcess
        query.argtypes = [wintypes.HANDLE, wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG,
                          ctypes.POINTER(wintypes.ULONG)]
        query.restype = wintypes.LONG
        try:
            basic = BasicInfo()
            if query(handle, 0, ctypes.byref(basic), ctypes.sizeof(basic), None) < 0:
                raise PermissionError('native process ancestry is unavailable')
            needed = wintypes.ULONG()
            query(handle, 60, None, 0, ctypes.byref(needed))  # ProcessCommandLineInformation
            if not ctypes.sizeof(UnicodeString) <= needed.value <= 1024 * 1024:
                raise PermissionError('native process command line is unavailable')
            storage = ctypes.create_string_buffer(needed.value)
            if query(handle, 60, storage, len(storage), ctypes.byref(needed)) < 0:
                raise PermissionError('native process command line is unavailable')
            text = UnicodeString.from_buffer(storage)
            command_line = ctypes.wstring_at(text.buffer, text.length // 2)
        finally:
            kernel.CloseHandle(handle)
        shell32 = ctypes.WinDLL('shell32', use_last_error=True)
        shell32.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
        shell32.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
        count = ctypes.c_int()
        arguments = shell32.CommandLineToArgvW(command_line, ctypes.byref(count))
        if not arguments:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            value = {'parent': basic.parent, 'argv': [arguments[n] for n in range(count.value)]}
        finally:
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.LocalFree.argtypes = [ctypes.c_void_p]
            kernel.LocalFree(arguments)
    if identity(pid) != before:
        raise ProcessLookupError(pid)
    return {**before, **value}
