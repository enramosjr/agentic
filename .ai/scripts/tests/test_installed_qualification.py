"""Qualify a real uncommitted adopter upgrade without framework history."""
import copy
import json
import os
import subprocess
import sys

from test_install import InstallerCase


class InstalledQualificationTests(InstallerCase):
    def test_history_free_uncommitted_upgrade_preserves_adopter_and_qualifies(self):
        name = '.claude/settings.json'
        desired = json.loads((self.template / name).read_text())
        legacy = copy.deepcopy(desired)
        expanded = 'Write|Edit|MultiEdit|NotebookEdit|Delete'
        old = 'Write|Edit|MultiEdit|NotebookEdit'
        changed = 0
        for group in legacy['hooks']['PreToolUse']:
            if group.get('matcher') == expanded:
                group['matcher'] = old
                changed += 1
        self.assertEqual(changed, 1)
        (self.template / name).write_text(json.dumps(legacy))
        added = self.template / '.ai/scripts/assurance.py'
        added_bytes = added.read_bytes()
        added.unlink()
        custom = b'adopter\n'
        self.write('AGENTS.md', custom)
        prompt = {'type': 'prompt', 'prompt': 'Preserve the adopter check'}
        settings = {'permissions': {'allow': ['adopter-command']}, 'hooks': {
            'PreToolUse': [{'matcher': 'AdopterTool', 'hooks': [prompt]}]}}
        self.write(name, json.dumps(settings))
        self.commit()
        self.run_install()
        self.commit()
        application_before = (self.target / 'src/app.py').read_bytes()
        knowledge_before = {str(p.relative_to(self.target)): p.read_bytes()
                            for p in (self.target / 'knowledge').rglob('*') if p.is_file()}
        head_before = self.git('rev-parse', 'HEAD')
        index_before = self.git('ls-files', '--stage', '-z')
        (self.template / name).write_text(json.dumps(desired))
        added.write_bytes(added_bytes)
        self.run_install()
        self.assertEqual(self.git('rev-parse', 'HEAD'), head_before)
        self.assertEqual(self.git('ls-files', '--stage', '-z'), index_before)
        self.assertIn('.ai/scripts/assurance.py', self.git('ls-files', '--others', '--exclude-standard', '-z'))
        self.assertLess(len((self.target / 'AGENTS.md').read_text().encode()), 30_000)
        self.assertTrue((self.target / 'AGENTS.md').read_bytes().startswith(custom))
        self.assertEqual((self.target / 'src/app.py').read_bytes(), application_before)
        self.assertEqual({str(p.relative_to(self.target)): p.read_bytes()
                          for p in (self.target / 'knowledge').rglob('*') if p.is_file()}, knowledge_before)
        merged = json.loads((self.target / name).read_text())
        self.assertEqual(merged['permissions'], settings['permissions'])
        self.assertIn(settings['hooks']['PreToolUse'][0], merged['hooks']['PreToolUse'])
        lifecycle_groups = [g for g in merged['hooks']['PreToolUse']
                            if any('lifecycle.py' in h.get('command', '') for h in g.get('hooks', []))]
        self.assertEqual(sum(g.get('matcher') == expanded for g in lifecycle_groups), 1)
        self.assertFalse(any(g.get('matcher') == old for g in lifecycle_groups))
        env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
        commands = [
            [sys.executable, '.ai/scripts/tests/test_assurance_inputs.py',
             'HarnessWiringProfileTests.test_exact_registration_and_prior_profiles',
             'AgentsBudgetProfileTests.test_exact_registration_and_prior_profiles'],
            [sys.executable, '.ai/scripts/tests/test_lifecycle_conformance.py',
             'AgentsBudget.test_agents_md_stays_below_its_cold_start_budget'],
        ]
        for command in commands:
            result = subprocess.run(command, cwd=self.target, env=env,
                                    capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn('skipped', result.stdout + result.stderr)
        scripts = str(self.target / '.ai/scripts')
        code = ('import sys; from pathlib import Path; '
                f'sys.path.insert(0, {scripts + "/tests"!r}); '
                'import test_assurance_measure as m; '
                'assert m.snapshot()[b".ai/scripts/assurance.py"] == '
                'Path(".ai/scripts/assurance.py").read_bytes()')
        result = subprocess.run([sys.executable, '-c', code], cwd=self.target, env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.run_install('--check')
        before = self.snapshot()
        self.run_install('--check')
        self.assertEqual(self.snapshot(), before)
        self.assertIn('up to date', self.run_install())
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    import unittest
    unittest.main()
