"""Actual owner-only fixture storage; not a trusted-context attestation."""
import backend_test_support
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from trusted_ci_policy import Refusal
import private_setup


class PrivateSetupContracts(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', 'POSIX parent substitution permissions')
    def test_shared_nonsticky_parent_is_rejected_before_child_creation(self):
        with self.temporary() as parent:
            shared = Path(parent) / 'shared'
            shared.mkdir()
            shared.chmod(0o777)
            try:
                with self.assertRaises(Refusal): private_setup.Store(shared / 'setup')
                self.assertFalse((shared / 'setup').exists())
            finally: shared.chmod(0o700)

    @unittest.skipUnless(os.name == 'nt', 'actual Windows parent DELETE_CHILD grant')
    def test_parent_delete_child_grant_to_everyone_is_rejected(self):
        import ctypes as c
        from ctypes import wintypes as w
        with self.temporary() as parent:
            api, kernel = c.WinDLL('advapi32', use_last_error=True), c.WinDLL('kernel32', use_last_error=True)
            pointer = c.c_void_p
            descriptor, acl = pointer(), pointer()
            present, defaulted = w.BOOL(), w.BOOL()
            api.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = (w.LPCWSTR, w.DWORD, c.POINTER(pointer), pointer)
            api.GetSecurityDescriptorDacl.argtypes = (pointer, c.POINTER(w.BOOL), c.POINTER(pointer), c.POINTER(w.BOOL))
            api.SetNamedSecurityInfoW.argtypes = (w.LPWSTR, c.c_int, w.DWORD, pointer, pointer, pointer, pointer)
            api.SetNamedSecurityInfoW.restype = w.DWORD
            kernel.LocalFree.argtypes = (pointer,)
            kernel.LocalFree.restype = pointer
            kernel.GetCurrentProcess.restype = w.HANDLE
            kernel.CloseHandle.argtypes = (w.HANDLE,)
            api.OpenProcessToken.argtypes = (w.HANDLE, w.DWORD, c.POINTER(w.HANDLE))
            api.GetTokenInformation.argtypes = (w.HANDLE, c.c_int, pointer, w.DWORD, c.POINTER(w.DWORD))
            api.ConvertSidToStringSidW.argtypes = (pointer, c.POINTER(pointer))
            token, size, text = w.HANDLE(), w.DWORD(), pointer()
            self.assertTrue(api.OpenProcessToken(kernel.GetCurrentProcess(), 8, c.byref(token)))
            try:
                api.GetTokenInformation(token, 1, None, 0, c.byref(size))
                buffer = c.create_string_buffer(size.value)
                self.assertTrue(api.GetTokenInformation(token, 1, buffer, size, c.byref(size)))
                self.assertTrue(api.ConvertSidToStringSidW(c.cast(buffer, c.POINTER(pointer))[0], c.byref(text)))
                sid = c.wstring_at(text.value)
            finally:
                kernel.LocalFree(text)
                kernel.CloseHandle(token)
            self.assertTrue(api.ConvertStringSecurityDescriptorToSecurityDescriptorW('D:P(A;;FA;;;' + sid + ')(A;;0x40;;;WD)',
                            1, c.byref(descriptor), None))
            try:
                self.assertTrue(api.GetSecurityDescriptorDacl(descriptor, c.byref(present), c.byref(acl), c.byref(defaulted)))
                self.assertEqual(api.SetNamedSecurityInfoW(parent, 1, 0x80000004, None, None, acl, None), 0)
                with self.assertRaises(Refusal): private_setup.Store(Path(parent) / 'setup')
                self.assertFalse((Path(parent) / 'setup').exists())
            finally:
                kernel.LocalFree(descriptor)
                private_setup._harden_new(Path(parent), directory=True)

    def temporary(self):
        # Lifecycle scratch lives in the checkout. Secret setup storage must not.
        # Ordinary Windows Temp may grant sandbox principals Modify on ancestors.
        # Use a fresh synthetic fixture under the user's home; never repair an
        # existing ancestor ACL or treat this fixture as a trusted bootstrap.
        parent = str(Path.home()) if os.name == 'nt' else '/tmp'
        return tempfile.TemporaryDirectory(prefix='agentic-private-fixture-', dir=parent)

    def test_actual_private_storage_atomic_update_and_generation_conflict(self):
        with self.temporary() as parent:
            store = private_setup.Store(Path(parent) / 'setup')
            self.assertIsNone(store.read())
            first = store.write(None, {'host_id': 'SYNTHETIC-HOST', 'secret': 'SYNTHETIC-PRIVATE-VALUE'})
            private_setup.verify(store.root, directory=True)
            private_setup.verify(store.path, directory=False)
            self.assertEqual(first['generation'], 1)
            second = store.write(first, {'host_id': 'SYNTHETIC-HOST', 'secret': 'SYNTHETIC-REPLACEMENT'})
            self.assertEqual(second['generation'], 2)
            with self.assertRaises(Refusal): store.write(first, {'stale': True})
            self.assertEqual(store.read(), second)

    def test_committed_snapshot_does_not_alias_mutable_caller_input(self):
        with self.temporary() as parent:
            store = private_setup.Store(Path(parent) / 'setup')
            value = {'attempt': {'phase': 'exchange-started'}}
            snapshot = store.write(None, value)
            value['attempt']['phase'] = 'sealed'
            self.assertEqual(snapshot['value']['attempt']['phase'], 'exchange-started')
            updated = store.write(snapshot, value)
            self.assertEqual(updated['value']['attempt']['phase'], 'sealed')

    def test_unknown_replace_completion_stops_even_when_new_bytes_are_visible(self):
        with self.temporary() as parent:
            store = private_setup.Store(Path(parent) / 'setup')
            real = private_setup.replace
            calls = []
            def lost(*args):
                calls.append(args)
                real(*args)
                raise OSError('synthetic lost replace acknowledgement')
            with patch.object(private_setup, 'replace', side_effect=lost):
                with self.assertRaises(Refusal): store.write(None, {'secret': 'SYNTHETIC-PRIVATE-VALUE'})
            self.assertEqual(store.read()['value'], {'secret': 'SYNTHETIC-PRIVATE-VALUE'})
            self.assertEqual(len(calls), 1)

    @unittest.skipUnless(os.name == 'posix', 'actual POSIX directory flush failure')
    def test_directory_flush_failure_is_not_persistence_proof(self):
        import stat
        with self.temporary() as parent:
            store = private_setup.Store(Path(parent) / 'setup')
            real = os.fsync
            def fail_directory(fd):
                if stat.S_ISDIR(os.fstat(fd).st_mode): raise OSError('synthetic directory persistence failure')
                return real(fd)
            with patch.object(private_setup.os, 'fsync', side_effect=fail_directory), self.assertRaises(Refusal):
                store.write(None, {'phase': 'exchange-started', 'secret': 'SYNTHETIC-PRIVATE-VALUE'})
            self.assertEqual(store.read()['value']['phase'], 'exchange-started')

    def test_checkout_and_linked_roots_are_refused_without_repair(self):
        with self.assertRaises(Refusal): private_setup.Store(backend_test_support.ROOT / '.git' / 'forbidden-model-setup')
        with self.temporary() as parent:
            target = Path(parent) / 'target'
            target.mkdir()
            link = Path(parent) / 'link'
            try: link.symlink_to(target, target_is_directory=True)
            except OSError:
                if os.name == 'nt': return  # Native ACL test still runs above.
                raise
            with self.assertRaises(Refusal): private_setup.Store(link)

    @unittest.skipUnless(os.name == 'posix', 'POSIX mode damage; Windows uses native DACL readback')
    def test_preexisting_exposed_storage_is_refused_without_chmod_repair(self):
        with self.temporary() as parent:
            root = Path(parent) / 'setup'
            root.mkdir(mode=0o755)
            with self.assertRaises(Refusal): private_setup.Store(root)
            self.assertEqual(root.stat().st_mode & 0o777, 0o755)


if __name__ == '__main__': unittest.main()
