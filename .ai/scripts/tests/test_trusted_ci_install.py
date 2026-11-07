"""R10: actual fresh install/upgrade, with adopter files retained."""
import json
from test_install import InstallerCase


class TrustedInstallTests(InstallerCase):
    def test_integration_is_exported_without_claiming_remote_enforcement(self):
        self.write('.github/workflows/ours.yml', 'name: keep ours\n')
        self.write('.agentic/trusted-ci.json', '{"adopter":"owned"}\n')
        out = self.run_install('--no-knowledge')
        self.assertIn('external authority provisioning required', out)
        for name in ['.ai/scripts/trusted_ci.py', '.ai/trusted-ci/authority.yml', '.ai/docs/trusted-ci.md']:
            self.assertTrue((self.target / name).is_file(), name)
        self.assertFalse((self.target / '.github/workflows/authority.yml').exists())
        self.assertEqual((self.target / '.github/workflows/ours.yml').read_text(), 'name: keep ours\n')
        self.assertEqual((self.target / '.agentic/trusted-ci.json').read_text(), '{"adopter":"owned"}\n')
        self.commit()
        self.run_install('--no-knowledge')
        self.assertEqual((self.target / '.agentic/trusted-ci.json').read_text(), '{"adopter":"owned"}\n')
        manifest = self.manifest()
        self.assertNotIn('.agentic/trusted-ci.json', manifest['files'])
        self.assertNotIn('.github/workflows/ours.yml', manifest['files'])
