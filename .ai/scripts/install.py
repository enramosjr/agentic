#!/usr/bin/env python3
"""Bootstrap or check AGENTIC inside an existing or new project folder. Python 3.9+, Git, stdlib only."""
from __future__ import annotations

import argparse
import copy
from contextlib import nullcontext
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import review_guard

KIT = ("AGENTS.md", "CLAUDE.md", ".ai/", ".claude/agents/", ".claude/skills/",
       ".claude/settings.json", ".codex/agents/", ".codex/hooks.json",
       ".cursor/hooks.json", ".agents/skills", "THIRD_PARTY_NOTICES.md")
HOOK_FILES = (".claude/settings.json", ".codex/hooks.json", ".cursor/hooks.json")
MANIFEST = ".ai/install-manifest.json"
BEGIN = b"<!-- agent-governance-kit:begin -->"
END = b"<!-- agent-governance-kit:end -->"
ROOT = Path(__file__).resolve().parents[2]


class Refusal(Exception):
    """Invalid inputs or unsafe writes, detected before applying changes."""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(data, sorted_keys=False):
    return (json.dumps(data, indent=2, sort_keys=sorted_keys) + "\n").encode()


def kit_files(root, exclude=()):
    """Enumerate only explicit kit entries; never descend into harness local state."""
    names = []
    for entry in KIT:
        if entry == ".agents/skills":
            continue
        source = root / entry
        candidates = source.rglob("*") if source.is_dir() else [source]
        for path in candidates:
            rel = path.relative_to(root)
            if any(p in ("__pycache__", *exclude) for p in rel.parts) or path.suffix == ".pyc" or rel.as_posix() == MANIFEST:
                continue
            if path.is_file():
                names.append(rel.as_posix())
    return sorted(set(names))


def plain_files(root):
    return [p for p in kit_files(root) if p not in (*HOOK_FILES, "AGENTS.md", "CLAUDE.md")]


def read_json(path):
    try:
        data = json.loads(path.read_bytes())
        if not isinstance(data, dict) or not isinstance(data.get("hooks", {}), dict):
            raise ValueError("expected an object and an object-valued hooks key")
        return data
    except (ValueError, UnicodeError) as error:
        raise Refusal(f"{path}: repair JSON object ({error})") from error


def commands(data, flat=False, require_commands=False):
    result = set()
    try:
        for groups in data.get("hooks", {}).values():
            if not isinstance(groups, list):
                raise ValueError("hook event must be an array")
            for group in groups:
                hooks = [group] if flat else group.get("hooks", [])
                if not isinstance(hooks, list):
                    raise ValueError("hooks group must be an array")
                for hook in hooks:
                    if "command" not in hook and not require_commands:
                        continue
                    command = hook["command"]
                    if not isinstance(command, str):
                        raise ValueError("command must be a string")
                    result.add(command)
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        raise Refusal(f"repair hook entries: {error}") from error
    return sorted(result)


def expand_managed_matcher(groups, desired, previous):
    """Replace only a redundant canonical command's literal matcher subset."""
    hooks = desired.get("hooks", [])
    if len(hooks) != 1 or hooks[0].get("type", "command") != "command" or hooks[0].get("command") not in previous:
        return
    pattern = r"[A-Za-z][A-Za-z0-9_]*(?:\|[A-Za-z][A-Za-z0-9_]*)*"
    matcher = desired.get("matcher")
    if not isinstance(matcher, str) or not re.fullmatch(pattern, matcher):
        return
    wanted = set(matcher.split("|"))
    other = {key: value for key, value in desired.items() if key != "matcher"}
    for group in list(groups):
        old = group.get("matcher")
        if (not isinstance(old, str) or not re.fullmatch(pattern, old)
                or not set(old.split("|")) < wanted
                or {key: value for key, value in group.items() if key != "matcher"} != other):
            continue
        if desired in groups:
            groups.remove(group)
        else:
            group["matcher"] = matcher


