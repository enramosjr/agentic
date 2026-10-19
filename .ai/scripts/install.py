#!/usr/bin/env python3
"""Install or check the governance kit in a Git worktree. Python 3.9+, stdlib only."""
from __future__ import annotations

import argparse
import copy
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


def merge_hooks(adopter, kit, previous=(), flat=False):
    result = copy.deepcopy(adopter)
    for key, value in kit.items():
        result.setdefault(key, copy.deepcopy(value) if key != "hooks" else {})
    hooks = result.setdefault("hooks", {})
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
                matches = [g for g in dest if g.get("matcher") == group.get("matcher")]
                if not matches:
                    dest.append(copy.deepcopy(group))
                else:
                    known = {h.get("command") for g in matches for h in g.get("hooks", [])}
                    for hook in group.get("hooks", []):
                        if hook["command"] not in known:
                            matches[0].setdefault("hooks", []).append(copy.deepcopy(hook))
                            known.add(hook["command"])
    return result


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
    result = subprocess.run(["git", "-C", str(target), *args], capture_output=True, timeout=30)
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


def atomic_write(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".kit-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


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
    target, template = target.resolve(), template.resolve()
    if target == template:
        raise Refusal("TARGET is the template root: choose a different repository")
    if Path(os.fsdecode(git(target, "rev-parse", "--show-toplevel")).strip()).resolve() != target:
        raise Refusal("TARGET: choose the top level of the Git work tree")
    try:
        raw_version = (template / ".ai/VERSION").read_text()
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
        if current != data or (path.exists() and stat.S_IMODE(path.stat().st_mode) != mode):
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
            elif installed_hash != desired_hash or stat.S_IMODE((target / name).stat().st_mode) != file_mode:
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

    body = (template / "AGENTS.md").read_bytes()
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
        if not link.is_symlink() or os.readlink(link) != "../.claude/skills":
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
            result = subprocess.run([sys.executable, str(template / ".ai/scripts/okf.py"), "--bundle", str(bundle), "init"], capture_output=True, timeout=60)
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
    if not force:
        for dirty in dirty_paths(target):
            if any(dirty == n or dirty.startswith(n + "/") or n.startswith(dirty + "/") for n in changing):
                raise Refusal(f"{dirty}: commit or stash changing paths, or use --force")
    for name, (data, file_mode) in writes.items():
        if name == MANIFEST:
            continue
        if name in HOOK_FILES:
            before = (target / name).read_text() if (target / name).exists() else ""
            print("".join(difflib.unified_diff(before.splitlines(True), data.decode().splitlines(True), fromfile=name, tofile=name)), end="")
        atomic_write(target / name, data, file_mode)
    for name in removals:
        (target / name).unlink()
    if make_link:
        link.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink("../.claude/skills", link)
        except OSError:
            for name in skill_names:
                dest = name.replace(".claude/skills/", ".agents/skills/", 1)
                data = (template / name).read_bytes()
                atomic_write(target / dest, data, stat.S_IMODE((template / name).stat().st_mode))
                manifest["files"][dest] = digest(data)
            manifest["skills_link"] = "copy"
    if initialize:
        result = subprocess.run([sys.executable, str(target / ".ai/scripts/okf.py"), "init"], cwd=target, capture_output=True, timeout=60)
        if result.returncode:
            raise OSError("installed okf.py init failed: " + result.stderr.decode(errors="replace"))
    if changing:
        atomic_write(target / MANIFEST, encoded(manifest, True))
    for name in conflicts:
        print(f"conflict: {name} (kept adopter copy)")
    print("installed" if changing else "up to date")
    return 1 if conflicts else 0


def main(argv=None, template=ROOT):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-knowledge", action="store_true")
    parser.add_argument("target", type=Path)
    args = parser.parse_args(argv)
    try:
        return install(args.target, template, args.check, args.force, args.no_knowledge)
    except Refusal as error:
        print(f"install: {error}", file=sys.stderr)
        return 2
    except (OSError, subprocess.TimeoutExpired) as error:
        print(f"install: I/O failure: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
