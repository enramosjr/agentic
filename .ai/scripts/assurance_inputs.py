#!/usr/bin/env python3
"""Export declared inputs for reviewed Python checks; never execute the check.

Standard library only; Python 3.9+. Profiles require input-completeness review.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
import ledger  # noqa: E402

PROFILES = [{
    'id': 'python-runner-test',
    'cwd': '.',
    'argv': ['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests', '-p', 'test_run_tests.py'],
    'inputs': ['.ai/scripts/tests/test_run_tests.py', '.ai/scripts/tests/disk_tmp.py',
               '.ai/scripts/scratch.py', '.ai/scripts/run_tests.py'],
    'rationale': {
        '.ai/scripts/tests/test_run_tests.py': 'Selected test module, including its generated fixture source.',
        '.ai/scripts/tests/disk_tmp.py': 'Imported fixture temporary-directory helper.',
        '.ai/scripts/scratch.py': 'Transitive helper used to validate disk-backed temporary storage.',
        '.ai/scripts/run_tests.py': 'Subprocess script exercised by the selected test.',
    },
}, {
    'id': 'python-architecture-compatibility',
    'cwd': '.',
    'argv': ['python3', '.ai/scripts/tests/test_assurance_architecture.py', 'CompatibilityTests'],
    'inputs': ['.ai/scripts/**', '!.ai/scripts/tests/**',
               '.ai/scripts/tests/test_assurance_architecture.py',
               '.ai/scripts/tests/test_assurance.py', '.ai/scripts/tests/test_assurance_gate.py',
               '.ai/scripts/tests/disk_tmp.py', '.ai/lifecycle.md'],
    'rationale': {
        '.ai/scripts/**': 'Conservative non-test script-directory scope: fixtures and demo copy all top-level Python scripts; the check watches their bytes. Includes future scripts and non-test descendants.',
        '!.ai/scripts/tests/**': 'Exclude unrelated tests before restoring the selected module and actual imported test helpers.',
        '.ai/scripts/tests/test_assurance_architecture.py': 'Selected CompatibilityTests class; executes the demo and reads the guide.',
        '.ai/scripts/tests/test_assurance.py': 'Imported Case fixture and constants; copies all top-level scripts into a temporary adopter.',
        '.ai/scripts/tests/test_assurance_gate.py': 'Imported GateCase and DeltaCase definitions, with covered fixture and production imports.',
        '.ai/scripts/tests/disk_tmp.py': 'Imported disk temporary-directory helper; its scratch dependency is within the production-script scope.',
        '.ai/lifecycle.md': 'Direct Markdown read and byte watch; asserts the published demo command, declaration and checker.',
    },
}, {
    'id': 'python-harness-wiring',
    'cwd': '.',
    'argv': ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py', 'HarnessWiring'],
    'inputs': ['.ai/scripts/**', '!.ai/scripts/tests/**',
               '.ai/scripts/tests/test_lifecycle_conformance.py', '.ai/scripts/tests/disk_tmp.py',
               '.claude/settings.json', '.codex/hooks.json', '.cursor/hooks.json'],
    'rationale': {
        '.ai/scripts/**': 'Conservative production import and lazy-loader setup scope; includes unused non-test descendants and future scripts, not a copied-directory boundary.',
        '!.ai/scripts/tests/**': 'Exclude unrelated tests before restoring the selected module and its imported test helper.',
        '.ai/scripts/tests/test_lifecycle_conformance.py': 'Selected HarnessWiring class parses hook JSON and asserts static lifecycle wiring declarations; it does not execute hooks.',
        '.ai/scripts/tests/disk_tmp.py': 'Imported temporary-storage helper; its scratch dependency is within the production-script scope.',
        '.claude/settings.json': 'Direct JSON read for Claude lifecycle event and matcher declarations.',
        '.codex/hooks.json': 'Direct JSON read for Codex lifecycle event and matcher declarations.',
        '.cursor/hooks.json': 'Direct JSON read for Cursor lifecycle event declarations.',
    },
}, {
    'id': 'python-reviewer-report-contract',
    'cwd': '.',
    'argv': ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
             'RolesAndSkills.test_reviewer_completion_report_contract'],
    'inputs': ['.ai/scripts/**', '!.ai/scripts/tests/**',
               '.ai/scripts/tests/test_lifecycle_conformance.py', '.ai/scripts/tests/disk_tmp.py',
               '.claude/agents/reviewer.md', '.codex/agents/reviewer.toml',
               '.ai/agents/reviewer.md', '.ai/lifecycle.md', '.claude/skills/review/SKILL.md'],
    'rationale': {
        '.ai/scripts/**': 'Conservative production import and lazy-loader setup scope; includes unused non-test descendants and future scripts, not a copied-directory boundary.',
        '!.ai/scripts/tests/**': 'Exclude unrelated tests before restoring the selected module and imported helper.',
        '.ai/scripts/tests/test_lifecycle_conformance.py': 'Selected reviewer-report method checks static instruction consistency; extracted commands are not executed and TOML is not structurally parsed.',
        '.ai/scripts/tests/disk_tmp.py': 'Imported temporary-storage helper; scratch is within the production-script scope.',
        '.claude/agents/reviewer.md': 'Direct text read of Claude reviewer section-loading instructions.',
        '.codex/agents/reviewer.toml': 'Direct text read of Codex reviewer section-loading instructions, not structural TOML validation.',
        '.ai/agents/reviewer.md': 'Direct text read of canonical report headings and return directions.',
        '.ai/lifecycle.md': 'Direct text read of Stage 3 report-preservation instructions.',
        '.claude/skills/review/SKILL.md': 'Direct text read of review-skill report-preservation instructions.',
    },
}, {
    'id': 'python-installer-doc-contract',
    'cwd': '.',
    'argv': ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
             'Distribution.test_readme_and_playbook_document_the_installer'],
    'inputs': ['.ai/scripts/**', '!.ai/scripts/tests/**',
               '.ai/scripts/tests/test_lifecycle_conformance.py', '.ai/scripts/tests/disk_tmp.py',
               '.ai/README.md', '.ai/docs/install-and-upgrade.md', '.ai/VERSION'],
    'rationale': {
        '.ai/scripts/**': 'Conservative production import and lazy-loader setup scope; includes unused non-test descendants and future scripts, not a copied-directory boundary.',
        '!.ai/scripts/tests/**': 'Exclude unrelated tests before restoring the selected module and imported helper.',
        '.ai/scripts/tests/test_lifecycle_conformance.py': 'Selected installer-documentation method checks static text tokens and the numeric VERSION regex; it does not run the installer.',
        '.ai/scripts/tests/disk_tmp.py': 'Imported temporary-storage helper; scratch is within the production-script scope.',
        '.ai/README.md': 'Direct text read of the Quick start installer-path token.',
        '.ai/docs/install-and-upgrade.md': 'Direct text read of five installer-documentation terms.',
        '.ai/VERSION': 'Direct non-Markdown text read checked with the existing numeric-version/newline regex, not semantic-version compatibility.',
    },
}, {
    'id': 'python-validation-policy-contract',
    'cwd': '.',
    'argv': ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
             'Relocation.test_agents_md_points_to_the_policy_and_the_policy_keeps_its_must_rules'],
    'inputs': ['.ai/scripts/**', '!.ai/scripts/tests/**',
               '.ai/scripts/tests/test_lifecycle_conformance.py', '.ai/scripts/tests/disk_tmp.py',
               'AGENTS.md', '.ai/validation-policy.md'],
    'rationale': {
        '.ai/scripts/**': 'Conservative production import and lazy-loader/decorator setup scope; includes unused non-test descendants and future scripts, not a copied-directory boundary.',
        '!.ai/scripts/tests/**': 'Exclude unrelated tests before restoring the selected module and imported helper.',
        '.ai/scripts/tests/test_lifecycle_conformance.py': 'Selected validation-policy method checks static text placement; it does not execute policy commands.',
        '.ai/scripts/tests/disk_tmp.py': 'Imported temporary-storage helper; scratch is within the production-script scope.',
        'AGENTS.md': 'Direct text read of two required reference/loading tokens and absence of four policy strings; explicit despite general Markdown freshness exemptions.',
        '.ai/validation-policy.md': 'Direct text read requiring four literal policy strings, not actual policy enforcement.',
    },
}, {
    'id': 'python-audit-doc-contract',
    'cwd': '.',
    'argv': ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
             'Tiers.test_the_committed_audit_record_is_documented'],
    'inputs': ['.ai/scripts/**', '!.ai/scripts/tests/**',
               '.ai/scripts/tests/test_lifecycle_conformance.py', '.ai/scripts/tests/disk_tmp.py',
               '.ai/lifecycle.md', '.ai/docs/lifecycle.md'],
    'rationale': {
        '.ai/scripts/**': 'Conservative production import and lazy-loader/decorator setup scope; includes unused non-test descendants and future scripts, not a copied-directory boundary.',
        '!.ai/scripts/tests/**': 'Exclude unrelated tests before restoring the selected module and imported helper.',
        '.ai/scripts/tests/test_lifecycle_conformance.py': 'Selected audit-documentation method checks static whole-document substring presence through a literal path loop; it does not execute audit commands.',
        '.ai/scripts/tests/disk_tmp.py': 'Imported temporary-storage helper; scratch is within the production-script scope.',
        '.ai/lifecycle.md': 'Direct text read requiring the lifecycle record-path and audit-command tokens, not actual audit behavior.',
        '.ai/docs/lifecycle.md': 'Direct text read requiring the same two tokens in the lifecycle guide, not command validity or record persistence.',
    },
}, {
    'id': 'python-analysis-convergence-doc-contract',
    'cwd': '.',
    'argv': ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
             'Tiers.test_analyze_and_converge_are_documented'],
    'inputs': ['.ai/scripts/**', '!.ai/scripts/tests/**',
               '.ai/scripts/tests/test_lifecycle_conformance.py', '.ai/scripts/tests/disk_tmp.py',
               '.ai/lifecycle.md', '.ai/docs/lifecycle.md', '.ai/validation-policy.md'],
    'rationale': {
        '.ai/scripts/**': 'Conservative production import and lazy-loader/decorator setup scope; includes unused non-test descendants and future scripts, not a copied-directory boundary.',
        '!.ai/scripts/tests/**': 'Exclude unrelated tests before restoring the selected module and imported helper.',
        '.ai/scripts/tests/test_lifecycle_conformance.py': 'Selected analysis/convergence documentation method checks static whole-document substrings through a literal path loop and a separate literal read; it executes no extracted command.',
        '.ai/scripts/tests/disk_tmp.py': 'Imported temporary-storage helper; scratch is within the production-script scope.',
        '.ai/lifecycle.md': 'Direct text read requiring analyze and converge command tokens, not actual analysis or convergence.',
        '.ai/docs/lifecycle.md': 'Direct text read requiring the same two command tokens in the lifecycle guide, not command validity.',
        '.ai/validation-policy.md': 'Direct text read of both command tokens through the loop and the convergence-evidence phrase through a separate literal call, not evidence matching or reuse behavior.',
    },
}, {
    'id': 'python-stage-doc-contract',
    'cwd': '.',
    'argv': ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
             'Tiers.test_every_stage_the_script_gates_is_described_in_the_lifecycle'],
    'inputs': ['.ai/scripts/**', '!.ai/scripts/tests/**',
               '.ai/scripts/tests/test_lifecycle_conformance.py', '.ai/scripts/tests/disk_tmp.py',
               '.ai/lifecycle.md'],
    'rationale': {
        '.ai/scripts/**': 'Conservative production import, runtime STAGES and lazy-loader/decorator construction scope; includes unused non-test descendants and future supported scripts, not a copied-directory boundary.',
        '!.ai/scripts/tests/**': 'Exclude unrelated tests before restoring the selected module and imported helper.',
        '.ai/scripts/tests/test_lifecycle_conformance.py': 'Selected method checks five static heading substrings and runtime lifecycle.STAGES set equality within one test; no lifecycle command is executed.',
        '.ai/scripts/tests/disk_tmp.py': 'Imported temporary-storage helper; scratch is within the production-script scope.',
        '.ai/lifecycle.md': 'Sole direct document read requiring five exact heading substrings, not section contents, order or actual stage enforcement.',
    },
}, {
    'id': 'python-tier-doc-contract',
    'cwd': '.',
    'argv': ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
             'Tiers.test_tier_definitions_agree_across_agents_lifecycle_and_script'],
    'inputs': ['.ai/scripts/**', '!.ai/scripts/tests/**',
               '.ai/scripts/tests/test_lifecycle_conformance.py', '.ai/scripts/tests/disk_tmp.py',
               'AGENTS.md', '.ai/lifecycle.md'],
    'rationale': {
        '.ai/scripts/**': 'Conservative production import, runtime TIERS/REQUIRED and lazy-loader/decorator construction scope; includes unused non-test descendants and future supported scripts, not a copied-directory boundary.',
        '!.ai/scripts/tests/**': 'Exclude unrelated tests before restoring the selected module and imported helper.',
        '.ai/scripts/tests/test_lifecycle_conformance.py': 'Selected method checks static bold substrings and regex matches per observed runtime tier, then REQUIRED/TIERS set equality within one test; no lifecycle command is executed.',
        '.ai/scripts/tests/disk_tmp.py': 'Imported temporary-storage helper; scratch is within the production-script scope.',
        'AGENTS.md': 'Direct text read repeated per observed runtime tier, requiring its bold substring; explicit despite general Markdown freshness exemptions.',
        '.ai/lifecycle.md': 'Direct text read repeated per observed runtime tier, requiring its unescaped interpolated pipe/space regex match, not table semantics or actual enforcement.',
    },
}, {
    'id': 'python-assurance-doc-contract',
    'cwd': '.',
    'argv': ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
             'Assurance.test_assurance_documented'],
    'inputs': ['.ai/scripts/**', '!.ai/scripts/tests/**',
               '.ai/scripts/tests/test_lifecycle_conformance.py', '.ai/scripts/tests/disk_tmp.py',
               '.ai/lifecycle.md'],
    'rationale': {
        '.ai/scripts/**': 'Conservative production import and lazy-loader/decorator construction scope; includes unused non-test descendants and future supported scripts, not a copied-directory boundary.',
        '!.ai/scripts/tests/**': 'Exclude unrelated tests before restoring the selected module and imported helper.',
        '.ai/scripts/tests/test_lifecycle_conformance.py': 'Selected method checks static assurance-section extraction, two body-token loops and a separate recording-row prefix within one test; no lifecycle command is executed.',
        '.ai/scripts/tests/disk_tmp.py': 'Imported temporary-storage helper; scratch is within the production-script scope.',
        '.ai/lifecycle.md': 'Sole direct document, read twice for first regex capture/body substring presence and a separate whole-document row-prefix regex, not assurance semantics or enforcement.',
    },
}, {
    'id': 'python-agents-budget-contract',
    'cwd': '.',
    'argv': ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
             'AgentsBudget.test_agents_md_stays_below_its_cold_start_budget'],
    'inputs': ['.ai/scripts/**', '!.ai/scripts/tests/**',
               '.ai/scripts/tests/test_lifecycle_conformance.py', '.ai/scripts/tests/disk_tmp.py',
               'AGENTS.md'],
    'rationale': {
        '.ai/scripts/**': 'Conservative production import and lazy-loader/decorator construction scope; includes unused non-test descendants and future supported scripts, not a copied-directory boundary.',
        '!.ai/scripts/tests/**': 'Exclude unrelated tests before restoring the selected module and imported helper.',
        '.ai/scripts/tests/test_lifecycle_conformance.py': 'Selected method makes one strict encoded-text length assertion within one test; no lifecycle command or historical baseline helper is executed.',
        '.ai/scripts/tests/disk_tmp.py': 'Imported temporary-storage helper; scratch is within the production-script scope.',
        'AGENTS.md': 'Sole direct document, read once with default decoding/newline translation then UTF-8 re-encoding for a strict less-than 30000 length assertion, not necessarily raw-file size.',
    },
}, {
    'id': 'python-semantic-lens-doc-contract',
    'cwd': '.',
    'argv': ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
             'RolesAndSkills.test_semantic_lens_in_analyst_reviewer_and_skills'],
    'inputs': ['.ai/scripts/**', '!.ai/scripts/tests/**',
               '.ai/scripts/tests/test_lifecycle_conformance.py', '.ai/scripts/tests/disk_tmp.py',
               '.ai/agents/analyst.md', '.ai/agents/reviewer.md',
               '.claude/skills/spec/SKILL.md', '.claude/skills/review/SKILL.md'],
    'rationale': {
        '.ai/scripts/**': 'Conservative production import and lazy-loader/decorator construction scope; includes unused non-test descendants and future supported scripts, not a copied-directory boundary.',
        '!.ai/scripts/tests/**': 'Exclude unrelated tests before restoring the selected module and imported helper.',
        '.ai/scripts/tests/test_lifecycle_conformance.py': 'Selected semantic-lens method checks fourteen case-sensitive presence assertions within one test; no lifecycle command is executed.',
        '.ai/scripts/tests/disk_tmp.py': 'Imported temporary-storage helper; scratch is within the production-script scope.',
        '.ai/agents/analyst.md': 'Direct whole-document read once for four terms and the analyze token, not actual semantic analysis.',
        '.ai/agents/reviewer.md': 'Direct read once for four whole-document terms and two tokens in the first literal Passes split capture, not review effectiveness.',
        '.claude/skills/spec/SKILL.md': 'Direct whole-document read once for the analyze token, not skill execution.',
        '.claude/skills/review/SKILL.md': 'Direct whole-document read once for converge and Validation Reviewed tokens, not skill execution.',
    },
}, {
    'id': 'python-skill-frontmatter-contract',
    'cwd': '.',
    'argv': ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
             'RolesAndSkills.test_skills_have_name_matching_directory_and_a_description'],
    'inputs': ['.ai/scripts/**', '!.ai/scripts/tests/**',
               '.ai/scripts/tests/test_lifecycle_conformance.py', '.ai/scripts/tests/disk_tmp.py',
               '.claude/skills/**'],
    'rationale': {
        '.ai/scripts/**': 'Conservative production import and lazy-loader/decorator construction scope; includes unused non-test descendants and future supported scripts.',
        '!.ai/scripts/tests/**': 'Exclude unrelated tests before restoring the selected module and imported helper.',
        '.ai/scripts/tests/test_lifecycle_conformance.py': 'Selected dynamic skill-frontmatter method checks name substrings and description regex matches within one test; no skill instructions are executed.',
        '.ai/scripts/tests/disk_tmp.py': 'Imported temporary-storage helper; scratch is within the production-script scope.',
        '.claude/skills/**': 'Conservative dynamic skill subtree: rglob SKILL.md reads split segment one for parent-name/newline and description checks; covers future supported skills and non-read assets with extra invalidation, without nonempty enforcement.',
    },
}]
LIMITATIONS = [
    'Declared repository input scope; review required when command reads or dependencies change.',
    'This is not complete read discovery, approval, or VERIFIED evidence; adoption is explicit.',
    'Runtime environment, executable, temporary storage and mount state remain outside this file-scope claim.',
    'Ignored files and external mutable data are not covered; unresolved application-data reads require retaining current scope.',
    'Full-suite coverage and existing inference, evidence matching and gates remain unchanged.',
]
REMEDIATION = 'Retain the current input scope; inspect dependencies before adding a reviewed profile. Omitted Inputs is not equivalent to explicit **.'


def strings(value):
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v.strip() for v in value)


def check_pattern(value, positive=False):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('input glob must be a nonempty string')
    if any(ord(c) < 32 or 127 <= ord(c) <= 159 or c in '\u2028\u2029`\\' for c in value):
        raise ValueError('input glob cannot be represented as a single-line POSIX Inputs value')
    if positive and value.startswith('!'):
        raise ValueError('supplemental inputs must be positive globs')
    if value.startswith('-'):
        raise ValueError('input glob would be interpreted as a lifecycle option')
    body = value[1:] if value.startswith('!') else value
    ledger.check_globs([body])
    return body


def catalog_checked(profiles):
    if not isinstance(profiles, list) or not profiles:
        raise ValueError('profile catalog must be a nonempty list')
    ids, commands = set(), set()
    for profile in profiles:
        if not isinstance(profile, dict) or set(profile) != {'id', 'cwd', 'argv', 'inputs', 'rationale'}:
            raise ValueError('profile needs id, cwd, argv, inputs and rationale')
        identity = profile['id']
        if not isinstance(identity, str) or not identity.strip() or profile['cwd'] != '.':
            raise ValueError('profile needs a nonempty ID and repository-root cwd')
        if not strings(profile['argv']) or not strings(profile['inputs']):
            raise ValueError('profile argv and inputs must be nonempty string lists')
        command = tuple(profile['argv'])
        if identity in ids or command in commands:
            raise ValueError('duplicate profile ID or ambiguous command/root match')
        ids.add(identity)
        commands.add(command)
        rationale = profile['rationale']
        if not isinstance(rationale, dict) or set(rationale) != set(profile['inputs']) or not all(
                isinstance(v, str) and v.strip() for v in rationale.values()):
            raise ValueError('profile rationale must explain every input')
        for pattern in profile['inputs']:
            check_pattern(pattern)
        if all(pattern.startswith('!') for pattern in profile['inputs']):
            raise ValueError('profile needs positive inputs')
    return profiles


def contained(root, path):
    try:
        path.resolve().relative_to(root)
    except (ValueError, RuntimeError) as error:
        raise ValueError('input path escapes or cannot resolve within the repository: ' + str(path)) from error


def check_paths(root, patterns, required):
    for pattern in patterns:
        body = check_pattern(pattern)
        prefix = root
        for part in body.split('/'):
            if any(c in part for c in '*?['):
                break
            prefix /= part
        contained(root, prefix)
        if any(c in body for c in '*?[') and (root / body).exists():
            raise ValueError('ambiguous literal filename containing glob metacharacters: ' + body)
    selected = ledger.input_paths(root, patterns)
    for name in selected:
        path = root / name
        contained(root, path)
        if not path.is_file():
            raise ValueError('selected input is missing or is not a file: ' + name)
    for pattern in patterns:
        if not pattern.startswith('!') and not any(c in pattern for c in '*?[') and not pattern.endswith('/'):
            if (root / pattern).exists() and pattern not in selected:
                raise ValueError('existing literal input is not a supported inventory file: ' + pattern)
    for pattern in required:
        if not pattern.startswith('!') and not any(c in pattern for c in '*?[') and not pattern.endswith('/'):
            if pattern not in selected or not (root / pattern).is_file():
                raise ValueError('required literal input is missing, ignored or excluded: ' + pattern)


def suggest(root, argv, extra=(), profiles=None, cwd=None):
    """Return a declared suggestion; supplied catalogs are a pure testing seam."""
    root = Path(root).resolve()
    if Path(cwd if cwd is not None else Path.cwd()).resolve() != root:
        raise ValueError('invoke the exporter from its repository root')
    result = subprocess.run(['git', '-C', str(root), 'rev-parse', '--show-toplevel'],
                            capture_output=True, text=True, timeout=10, check=False)
    if result.returncode or Path(result.stdout.strip()).resolve() != root:
        raise ValueError('exporter location must be the Git worktree root')
    catalog = catalog_checked(PROFILES if profiles is None else profiles)
    profile = next((p for p in catalog if p['argv'] == list(argv)), None)
    if profile is None:
        raise ValueError('no reviewed profile for this exact command; full suites retain broad scope')
    additions = list(extra)
    for pattern in additions:
        check_pattern(pattern, positive=True)
    patterns = [*profile['inputs'], *additions]
    check_paths(root, patterns, profile['inputs'])
    rationale = dict(profile['rationale'])
    for pattern in additions:
        rationale.setdefault(pattern, 'Author-supplied supplemental input; completeness requires review.')
    return {'schema_version': 1, 'ok': True, 'profile_id': profile['id'], 'argv': list(argv),
            'inputs': patterns, 'inputs_line': '  - Inputs: ' + ' '.join('`' + p + '`' for p in patterns),
            'lifecycle_inputs_argv': ['--inputs', *patterns], 'rationale': rationale,
            'limitations': list(LIMITATIONS), 'review_required': True}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None):
    raw = list(sys.argv[1:] if argv is None else argv)
    separator = raw.index('--') if '--' in raw else None
    options = raw[:separator] if separator is not None else raw
    as_json = '--json' in options
    parser = Parser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--extra-input', action='append', default=[], metavar='GLOB')
    try:
        args = parser.parse_args(options)
        if separator is None or not raw[separator + 1:]:
            raise ValueError('give a nonempty check command after --')
        value = suggest(Path(__file__).resolve().parents[2], raw[separator + 1:], args.extra_input)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        value = {'schema_version': 1, 'ok': False, 'reason': str(error), 'remediation': REMEDIATION}
        if as_json:
            print(json.dumps(value))
        else:
            print('inputs refused: ' + value['reason'] + '\n' + REMEDIATION, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(value))
    else:
        print('Profile: ' + value['profile_id'] + ' (declared; review required)')
        print('Command argv: ' + json.dumps(value['argv']))
        print(value['inputs_line'])
        print('Lifecycle input argv: ' + json.dumps(value['lifecycle_inputs_argv']))
        for name, reason in value['rationale'].items():
            print(name + ': ' + reason)
        for limit in value['limitations']:
            print(limit)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