def posix_hook_replacement(command):
    """Recognize exact pre-bootstrap kit commands, never arbitrary shell text."""
    missing = ("{ printf '%s\\n' 'AGENTIC POSIX hook: missing bootstrap; "
               "reinstall the project-local kit.' >&2; exit 2; }")
    layouts = (
        ('$(git rev-parse --show-toplevel)', '$r',
         "r=$(git rev-parse --show-toplevel) || { printf '%s\\n' "
         "'AGENTIC POSIX hook: Git root unavailable; install Git and open a trusted Git worktree.' "
         ">&2; exit 2; }; ",
         ('shell_guard.py', 'lifecycle.py" hook', 'review_native.py" hook --adapter codex')),
        ('$CLAUDE_PROJECT_DIR', '$CLAUDE_PROJECT_DIR', '',
         ('shell_guard.py" --skip-in-cursor', 'lifecycle.py" hook --skip-in-cursor',
          'review_native.py" hook --adapter claude', 'autonomy_hook.py')),
        ('', '', '', ('shell_guard.py', 'lifecycle.py" hook')),
    )
    for old_root, new_root, prelude, handlers in layouts:
        for handler in handlers:
            script, _, arguments = handler.partition('"')
            old_path = old_root + '/.ai/scripts/' if old_root else '.ai/scripts/'
            new_path = new_root + '/.ai/scripts/' if new_root else '.ai/scripts/'
            old = 'python3 ' + ('"' + old_path + script + '"' if old_root else old_path + script) + arguments
            if command == old:
                return (prelude + 'b="' + new_path + 'posix_hook.sh"; [ -f "$b" ] || ' + missing
                        + '; exec sh "$b" "' + new_path + script + '"' + arguments)
    return None


def migrate_posix_hooks(hooks, kit, previous, flat):
    """Retain adopter options while changing a manifest-owned command identity."""
    migrated = set()
    for event, groups in kit.get('hooks', {}).items():
        for desired in groups:
            wanted = [desired] if flat else desired.get('hooks', [])
            for group in list(hooks.get(event, [])):
                if group.get('matcher') != desired.get('matcher'):
                    continue
                for hook in [group] if flat else list(group.get('hooks', [])):
                    old = hook.get('command')
                    if old not in previous:
                        continue
                    replacement = posix_hook_replacement(old)
                    if replacement and any(h.get('command') == replacement for h in wanted):
                        hook['command'] = replacement
                        migrated.add(replacement)
                        # A partial upgrade may already contain the replacement.
                        # Owned legacy options win; retain replacement-only fields.
                        for peer_group in list(hooks[event]):
                            if peer_group.get('matcher') != desired.get('matcher'):
                                continue
                            for peer in [peer_group] if flat else list(peer_group.get('hooks', [])):
                                if peer is hook or peer.get('command') != replacement:
                                    continue
                                for key, value in peer.items():
                                    hook.setdefault(key, value)
                                if flat:
                                    hooks[event].remove(peer_group)
                                else:
                                    peer_group['hooks'].remove(peer)
    return migrated


def merge_hooks(adopter, kit, previous=(), flat=False):
    result = copy.deepcopy(adopter)
    for key, value in kit.items():
        result.setdefault(key, copy.deepcopy(value) if key != "hooks" else {})
    hooks = result.setdefault("hooks", {})
    previous = set(previous) | migrate_posix_hooks(hooks, kit, set(previous), flat)
    obsolete = set(previous) - set(commands(kit, flat, require_commands=True))
    for groups in hooks.values():
        if flat:
            groups[:] = [h for h in groups if h.get("command") not in obsolete]
        else:
            for group in groups:
                group["hooks"] = [h for h in group.get("hooks", []) if h.get("command") not in obsolete]
    for event, groups in kit.get("hooks", {}).items():
        dest = hooks.setdefault(event, [])
        for group in groups:
            if flat:
                if not any((h.get("command"), h.get("matcher")) == (group["command"], group.get("matcher")) for h in dest):
                    dest.append(copy.deepcopy(group))
            else:
                expand_managed_matcher(dest, group, previous)
                matches = [g for g in dest if g.get("matcher") == group.get("matcher")]
                if not matches:
                    dest.append(copy.deepcopy(group))
                else:
                    # Existing manifests own command identities, not adopter options.
                    # Add the new Windows launcher only where the adopter has none.
                    for existing in (h for g in matches for h in g.get("hooks", [])):
                        if existing.get("command") in previous and "commandWindows" not in existing:
                            desired = next((h for h in group.get("hooks", [])
                                            if h.get("command") == existing.get("command")), {})
                            if "commandWindows" in desired:
                                existing["commandWindows"] = desired["commandWindows"]
                    known = {h.get("command") for g in matches for h in g.get("hooks", [])}
                    for hook in group.get("hooks", []):
                        if hook["command"] not in known:
                            matches[0].setdefault("hooks", []).append(copy.deepcopy(hook))
                            known.add(hook["command"])
    return result


