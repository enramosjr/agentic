"""Actual synthetic App JWT signatures without secret files or child processes."""
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai/scripts'))
import bootstrap
from trusted_ci_policy import Refusal


class AppSigningContracts(unittest.TestCase):
    def test_actual_rsa_signature_never_writes_pem_or_starts_openssl_child(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        for format in (serialization.PrivateFormat.PKCS8, serialization.PrivateFormat.TraditionalOpenSSL):
            pem = key.private_bytes(serialization.Encoding.PEM, format, serialization.NoEncryption()).decode()
            before = int(time.time())
            with patch.object(tempfile, 'TemporaryDirectory', side_effect=AssertionError('no PEM files')), \
                 patch.object(bootstrap, 'run', side_effect=AssertionError('no signer child')):
                api = bootstrap.app_api(41, pem)
            value = jwt.decode(api.token, key.public_key(), algorithms=['RS256'], issuer='41', options={'require': ['iss', 'iat', 'exp']})
            self.assertTrue(before - 60 <= value['iat'] <= int(time.time()) - 60)
            self.assertEqual(value['exp'] - value['iat'], 600)

    def test_wrong_key_type_weak_rsa_and_malformed_secret_refuse_without_echo(self):
        for key in (ec.generate_private_key(ec.SECP256R1()), rsa.generate_private_key(public_exponent=65537, key_size=1024)):
            pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                    serialization.NoEncryption()).decode()
            with self.assertRaises(Refusal) as error: bootstrap.app_api(41, pem)
            self.assertNotIn(pem, str(error.exception))
        with self.assertRaises(Refusal): bootstrap.app_api(41, 'SYNTHETIC-NOT-A-KEY')


if __name__ == '__main__': unittest.main()