def agents_body(source):
    """Extract only shared governance when an installed kit is used as a template."""
    # Git may check out template text with CRLF. Keep the managed body canonical
    # across hosts; adopter bytes outside that body remain untouched.
    source = source.replace(b'\r\n', b'\n')
    lines = source.splitlines(keepends=True)
    begins = [i for i, line in enumerate(lines) if line.rstrip(b"\r\n") == BEGIN]
    ends = [i for i, line in enumerate(lines) if line.rstrip(b"\r\n") == END]
    if not begins and not ends:
        return source
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        raise Refusal("template AGENTS.md: repair to exactly one ordered begin/end marker pair")
    return b"".join(lines[begins[0] + 1:ends[0]])


def agents_content(current, body):
    lines = current.splitlines(keepends=True)
    begins = [i for i, line in enumerate(lines) if line.rstrip(b"\r\n") == BEGIN]
    ends = [i for i, line in enumerate(lines) if line.rstrip(b"\r\n") == END]
    if not begins and not ends:
        prefix = current + (b"\n" if current.endswith(b"\n") else b"\n\n") if current else b""
        return prefix + BEGIN + b"\n" + body + END + b"\n"
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        raise Refusal("AGENTS.md: repair to exactly one ordered begin/end marker pair")
    return b"".join(lines[:begins[0] + 1]) + body + b"".join(lines[ends[0]:])


def git(target, *args):
    runner = review_guard.run_owned if args[:1] == ('init',) else subprocess.run
    result = runner(["git", "-C", str(target), *args], capture_output=True, timeout=30)
    if result.returncode:
        raise Refusal("TARGET: choose the top level of a Git work tree")
    return result.stdout


def dirty_paths(target):
    fields = git(target, "status", "--porcelain=v1", "-z", "--untracked-files=all").split(b"\0")
    result, i = [], 0
    while i < len(fields) and fields[i]:
        entry = fields[i]
        result.append(os.fsdecode(entry[3:]))
        if b"R" in entry[:2] or b"C" in entry[:2]:
            i += 1
            result.append(os.fsdecode(fields[i]))
        i += 1
    return result


def needs_git_init(target):
    """Discover the worktree before creating anything, including for missing targets."""
    ancestor = target
    while not ancestor.exists():
        ancestor = ancestor.parent
    if not ancestor.is_dir():
        raise Refusal("TARGET: choose a directory, not a file or a path beneath one")
    result = subprocess.run(["git", "-C", str(ancestor), "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True, encoding='utf-8', timeout=30,
                            env={**os.environ, "LC_ALL": "C"})
    if result.returncode == 0:
        if Path(result.stdout.strip()).resolve() != target:
            raise Refusal("TARGET: choose the top level of the Git work tree")
        return False
    # Git errors (including bare repos, invalid metadata and ownership errors)
    # must not become permission to initialize a new or nested repository.
    metadata = (ancestor / ".git").exists() or (ancestor / ".git").is_symlink()
    if metadata or result.returncode != 128 or not result.stderr.startswith("fatal: not a git repository"):
        raise Refusal("TARGET: cannot inspect Git work tree: " + result.stderr.strip())
    return True


def atomic_write(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".kit-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            if hasattr(os, 'fchmod'):
                os.fchmod(stream.fileno(), mode)
            else:
                os.chmod(temp, mode)
        previous_mode = None
        if os.name == 'nt' and path.exists():
            current_mode = stat.S_IMODE(path.stat().st_mode)
            if not current_mode & stat.S_IWRITE:
                previous_mode = current_mode
                path.chmod(current_mode | stat.S_IWRITE)
        try:
            os.replace(temp, path)
        except BaseException:
            if previous_mode is not None and path.exists():
                path.chmod(previous_mode)
            raise
    finally:
        if os.path.exists(temp):
            if os.name == 'nt':
                os.chmod(temp, stat.S_IREAD | stat.S_IWRITE)
            os.unlink(temp)


def mode_matches(path, expected):
    actual = stat.S_IMODE(path.stat().st_mode)
    if os.name == 'nt':
        # Windows chmod represents the read-only bit, not POSIX execute/group bits.
        return bool(actual & stat.S_IWRITE) == bool(expected & stat.S_IWRITE)
    return actual == expected


def version(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise Refusal(".ai/VERSION: provide one MAJOR.MINOR.PATCH line")
    return tuple(int(p) for p in value.split("."))


def validate_manifest(data):
    if data is None:
        return
    if data.get("format") != 1 or not isinstance(data.get("files"), dict) or not isinstance(data.get("hooks"), dict):
        raise Refusal("install-manifest.json: repair format 1 files/hooks objects")
    version(data.get("template_version", ""))
    for name, hash_value in data["files"].items():
        p = PurePosixPath(name)
        allowed = name.startswith(".agents/skills/") or any(name.startswith(e) if e.endswith("/") else name == e for e in KIT)
        if p.is_absolute() or ".." in p.parts or name != p.as_posix() or not allowed or name in (MANIFEST, "AGENTS.md", "CLAUDE.md", *HOOK_FILES):
            raise Refusal("install-manifest.json: remove unsafe plain-file path")
        if not isinstance(hash_value, str) or not re.fullmatch(r"[a-f0-9]{64}", hash_value):
            raise Refusal("install-manifest.json: repair file hash")
    if any(not isinstance(v, list) or any(not isinstance(c, str) for c in v) for v in data["hooks"].values()):
        raise Refusal("install-manifest.json: repair hook command arrays")
    if data.get("skills_link") not in ("copy", "symlink"):
        raise Refusal("install-manifest.json: repair skills_link")


def install(target, template, check=False, force=False, no_knowledge=False):
    import framework_policy
    try:
        framework_policy.validate_source(template)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        raise Refusal(f'framework source refused before installation: {error}') from error
    target, template = target.resolve(), template.resolve()
    if target == template:
        raise Refusal("TARGET is the template root: choose a different repository")
    try:
        framework_policy.adopter_task(target, exact_target=True)
    except framework_policy.PolicyError as error:
        raise Refusal(f'framework target refused before installation: {error}') from error
    initialize_git = needs_git_init(target)
    if check and initialize_git:
        print("not installed (Git initialization required)")
        return 1
    try:
        raw_version = (template / ".ai/VERSION").read_text(encoding='utf-8')
    except OSError as error:
        raise Refusal(".ai/VERSION: create one MAJOR.MINOR.PATCH line") from error
    template_version = raw_version.strip()
    version(template_version)
    if len(raw_version.splitlines()) != 1:
        raise Refusal(".ai/VERSION: provide one MAJOR.MINOR.PATCH line")
    previous = read_json(target / MANIFEST) if (target / MANIFEST).exists() else None
    validate_manifest(previous)
    old = previous or {"files": {}, "hooks": {}}
    writes, removals, conflicts, problems = {}, set(), [], []

    def safe(name):
        path = target / name
        if not path.resolve().is_relative_to(target):
            raise Refusal(f"{name}: remove symlink escaping TARGET")
        for parent in path.parents:
            if parent == target:
                break
            if parent.exists() and not parent.is_dir():
                raise Refusal(f"{name}: replace non-directory parent")
        return path

    def read(name):
        path = safe(name)
        if path.exists() and not path.is_file():
            raise Refusal(f"{name}: replace non-file destination")
        return path.read_bytes() if path.exists() else None

    def put(name, data, mode=0o644):
        current = read(name)
        path = target / name
        if current != data or (path.exists() and not mode_matches(path, mode)):
            writes[name] = (data, mode)

    hashes = {}

    def resolve_file(name, data, file_mode, prior_hash):
        current = read(name)
        installed_hash = digest(current) if current is not None else None
        desired_hash = digest(data) if data is not None else None
        if data is not None:
            if current is None or installed_hash == desired_hash or installed_hash == prior_hash:
                put(name, data, file_mode)
                hashes[name] = desired_hash
            else:
                conflicts.append(name)
                if prior_hash:
                    hashes[name] = prior_hash
            if current is None:
                problems.append(f"missing: {name}")
            elif installed_hash != desired_hash or not mode_matches(target / name, file_mode):
                problems.append(f"drift: {name}")
        elif current is not None:
            problems.append(f"drift: {name}")
            if installed_hash == prior_hash:
                removals.add(name)
            else:
                conflicts.append(name)
                hashes[name] = prior_hash

    plain = set(plain_files(template))
    old_plain = {n for n in old["files"] if not n.startswith(".agents/skills/")}
    for name in sorted(plain | old_plain):
        path = template / name
        data = path.read_bytes() if name in plain else None
        file_mode = stat.S_IMODE(path.stat().st_mode) if data is not None else None
        resolve_file(name, data, file_mode, old["files"].get(name))

    # Pinned test oracles must survive a later Windows clone byte-for-byte,
    # including installations that intentionally omit the knowledge bundle.
    attribute_rule = b'.ai/scripts/tests/fixtures/qualification-baselines/** -text'
    attributes = read('.gitattributes') or b''
    if attribute_rule not in attributes.splitlines():
        separator = b'' if not attributes or attributes.endswith(b'\n') else b'\n'
        put('.gitattributes', attributes + separator + attribute_rule + b'\n')
        problems.append('attributes: .gitattributes')

    hook_manifest = {}
    for name in HOOK_FILES:
        flat = name == ".cursor/hooks.json"
        raw = read(name)
        ours = read_json(target / name) if raw is not None else {}
        kit = read_json(template / name)
        commands(ours, flat)
        hook_manifest[name] = commands(kit, flat, require_commands=True)
        merged = merge_hooks(ours, kit, old["hooks"].get(name, []), flat)
        if ours != merged or raw is None:
            put(name, encoded(merged), stat.S_IMODE((target / name).stat().st_mode) if raw is not None else 0o644)
            problems.append(f"hooks: {name}")

    body = agents_body((template / "AGENTS.md").read_bytes())
    current = read("AGENTS.md") or b""
    managed = agents_content(current, body)
    put("AGENTS.md", managed, stat.S_IMODE((target / "AGENTS.md").stat().st_mode) if current else 0o644)
    claude = read("CLAUDE.md") or b""
    imported = claude
    if b"@AGENTS.md" not in claude.splitlines():
        separator = (b"\n" if claude.endswith(b"\n") else b"\n\n") if claude else b""
        imported = claude + separator + b"@AGENTS.md\n"
    put("CLAUDE.md", imported, stat.S_IMODE((target / "CLAUDE.md").stat().st_mode) if claude else 0o644)
    if managed != current or imported != claude:
        problems.append("agents-block: AGENTS.md")

    link = target / ".agents/skills"
    safe(".agents")
    mode = old.get("skills_link", "symlink")
    make_link = False
    skill_names = [n for n in plain_files(template) if n.startswith(".claude/skills/")]
    if mode == "symlink":
        if not link.is_symlink() or os.readlink(link).replace('\\', '/') != "../.claude/skills":
            problems.append("drift: .agents/skills")
            if link.exists() or link.is_symlink():
                conflicts.append(".agents/skills")
            else:
                make_link = True
    else:
        incompatible = link.is_symlink() or (link.exists() and not link.is_dir())
        if incompatible:
            problems.append("drift: .agents/skills")
            conflicts.append(".agents/skills")
        aliases = {n.replace(".claude/skills/", ".agents/skills/", 1) for n in skill_names}
        aliases.update(n for n in old["files"] if n.startswith(".agents/skills/"))
        # Earlier format-1 copies can derive ownership from their canonical files.
        aliases.update(n.replace(".claude/skills/", ".agents/skills/", 1) for n in old["files"] if n.startswith(".claude/skills/"))
        if incompatible:
            hashes.update({n: h for n, h in old["files"].items() if n.startswith(".agents/skills/")})
        else:
            for dest in sorted(aliases):
                name = dest.replace(".agents/skills/", ".claude/skills/", 1)
                path = template / name
                data = path.read_bytes() if name in plain else None
                file_mode = stat.S_IMODE(path.stat().st_mode) if data is not None else None
                prior = old["files"].get(dest, old["files"].get(name))
                resolve_file(dest, data, file_mode, prior)

    manifest = {"format": 1, "template_version": template_version, "files": hashes,
                "hooks": hook_manifest, "agents_block": digest(body), "skills_link": mode}
    put(MANIFEST, encoded(manifest, True))
    if previous is None:
        problems.insert(0, "not installed")
    elif version(previous["template_version"]) < version(template_version):
        problems.append(f"outdated: {previous['template_version']} < {template_version}")
    if MANIFEST in writes and not problems:
        problems.append(f"drift: {MANIFEST}")
    if check:
        for problem in problems:
            print(problem)
        return 1 if problems else 0

    initialize = not no_knowledge and not (target / "knowledge/index.md").exists()
    knowledge_writes = []
    if initialize:
        # Model init's actual writes in a separate bundle, including its reindexing.
        with tempfile.TemporaryDirectory() as scratch:
            bundle = Path(scratch) / "knowledge"
            if (target / "knowledge").exists():
                shutil.copytree(target / "knowledge", bundle, symlinks=False)
            result = review_guard.run_owned([sys.executable, str(template / ".ai/scripts/okf.py"), "--bundle", str(bundle), "init"], capture_output=True, timeout=60)
            if result.returncode:
                raise Refusal("knowledge: repair the bundle before initialization")
            for path in bundle.rglob("*"):
                if path.is_file():
                    name = "knowledge/" + path.relative_to(bundle).as_posix()
                    if read(name) != path.read_bytes():
                        knowledge_writes.append(name)

    changing = set(writes) | removals | set(knowledge_writes)
    if make_link:
        changing.add(".agents/skills")
        # Symlink failure may require writing every descendant instead.
        changing.update(n.replace(".claude/skills/", ".agents/skills/", 1) for n in skill_names)
    for name in changing:
        safe(name)
    if not force and not initialize_git:
        for dirty in dirty_paths(target):
            if any(dirty == n or dirty.startswith(n + "/") or n.startswith(dirty + "/") for n in changing):
                raise Refusal(f"{dirty}: commit or stash changing paths, or use --force")
    # Validation/planning above is read-only for TARGET. Register before its first effect,
    # so refused inputs do not create or touch the containing repository's journal.
    ownership = review_guard.target_producer(target) if changing or initialize_git or initialize else nullcontext()
    with ownership:
        if initialize_git:
            target.mkdir(parents=True, exist_ok=True)
            git(target, "init", "--quiet")
        for name, (data, file_mode) in writes.items():
            if name == MANIFEST:
                continue
            if name in HOOK_FILES:
                before = (target / name).read_text(encoding='utf-8') if (target / name).exists() else ""
                print("".join(difflib.unified_diff(before.splitlines(True), data.decode().splitlines(True), fromfile=name, tofile=name)), end="")
            atomic_write(target / name, data, file_mode)
        for name in removals:
            (target / name).unlink()
        if make_link:
            link.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.symlink(os.path.join('..', '.claude', 'skills'), link, target_is_directory=True)
            except OSError:
                for name in skill_names:
                    dest = name.replace(".claude/skills/", ".agents/skills/", 1)
                    data = (template / name).read_bytes()
                    atomic_write(target / dest, data, stat.S_IMODE((template / name).stat().st_mode))
                    manifest["files"][dest] = digest(data)
                manifest["skills_link"] = "copy"
        if initialize:
            result = review_guard.run_owned([sys.executable, str(target / ".ai/scripts/okf.py"), "init"], cwd=target, capture_output=True, timeout=60)
            if result.returncode:
                raise OSError("installed okf.py init failed: " + result.stderr.decode(errors="replace"))
        if changing:
            atomic_write(target / MANIFEST, encoded(manifest, True))
    for name in conflicts:
        print(f"conflict: {name} (kept adopter copy)")
    print("installed" if changing else "up to date")
    print("trusted CI: external authority provisioning required; installation does not activate merge enforcement")
    return 1 if conflicts else 0


def sync_source_skills(root, check=False):
    root = root.resolve()
    marker = root / '.agentic.json'
    if not marker.is_file() or read_json(marker).get('repository_kind') != 'framework':
        raise Refusal('source skill synchronization requires a framework source checkout')
    canonical, aliases = root / '.claude/skills', root / '.agents/skills'
    if not canonical.resolve().is_relative_to(root) or not aliases.resolve().is_relative_to(root):
        raise Refusal('source skill paths must stay inside the framework checkout')
    desired = {}
    for source in canonical.rglob('*'):
        if source.is_file():
            if source.is_symlink() or not source.resolve().is_relative_to(canonical.resolve()):
                raise Refusal('canonical source skills must not escape through aliases')
            desired[source.relative_to(canonical)] = source
    if not desired:
        raise Refusal('canonical framework skills are missing')
    reparse = aliases.exists() and bool(getattr(aliases.lstat(), 'st_file_attributes', 0) & 0x400)
    replace_alias = aliases.is_symlink() or reparse or aliases.is_file()
    if aliases.is_file() and not aliases.is_symlink():
        if aliases.read_bytes().strip() != b'../.claude/skills':
            raise Refusal('source skills pointer is customized; refusing to overwrite it')
    elif replace_alias and aliases.resolve() != canonical.resolve():
        raise Refusal('source skills alias has an unexpected target')
    existing = {}
    if aliases.is_dir() and not replace_alias:
        for path in aliases.rglob('*'):
            if path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0) & 0x400):
                raise Refusal('generated source skills contain an unexpected alias')
            if path.is_file():
                existing[path.relative_to(aliases)] = path
    drift = replace_alias or set(existing) != set(desired) or any(
        existing[name].read_bytes() != source.read_bytes()
        for name, source in desired.items() if name in existing)
    if check or not drift:
        print('source skills drift' if drift else 'source skills up to date')
        return int(drift)
    with review_guard.target_producer(root):
        if replace_alias:
            if aliases.is_dir() and not aliases.is_symlink():
                aliases.rmdir()
            else:
                aliases.unlink()
        aliases.mkdir(parents=True, exist_ok=True)
        for name, path in existing.items():
            if name not in desired:
                path.unlink()
        for name, source in desired.items():
            atomic_write(aliases / name, source.read_bytes(), stat.S_IMODE(source.stat().st_mode))
        for path in sorted(aliases.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
    print('source skills synchronized')
    return 0


def main(argv=None, template=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report installation drift without writing files or initializing Git")
    parser.add_argument("--force", action="store_true", help="allow changing dirty paths; conflicting adopter files are still kept")
    parser.add_argument("--no-knowledge", action="store_true", help="skip creating the project's knowledge bundle")
    parser.add_argument('--sync-source-skills', action='store_true', help='refresh generated Codex skills in a framework source checkout')
    parser.add_argument("target", nargs='?', type=Path, help="existing project root or new folder; initializes Git when needed")
    args = parser.parse_args(argv)
    try:
        if args.sync_source_skills:
            if args.target is not None or args.force or args.no_knowledge:
                raise Refusal('--sync-source-skills accepts only --check')
            return sync_source_skills(template, args.check)
        if args.target is None:
            parser.error('target is required unless --sync-source-skills is selected')
        return install(args.target, template, args.check, args.force, args.no_knowledge)
    except (Refusal, review_guard.ReviewError) as error:
        print(f"install: {error}", file=sys.stderr)
        return 2
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"install: I/O failure: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import process_runtime
    process_runtime.configure_windows_environment()
    sys.exit(main())
