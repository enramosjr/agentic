#!/usr/bin/env python3
"""Deterministic operations on an Open Knowledge Format (OKF v0.2) bundle.

Agents call this instead of reading, indexing, editing, or validating
``knowledge/`` by hand. Standard library only; Python 3.9+.

Run ``python3 .ai/scripts/okf.py --help`` for the command list.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator
from urllib.parse import unquote

OKF_VERSION = "0.2"
STANDARD_SECTIONS = (
    "project",
    "capabilities",
    "specifications",
    "history",
    "concepts",
    "playbooks",
)
RECOMMENDED_FIELDS = (
    "title",
    "description",
    "tags",
    "status",
    "evidence",
    "generated",
    "verified",
    "sources",
)
STATUS_VALUES = frozenset({"stable", "draft", "deprecated"})
EVIDENCE_VALUES = frozenset(
    {
        "implementation-and-current-specifications",
        "project-documentation",
        "validated-runtime",
    }
)
SCAN_ONLY_ACTOR = "process:repository-scan"
QUEUE_DOC = "project/work-queue.md"
ARCHIVE_DOC = "project/work-queue-archive.md"
STATUS_DOC = "project/status.md"
STATUS_BUDGET_CHARS = 6000
TASK_BUDGET_CHARS = 3000
SESSION_CAP = 3  # Implementation sessions one task may consume before it must be split (§9.2).
ACCEPTANCE_COMMAND_CAP = 8  # Backticked commands one task entry may list as acceptance.
PROTOCOL_DOC = ".ai/autonomous-execution.md"  # repo-relative
ROLES = ("solo", "orchestrator")
TASK_STATES = ("NOT_READY", "READY", "IN_PROGRESS", "BLOCKED", "DONE", "DEFERRED", "CANCELLED")
# Stored states the queue trusts as written; READY/NOT_READY are recomputed from dependencies.
DECLARED_STATES = frozenset({"IN_PROGRESS", "BLOCKED", "DONE", "DEFERRED", "CANCELLED"})
CLOSED_STATES = frozenset({"DONE", "CANCELLED"})
TASK_REQUIRED_FIELDS = {
    "IN_PROGRESS": ("Owner",),
    "BLOCKED": ("Blocker", "Unblock"),
    "DONE": ("Evidence",),
    "DEFERRED": ("Reason",),
    "CANCELLED": ("Reason",),
}
DEFAULT_PRIORITY = 100
STATUS_SECTIONS = (
    "Objective",
    "Active task",
    "In flight",
    "Next step",
    "Blockers",
    "Known failures",
    "Key decisions",
    "Last validation",
)
EMPTY_VALUES = frozenset({"", "-", "none", "n/a"})
INDEX_BEGIN = "<!-- okf:index:begin -->"
INDEX_END = "<!-- okf:index:end -->"
LOG_TITLE = "# OKF Change Log"

_KEY_RE = re.compile(r"^([A-Za-z_][\w.-]*)[ \t]*:(?:[ \t]+(.*))?$")
_FIELD_NAME_RE = re.compile(r"^[A-Za-z_][\w.-]*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
_INT_RE = re.compile(r"^[-+]?\d+$")
_FLOAT_RE = re.compile(r"^[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?$")
_PLAIN_RE = re.compile(r"^[\w./][\w ./()+'-]*$")
_AMBIGUOUS_PLAIN = frozenset(
    {"true", "false", "yes", "no", "on", "off", "null", "~", "y", "n"}
)
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)(?:\s+#+)?\s*$")
_LINK_RE = re.compile(r"\[(?:[^\]\\]|\\.)*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'(][^)]*)?\)")
_TASK_HEADING_RE = re.compile(r"^###\s+(\S+)\s+(?:—|–|--?)\s+(.+?)\s*$")
_TASK_FIELD_RE = re.compile(r"^[-*]\s+([A-Za-z][\w ]*?):\s*(.*?)\s*$")


class OkfError(Exception):
    """User-facing failure, reported on stderr with exit status 1."""


class FrontmatterError(OkfError):
    """Frontmatter is missing a terminator or outside the supported YAML subset."""


# --------------------------------------------------------------------------
# YAML subset: the frontmatter shapes OKF documents actually use.
# Scalars, quoted strings, flow lists/maps, one-level block maps, and block
# lists of scalars or flat maps. Anything else is rejected, not guessed.
# --------------------------------------------------------------------------


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _strip_comment(raw: str) -> str:
    quote: str | None = None
    i = 0
    while i < len(raw):
        ch = raw[i]
        if quote:
            if quote == '"' and ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'" and (i == 0 or raw[i - 1] in " \t[{,:"):
            quote = ch
        elif ch == "#" and (i == 0 or raw[i - 1] in " \t"):
            return raw[:i].rstrip()
        i += 1
    return raw


def _split_flow(inner: str, line: int) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    quote: str | None = None
    i = 0
    while i < len(inner):
        ch = inner[i]
        if quote:
            buf.append(ch)
            if quote == '"' and ch == "\\" and i + 1 < len(inner):
                buf.append(inner[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'" and not "".join(buf).strip():
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    if quote or depth:
        raise FrontmatterError(f"line {line}: unbalanced quotes or brackets")
    parts.append("".join(buf).strip())
    return [part for part in parts if part]


def parse_scalar(raw: str, line: int = 0) -> object:
    """Parse one inline YAML value (plain, quoted, or flow collection)."""
    s = raw.strip()
    if not s or s in ("~", "null", "Null", "NULL"):
        return None
    first = s[0]
    if first in "|>":
        raise FrontmatterError(f"line {line}: block scalars ('|', '>') are not supported")
    if first == '"':
        if len(s) < 2 or not s.endswith('"'):
            raise FrontmatterError(f"line {line}: unterminated double-quoted string")
        try:
            return json.loads(s)
        except json.JSONDecodeError as error:
            raise FrontmatterError(f"line {line}: invalid double-quoted string") from error
    if first == "'":
        if len(s) < 2 or not s.endswith("'"):
            raise FrontmatterError(f"line {line}: unterminated single-quoted string")
        return s[1:-1].replace("''", "'")
    if first == "[":
        if not s.endswith("]"):
            raise FrontmatterError(f"line {line}: unterminated flow list")
        return [parse_scalar(part, line) for part in _split_flow(s[1:-1], line)]
    if first == "{":
        if not s.endswith("}"):
            raise FrontmatterError(f"line {line}: unterminated flow map")
        mapping: dict[str, object] = {}
        for part in _split_flow(s[1:-1], line):
            key, sep, value = part.partition(":")
            if not sep:
                raise FrontmatterError(f"line {line}: flow map entry without ':': {part!r}")
            mapping[key.strip().strip("\"'")] = parse_scalar(value, line)
        return mapping
    if s in ("true", "True", "TRUE"):
        return True
    if s in ("false", "False", "FALSE"):
        return False
    if _INT_RE.match(s):
        return int(s)
    if _FLOAT_RE.match(s):
        return float(s)
    return s


def _inline_value(raw: str | None, line: int) -> object:
    return parse_scalar(_strip_comment(raw or ""), line)


def _parse_block_list(content: list[tuple[int, str]]) -> list[object]:
    items: list[object] = []
    dash_indent = _indent(content[0][1])
    current: dict[str, object] | None = None
    for lineno, line in content:
        indent = _indent(line)
        stripped = line.strip()
        if indent == dash_indent and (stripped == "-" or stripped.startswith("- ")):
            rest = stripped[1:].strip()
            match = None if rest[:1] in ("'", '"', "[", "{") else _KEY_RE.match(rest)
            if match:
                current = {match.group(1): _inline_value(match.group(2), lineno)}
                items.append(current)
            else:
                current = None
                items.append(_inline_value(rest, lineno))
            continue
        if current is None or indent <= dash_indent:
            raise FrontmatterError(f"line {lineno}: misplaced list content: {stripped!r}")
        match = _KEY_RE.match(stripped)
        if not match:
            raise FrontmatterError(f"line {lineno}: expected 'key: value' in list item")
        current[match.group(1)] = _inline_value(match.group(2), lineno)
    return items


def _parse_block(block: list[tuple[int, str]]) -> object:
    content = [
        (lineno, line)
        for lineno, line in block
        if line.strip() and not line.strip().startswith("#")
    ]
    if not content:
        return None
    if content[0][1].strip().startswith("-"):
        return _parse_block_list(content)
    mapping: dict[str, object] = {}
    base = _indent(content[0][1])
    for lineno, line in content:
        if _indent(line) != base:
            raise FrontmatterError(f"line {lineno}: nesting deeper than one level is not supported")
        match = _KEY_RE.match(line.strip())
        if not match:
            raise FrontmatterError(f"line {lineno}: expected 'key: value'")
        mapping[match.group(1)] = _inline_value(match.group(2), lineno)
    return mapping


def parse_frontmatter(text: str, first_line: int = 2) -> dict[str, object]:
    """Parse frontmatter text (without fences). ``first_line`` is its file line."""
    result: dict[str, object] = {}
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        lineno = first_line + i
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line[0].isspace() or line.startswith("-"):
            raise FrontmatterError(f"line {lineno}: unexpected indentation: {line.strip()!r}")
        match = _KEY_RE.match(line.rstrip())
        if not match:
            raise FrontmatterError(f"line {lineno}: expected 'key: value'")
        key, raw = match.group(1), match.group(2)
        if key in result:
            raise FrontmatterError(f"line {lineno}: duplicate key {key!r}")
        i += 1
        if raw is not None and _strip_comment(raw).strip():
            result[key] = _inline_value(raw, lineno)
            continue
        block: list[tuple[int, str]] = []
        while i < len(lines) and (
            not lines[i].strip() or lines[i][0].isspace() or lines[i].startswith("-")
        ):
            block.append((first_line + i, lines[i]))
            i += 1
        result[key] = _parse_block(block)
    return result


def dump_scalar(value: object) -> str:
    """Render a value in inline (flow) YAML form."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(dump_scalar(item) for item in value) + "]"
    if isinstance(value, dict):
        if not value:
            return "{}"
        return "{ " + ", ".join(f"{k}: {dump_scalar(v)}" for k, v in value.items()) + " }"
    text = str(value)
    if _TIMESTAMP_RE.match(text) or _DATE_RE.match(text):
        return text
    if (
        _PLAIN_RE.match(text)
        and not text.endswith(" ")
        and text.lower() not in _AMBIGUOUS_PLAIN
        and not _FLOAT_RE.match(text)
    ):
        return text
    return json.dumps(text, ensure_ascii=False)


def dump_entry(key: str, value: object) -> list[str]:
    """Render one top-level frontmatter entry as lines."""
    if isinstance(value, list) and any(isinstance(item, dict) for item in value):
        lines = [f"{key}:"]
        for item in value:
            if isinstance(item, dict) and item:
                for position, (k, v) in enumerate(item.items()):
                    prefix = "  - " if position == 0 else "    "
                    lines.append(f"{prefix}{k}: {dump_scalar(v)}")
            else:
                lines.append(f"  - {dump_scalar(item)}")
        return lines
    return [f"{key}: {dump_scalar(value)}"]


def split_frontmatter(text: str) -> tuple[str | None, str, int]:
    """Return (frontmatter text or None, body, 1-based file line of the body)."""
    lines = text.split("\n")
    if lines[0].rstrip() != "---":
        return None, text, 1
    for i in range(1, len(lines)):
        if lines[i].rstrip() in ("---", "..."):
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1 :]), i + 2
    raise FrontmatterError("unterminated frontmatter (missing closing '---')")


def _top_level_key(line: str) -> str | None:
    if not line or line[0].isspace():
        return None
    match = _KEY_RE.match(line.rstrip())
    return match.group(1) if match else None


def _key_span(lines: list[str], key: str) -> tuple[int, int] | None:
    start = next((i for i, line in enumerate(lines) if _top_level_key(line) == key), None)
    if start is None:
        return None
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and not line[0].isspace() and not line.startswith("-"):
            break
        end += 1
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return start, end


def update_frontmatter(text: str, updates: dict[str, object]) -> str:
    """Replace or append top-level keys, leaving every other line untouched."""
    fm, body, body_line = split_frontmatter(text)
    lines: list[str] = []
    if fm is not None:
        parse_frontmatter(fm)
        lines = fm.split("\n")
    else:
        body = text
    for key, value in updates.items():
        rendered = dump_entry(key, value)
        span = _key_span(lines, key)
        if span is None:
            while lines and not lines[-1].strip():
                lines.pop()
            lines.extend(rendered)
        else:
            lines[span[0] : span[1]] = rendered
    return "---\n" + "\n".join(lines) + "\n---\n" + body


# --------------------------------------------------------------------------
# Bundle documents
# --------------------------------------------------------------------------


@dataclass
class Doc:
    path: Path
    rel: str
    kind: str  # "root-index" | "index" | "log" | "concept"
    meta: dict[str, object] | None
    body: str
    body_line: int
    error: str | None = None

    @property
    def title(self) -> str:
        title = self.meta.get("title") if self.meta else None
        if isinstance(title, str) and title.strip():
            return title.strip()
        for _, level, text in headings(self):
            if level == 1:
                return text
        return self.path.stem

    def field(self, name: str) -> str:
        value = self.meta.get(name) if self.meta else None
        return "" if value is None else str(value)

    def tags(self) -> list[str]:
        value = self.meta.get("tags") if self.meta else None
        return [str(tag) for tag in value] if isinstance(value, list) else []


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _doc_kind(rel: str) -> str:
    name = rel.rsplit("/", 1)[-1]
    if rel == "index.md":
        return "root-index"
    if name == "index.md":
        return "index"
    if name == "log.md":
        return "log"
    return "concept"


def load_doc(bundle: Path, path: Path) -> Doc:
    text = read_text(path)
    rel = path.relative_to(bundle).as_posix()
    kind = _doc_kind(rel)
    try:
        fm, body, body_line = split_frontmatter(text)
        meta = parse_frontmatter(fm) if fm is not None else None
    except FrontmatterError as error:
        return Doc(path, rel, kind, None, text, 1, str(error))
    return Doc(path, rel, kind, meta, body, body_line)


def _is_hidden(path: Path, bundle: Path) -> bool:
    return any(part.startswith(".") for part in path.relative_to(bundle).parts)


def iter_docs(bundle: Path) -> list[Doc]:
    paths = sorted(p for p in bundle.rglob("*.md") if p.is_file() and not _is_hidden(p, bundle))
    return [load_doc(bundle, path) for path in paths]


def _lines_outside_fences(doc: Doc) -> Iterator[tuple[int, str]]:
    fence: str | None = None
    for offset, line in enumerate(doc.body.split("\n")):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is None:
            yield doc.body_line + offset, line


def headings(doc: Doc) -> list[tuple[int, int, str]]:
    """(file line, level, text) for each Markdown heading outside code fences."""
    found: list[tuple[int, int, str]] = []
    for lineno, line in _lines_outside_fences(doc):
        match = _HEADING_RE.match(line)
        if match:
            found.append((lineno, len(match.group(1)), match.group(2)))
    return found


def find_bundle(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    env = os.environ.get("OKF_BUNDLE")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[2] / "knowledge"


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def bundle_path(bundle: Path, raw: str) -> Path:
    """Resolve a doc path given relative to cwd, the repo, or the bundle."""
    path = Path(raw)
    if not path.is_absolute():
        candidates = ((Path.cwd() / path).resolve(), (bundle.parent / path).resolve())
        path = next((c for c in candidates if _is_within(c, bundle)), bundle / path)
    path = path.resolve()
    if not _is_within(path, bundle):
        raise OkfError(f"path is outside the OKF bundle {bundle}: {raw}")
    return path


def resolve_spec_path(bundle: Path, doc_path: Path, value: str) -> Path | None:
    """Resolve an OKF link or path field (SPEC §6.1, §6.2).

    URLs return None, ``/x`` is bundle-relative, anything else is relative to the document.
    """
    if _SCHEME_RE.match(value):
        return None
    if value.startswith("/"):
        return Path(os.path.normpath(bundle / value.lstrip("/")))
    return Path(os.path.normpath(doc_path.parent / value))


def existing_doc(bundle: Path, raw: str) -> Doc:
    path = bundle_path(bundle, raw)
    if not path.is_file():
        raise OkfError(f"no such OKF document: {raw}{_suggest(bundle, raw)}")
    return load_doc(bundle, path)


def _suggest(bundle: Path, raw: str) -> str:
    rels = sorted(
        p.relative_to(bundle).as_posix()
        for p in bundle.rglob("*.md")
        if p.is_file() and not _is_hidden(p, bundle)
    )
    stem = Path(raw).stem
    matches = [r for r in rels if Path(r).stem == stem] or difflib.get_close_matches(raw, rels, n=3, cutoff=0.4)
    if not matches:
        return " (run `okf.py list`)"
    return f" (did you mean: {', '.join(display(bundle, r) for r in matches)})"


def markdown_outside_bundle(bundle: Path, raw: str) -> Doc | None:
    """Load an existing Markdown file outside the bundle, such as a persona or agent role file."""
    if not Path(raw).is_absolute() and (bundle / raw).is_file():
        return None
    repo = bundle.parent
    for candidate in (Path.cwd() / raw, repo / raw):
        path = candidate.resolve()
        if path.suffix == ".md" and path.is_file() and not _is_within(path, bundle):
            return load_doc(repo if _is_within(path, repo) else path.parent, path)
    return None


def require_bundle(bundle: Path) -> None:
    if not (bundle / "index.md").is_file():
        raise OkfError(f"no OKF bundle at {bundle} (run `okf.py init`)")


def display(bundle: Path, rel: str) -> str:
    return f"{bundle.name}/{rel}" if rel else bundle.name


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_actor() -> str:
    return os.environ.get("OKF_ACTOR", "agent/unknown")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# --------------------------------------------------------------------------
# Index generation
# --------------------------------------------------------------------------


def _index_block(bundle: Path, directory: Path) -> str:
    entries: list[str] = []
    children = sorted(p for p in directory.iterdir() if not p.name.startswith("."))
    for child in children:
        if child.is_dir():
            entries.append(f"- [{child.name}/]({child.name}/index.md)")
    has_log = False
    for child in children:
        if not child.is_file() or child.suffix != ".md" or child.name == "index.md":
            continue
        if child.name == "log.md":
            has_log = True
            continue
        doc = load_doc(bundle, child)
        title = doc.title.replace("[", "\\[").replace("]", "\\]")
        entry = f"- [{title}]({child.name})"
        description = doc.field("description").strip()
        if description:
            entry += f" — {description}"
        entries.append(entry)
    if has_log:
        entries.append("- [Change log](log.md)")
    if not entries:
        entries.append("No documents yet.")
    return "\n".join([INDEX_BEGIN, *entries, INDEX_END])


def _render_index(existing: str | None, block: str, directory: Path, is_root: bool) -> str:
    if existing is None:
        if is_root:
            header = f'---\nokf_version: "{OKF_VERSION}"\n---\n\n# Knowledge Bundle\n\n'
        else:
            header = f"# {directory.name.replace('-', ' ').replace('_', ' ').title()}\n\n"
        return header + block + "\n"
    start = existing.find(INDEX_BEGIN)
    end = existing.find(INDEX_END)
    if start != -1 and end > start:
        return existing[:start] + block + existing[end + len(INDEX_END) :]
    return existing.rstrip("\n") + "\n\n" + block + "\n"


def reindex(bundle: Path, *, check: bool = False) -> list[Path]:
    """Regenerate the marked listing block in every index.md; return changed files."""
    directories = [bundle] + sorted(
        p for p in bundle.rglob("*") if p.is_dir() and not _is_hidden(p, bundle)
    )
    changed: list[Path] = []
    for directory in directories:
        index = directory / "index.md"
        existing = read_text(index) if index.is_file() else None
        rendered = _render_index(existing, _index_block(bundle, directory), directory, directory == bundle)
        if rendered != existing:
            changed.append(index)
            if not check:
                write_text(index, rendered)
    return changed


# --------------------------------------------------------------------------
# Change log
# --------------------------------------------------------------------------


def append_log(bundle: Path, message: str, day: date) -> Path:
    """Add a bullet under ``## day`` in log.md, keeping headings newest-first."""
    path = bundle / "log.md"
    text = read_text(path) if path.is_file() else LOG_TITLE + "\n"
    lines = text.rstrip("\n").split("\n")
    heading = f"## {day.isoformat()}"
    bullet = message if message.startswith("- ") else f"- {message}"

    existing = next((i for i, line in enumerate(lines) if line.strip() == heading), None)
    if existing is not None:
        end = next(
            (j for j in range(existing + 1, len(lines)) if lines[j].startswith("## ")),
            len(lines),
        )
        while end > existing + 1 and not lines[end - 1].strip():
            end -= 1
        lines.insert(end, bullet)
    else:
        position = len(lines)
        for i, line in enumerate(lines):
            text_after = line[3:].strip() if line.startswith("## ") else ""
            if _DATE_RE.match(text_after) and date.fromisoformat(text_after) < day:
                position = i
                break
        if position == len(lines):
            lines.extend(["", heading, "", bullet])
        else:
            lines[position:position] = [heading, "", bullet, ""]
    write_text(path, "\n".join(lines) + "\n")
    return path


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Issue:
    level: str  # "error" | "warning"
    path: str
    line: int | None
    message: str

    def render(self) -> str:
        location = f"{self.path}:{self.line}" if self.line else self.path
        return f"{self.level.upper()} {location}: {self.message}"


def _check_links(doc: Doc, bundle: Path, where: str) -> Iterator[Issue]:
    for lineno, line in _lines_outside_fences(doc):
        for target in _LINK_RE.findall(re.sub(r"`[^`]*`", "", line)):
            if target.startswith("#"):
                continue
            relative = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not relative:
                continue
            resolved = resolve_spec_path(bundle, doc.path, relative)
            if resolved is not None and not resolved.exists():
                yield Issue("error", where, lineno, f"broken link: {target}")


def _check_log(doc: Doc, where: str) -> Iterator[Issue]:
    previous: date | None = None
    seen: set[date] = set()
    for lineno, line in _lines_outside_fences(doc):
        if not line.startswith("## "):
            continue
        text = line[3:].strip()
        try:
            day = date.fromisoformat(text) if _DATE_RE.match(text) else None
        except ValueError:
            day = None
        if day is None:
            yield Issue("error", where, lineno, f"log heading must be '## YYYY-MM-DD', got {text!r}")
            continue
        if day in seen:
            yield Issue("error", where, lineno, f"duplicate log date {text}")
        elif previous is not None and day > previous:
            yield Issue("error", where, lineno, f"log dates must be newest-first ({text} after {previous})")
        seen.add(day)
        previous = day


def _check_concept(doc: Doc, bundle: Path, where: str) -> Iterator[Issue]:
    meta = doc.meta
    if meta is None:
        yield Issue("error", where, None, "concept document has no YAML frontmatter")
        return
    doc_type = meta.get("type")
    if not isinstance(doc_type, str) or not doc_type.strip():
        yield Issue("error", where, None, "frontmatter requires a non-empty 'type'")
    missing = [name for name in RECOMMENDED_FIELDS if meta.get(name) in (None, "", [])]
    if missing:
        yield Issue("warning", where, None, f"missing recommended fields: {', '.join(missing)}")
    status = meta.get("status")
    if status is not None and status not in STATUS_VALUES:
        yield Issue("warning", where, None, f"status {status!r} not in {sorted(STATUS_VALUES)}")
    evidence = meta.get("evidence")
    if evidence is not None and evidence not in EVIDENCE_VALUES:
        yield Issue("warning", where, None, f"evidence {evidence!r} not in {sorted(EVIDENCE_VALUES)}")
    tags = meta.get("tags")
    if tags is not None and not isinstance(tags, list):
        yield Issue("warning", where, None, "'tags' should be a list")
    generated = meta.get("generated")
    if generated is not None and not (isinstance(generated, dict) and generated.get("by")):
        yield Issue("warning", where, None, "'generated' should be a map with 'by' (and 'at')")
    verified = meta.get("verified")
    events = [] if verified is None else verified if isinstance(verified, list) else [verified]
    if not all(isinstance(event, dict) and event.get("by") and event.get("at") for event in events):
        yield Issue("warning", where, None, "'verified' should be a {by, at} map or a list of them")
    actors = {event.get("by") for event in events if isinstance(event, dict)}
    if evidence == "validated-runtime" and not actors - {None, SCAN_ONLY_ACTOR}:
        yield Issue(
            "warning",
            where,
            None,
            "evidence 'validated-runtime' needs verification by an executed test, not a repository scan",
        )
    sources = meta.get("sources")
    if sources is None:
        return
    if not isinstance(sources, list):
        yield Issue("warning", where, None, "'sources' should be a list")
        return
    for source in sources:
        resource = source.get("resource") if isinstance(source, dict) else None
        if not isinstance(resource, str) or not resource.strip():
            yield Issue("warning", where, None, "each 'sources' entry needs a 'resource'")
            continue
        resolved = resolve_spec_path(bundle, doc.path, resource)
        if resolved is not None and not resolved.exists():
            yield Issue("warning", where, None, f"source resource not found: {resource}")


def validate(bundle: Path) -> list[Issue]:
    if not bundle.is_dir():
        return [Issue("error", display(bundle, ""), None, "bundle directory does not exist")]
    issues: list[Issue] = []
    if not (bundle / "index.md").is_file():
        issues.append(Issue("error", display(bundle, "index.md"), None, "bundle root index.md is missing"))
    for doc in iter_docs(bundle):
        where = display(bundle, doc.rel)
        if doc.error:
            issues.append(Issue("error", where, None, doc.error))
            continue
        if doc.kind == "root-index":
            extra = sorted(set(doc.meta or {}) - {"okf_version"})
            if extra:
                issues.append(Issue("error", where, None, f"root index frontmatter may only contain okf_version (found {', '.join(extra)})"))
        elif doc.kind in ("index", "log") and doc.meta is not None:
            issues.append(Issue("error", where, None, f"{doc.path.name} must not have frontmatter"))
        if doc.kind == "log":
            issues.extend(_check_log(doc, where))
        elif doc.kind == "concept":
            issues.extend(_check_concept(doc, bundle, where))
            if doc.rel == QUEUE_DOC:
                try:
                    archived = _archived_tasks(bundle)
                except OkfError:
                    archived = []  # The archive's own frontmatter error is reported on its own entry.
                issues.extend(_check_queue(doc, where, archived))
            elif doc.rel == ARCHIVE_DOC:
                issues.extend(_check_queue(doc, where))
            elif doc.rel == STATUS_DOC and len(doc.body) > STATUS_BUDGET_CHARS:
                issues.append(Issue("warning", where, None,
                                    f"status body is {len(doc.body)} chars (budget {STATUS_BUDGET_CHARS}); "
                                    "every handoff prints it, so keep current facts and link evidence (§9.6)"))
        issues.extend(_check_links(doc, bundle, where))
    for index in reindex(bundle, check=True):
        rel = index.relative_to(bundle).as_posix()
        issues.append(Issue("warning", display(bundle, rel), None, "index is out of date (run `okf.py reindex`)"))
    return issues


# --------------------------------------------------------------------------
# Change impact
# --------------------------------------------------------------------------


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    except FileNotFoundError as error:
        raise OkfError("git is not installed; pass changed paths explicitly: okf.py affected PATH...") from error


def _git_changed(repo: Path, rev: str) -> list[str]:
    if _run_git(repo, "rev-parse", "--is-inside-work-tree").returncode != 0:
        raise OkfError(f"{repo} is not a git work tree; pass changed paths explicitly: okf.py affected PATH...")
    has_rev = _run_git(repo, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}").returncode == 0
    if not has_rev and rev != "HEAD":
        raise OkfError(f"unknown git revision: {rev}")
    # With no commits yet, every tracked file counts as changed.
    commands = (
        ("diff", "--name-only", "--relative", rev, "--") if has_rev else ("ls-files", "--cached"),
        ("ls-files", "--others", "--exclude-standard"),
    )
    paths: list[str] = []
    for command in commands:
        result = _run_git(repo, *command)
        if result.returncode != 0:
            detail = (result.stderr.strip().splitlines() or ["no output"])[0]
            raise OkfError(f"git {command[0]} failed: {detail}")
        paths.extend(line for line in result.stdout.splitlines() if line.strip())
    return paths


def _repo_relative(repo: Path, raw: str) -> str:
    path = Path(raw)
    if not path.is_absolute():
        return _normalize_resource(path.as_posix())
    try:
        return path.resolve().relative_to(repo).as_posix()
    except ValueError:
        return path.as_posix()


def _normalize_resource(resource: str) -> str:
    while resource.startswith("./"):
        resource = resource[2:]
    return resource.rstrip("/")


def affected(bundle: Path, changed: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    """Map changed repo paths to concept docs whose ``sources`` cover them."""
    bundle_prefix = bundle.name + "/"
    changed = sorted({path for path in changed if not path.startswith(bundle_prefix)})
    repo = bundle.parent
    hits: dict[str, list[str]] = {}
    covered: set[str] = set()
    for doc in iter_docs(bundle):
        if doc.kind != "concept" or not doc.meta or not isinstance(doc.meta.get("sources"), list):
            continue
        resources: list[str] = []
        for source in doc.meta["sources"]:
            raw = source.get("resource") if isinstance(source, dict) else None
            resolved = resolve_spec_path(bundle, doc.path, raw) if isinstance(raw, str) else None
            if resolved is not None and resolved != repo and _is_within(resolved, repo):
                resources.append(resolved.relative_to(repo).as_posix())
        matched = [
            path
            for path in changed
            if any(path == res or path.startswith(res + "/") for res in resources)
        ]
        if matched:
            hits[display(bundle, doc.rel)] = matched
            covered.update(matched)
    return hits, [path for path in changed if path not in covered]


# --------------------------------------------------------------------------
# Work queue, recovery checkpoint and handoff (autonomous execution)
# --------------------------------------------------------------------------


@dataclass
class Task:
    id: str
    title: str
    line: int
    fields: dict[str, str]
    text: str
    archived: bool = False

    def get(self, name: str) -> str:
        value = self.fields.get(name, "").strip()
        return "" if value.lower() in EMPTY_VALUES else value

    @property
    def state(self) -> str:
        return self.fields.get("State", "").strip().upper()

    @property
    def depends(self) -> list[str]:
        return [part.strip() for part in self.get("Depends").split(",") if part.strip().lower() not in EMPTY_VALUES]

    @property
    def parent(self) -> str:
        return self.get("Parent")

    @property
    def priority(self) -> int:
        raw = self.get("Priority")
        return int(raw) if _INT_RE.match(raw) else DEFAULT_PRIORITY


def parse_queue(doc: Doc) -> list[Task]:
    """Tasks are `### ID — Title` headings followed by `- Key: value` lines (fenced examples are skipped)."""
    tasks: list[Task] = []
    current: Task | None = None
    lines: list[str] = []
    for lineno, line in _lines_outside_fences(doc):
        heading = _HEADING_RE.match(line)
        if heading:
            if current is not None:
                current.text = "\n".join(lines).rstrip()
            match = _TASK_HEADING_RE.match(line)
            current = Task(match.group(1), match.group(2), lineno, {}, "") if match else None
            lines = [line]
            if current is not None:
                tasks.append(current)
            continue
        if current is None:
            continue
        lines.append(line)
        field = _TASK_FIELD_RE.match(line.strip())
        if field and field.group(1) not in current.fields:
            current.fields[field.group(1)] = field.group(2)
    if current is not None:
        current.text = "\n".join(lines).rstrip()
    return tasks


def effective_states(tasks: list[Task]) -> dict[str, str]:
    """Declared states are kept; READY/NOT_READY are derived from dependencies and children."""
    declared = {task.id: task.state for task in tasks}
    children: dict[str, list[str]] = {}
    for task in tasks:
        if task.parent:
            children.setdefault(task.parent, []).append(task.id)
    states: dict[str, str] = {}
    for task in tasks:
        if task.state in DECLARED_STATES:
            states[task.id] = task.state
            continue
        open_children = [c for c in children.get(task.id, []) if declared.get(c) not in CLOSED_STATES]
        deps_done = all(declared.get(dep) == "DONE" for dep in task.depends)
        states[task.id] = "READY" if deps_done and not open_children else "NOT_READY"
    return states


def next_tasks(tasks: list[Task]) -> list[Task]:
    """Unowned READY tasks without an execution hold, ordered by priority."""
    states = effective_states(tasks)
    ready = [(task.priority, index, task) for index, task in enumerate(tasks)
             if states[task.id] == "READY" and not task.get("Owner") and not task.get("Hold")]
    return [task for _, _, task in sorted(ready, key=lambda item: item[:2])]


def _dependency_cycle(tasks: list[Task]) -> list[str] | None:
    graph = {task.id: task.depends for task in tasks}
    visiting: list[str] = []
    done: set[str] = set()

    def visit(node: str) -> list[str] | None:
        if node in visiting:
            return visiting[visiting.index(node) :] + [node]
        if node in done or node not in graph:
            return None
        visiting.append(node)
        for dep in graph[node]:
            cycle = visit(dep)
            if cycle:
                return cycle
        visiting.pop()
        done.add(node)
        return None

    for task in tasks:
        cycle = visit(task.id)
        if cycle:
            return cycle
    return None


def _check_queue(doc: Doc, where: str, archived: list[Task] | None = None) -> Iterator[Issue]:
    """Validate the live queue, whose references may name `archived` tasks, or the archive itself.

    Archived tasks are closed, so the archive skips reference and cycle checks: a CANCELLED task
    may still name a dependency that lives in the queue.
    """
    tasks = parse_queue(doc)
    is_archive = doc.rel == ARCHIVE_DOC
    ids: dict[str, str] = {task.id: f"{ARCHIVE_DOC} line {task.line}" for task in archived or []}
    for task in tasks:
        if task.id in ids:
            yield Issue("error", where, task.line, f"duplicate task id {task.id} (first at {ids[task.id]})")
            continue
        ids[task.id] = f"line {task.line}"
    for task in tasks:
        if is_archive and task.state not in CLOSED_STATES:
            yield Issue("error", where, task.line, f"{task.id}: archived tasks must be DONE or CANCELLED, got {task.state or 'nothing'!r}")
            continue
        if task.state not in TASK_STATES:
            yield Issue("error", where, task.line, f"{task.id}: State must be one of {', '.join(TASK_STATES)}, got {task.state or 'nothing'!r}")
            continue
        missing = [name for name in TASK_REQUIRED_FIELDS.get(task.state, ()) if not task.get(name)]
        if missing:
            yield Issue("error", where, task.line, f"{task.id}: {task.state} requires {', '.join(missing)}")
        if task.get("Hold"):
            if task.state not in ("READY", "NOT_READY", "IN_PROGRESS"):
                yield Issue("error", where, task.line, f"{task.id}: Hold applies only to unfinished READY/NOT_READY/IN_PROGRESS work")
            if not task.get("Unblock"):
                yield Issue("error", where, task.line, f"{task.id}: Hold requires Unblock with the concrete resume condition")
        raw_priority = task.get("Priority")
        if raw_priority and not _INT_RE.match(raw_priority):
            yield Issue("error", where, task.line, f"{task.id}: Priority must be an integer, got {raw_priority!r}")
        raw_sessions = task.get("Sessions")
        if raw_sessions and not _INT_RE.match(raw_sessions):
            yield Issue("error", where, task.line, f"{task.id}: Sessions must be an integer, got {raw_sessions!r}")
        if is_archive:
            continue
        for dep in task.depends:
            if dep not in ids:
                yield Issue("error", where, task.line, f"{task.id}: unknown dependency {dep}")
        if task.parent and task.parent not in ids:
            yield Issue("error", where, task.line, f"{task.id}: unknown parent {task.parent}")
    if is_archive:
        return
    cycle = _dependency_cycle(tasks)
    if cycle:
        yield Issue("error", where, None, f"dependency cycle: {' -> '.join(cycle)}")


def _git_text(repo: Path, *args: str) -> str | None:
    """Trimmed stdout of a git command, or None outside a work tree or on failure."""
    try:
        result = _run_git(repo, *args)
    except OkfError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _archived_tasks(bundle: Path) -> list[Task]:
    path = bundle / ARCHIVE_DOC
    if not path.is_file():
        return []
    doc = load_doc(bundle, path)
    if doc.error:
        raise OkfError(f"{doc.rel}: {doc.error}")
    tasks = parse_queue(doc)
    for task in tasks:
        task.archived = True
    return tasks


def _load_queue(bundle: Path) -> tuple[Doc, list[Task]]:
    """The live queue doc and every task: archived ones first (closed, still resolvable), then live."""
    path = bundle / QUEUE_DOC
    if not path.is_file():
        raise OkfError(f"no work queue at {display(bundle, QUEUE_DOC)} (run `okf.py init --autonomous`)")
    doc = load_doc(bundle, path)
    if doc.error:
        raise OkfError(f"{doc.rel}: {doc.error}")
    return doc, _archived_tasks(bundle) + parse_queue(doc)


def _status_sections(bundle: Path) -> dict[str, str]:
    path = bundle / STATUS_DOC
    if not path.is_file():
        return {}
    doc = load_doc(bundle, path)
    sections: dict[str, str] = {}
    for _, level, text in headings(doc):
        if level == 2:
            body = _find_section(doc, text).split("\n", 1)
            sections[text] = body[1].strip() if len(body) > 1 else ""
    return sections


_ACCEPTANCE_COMMAND_RE = re.compile(r"`[^`\n]*\s[^`\n]*`")


def _session_count(task: Task) -> int:
    raw = task.get("Sessions")
    return int(raw) if _INT_RE.match(raw) else 0


def status_anchor(bundle: Path) -> str:
    """The task ID `status.md` names as the active batch anchor, or an empty string."""
    active = _status_sections(bundle).get("Active task", "").split()
    ident = active[0].rstrip(".,:;") if active else ""
    return "" if ident.lower() in EMPTY_VALUES else ident


def _anchor_task(bundle: Path) -> Task | None:
    anchor = status_anchor(bundle)
    if not anchor:
        return None
    _, tasks = _load_queue(bundle)
    task = next((t for t in tasks if t.id == anchor and not t.archived), None)
    return task if task is not None and effective_states(tasks).get(anchor) == "IN_PROGRESS" else None


def session_gate(bundle: Path) -> str | None:
    """Why another implementation session on the active task must not start, or None."""
    task = _anchor_task(bundle)
    if task is None or _session_count(task) < SESSION_CAP:
        return None
    return (f"task {task.id} has used {_session_count(task)} implementation sessions (cap {SESSION_CAP}); split it into "
            "separately gated tasks that start at zero, or close it. Raising --max-* flags does not reset this count (§9.2)")


def record_session(bundle: Path) -> tuple[str, int] | None:
    """Count one implementation session on the active task. The count lives in the queue, so it survives relaunches."""
    task = _anchor_task(bundle)
    if task is None:
        return None
    count = _session_count(task) + 1
    path = bundle / QUEUE_DOC
    lines = path.read_text(encoding="utf-8").split("\n")
    start = next(i for i, line in enumerate(lines) if (m := _TASK_HEADING_RE.match(line)) and m.group(1) == task.id)
    end = next((i for i in range(start + 1, len(lines)) if _HEADING_RE.match(lines[i])), len(lines))
    for i in range(start + 1, end):
        if re.match(r"^[-*]\s+Sessions:", lines[i]):
            lines[i] = f"- Sessions: {count}"
            break
    else:
        state = next((i for i in range(start + 1, end) if re.match(r"^[-*]\s+State:", lines[i])), start)
        lines.insert(state + 1, f"- Sessions: {count}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return task.id, count


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def checkpoint(bundle: Path, *, audit: bool = True) -> list[Check]:
    """Conditions under which a fresh agent can resume from repository state alone."""
    repo = bundle.parent
    checks: list[Check] = []
    sections = _status_sections(bundle)
    missing = [name for name in ("Active task", "Next step") if sections.get(name, "").strip() == ""]
    if not sections:
        checks.append(Check("status", False, f"{display(bundle, STATUS_DOC)} is missing (run `okf.py init --autonomous`)"))
    elif missing:
        checks.append(Check("status", False, f"empty or missing sections: {', '.join(missing)}"))
    else:
        checks.append(Check("status", True, "active task and next step recorded"))
        size = len(load_doc(bundle, bundle / STATUS_DOC).body)
        if size > STATUS_BUDGET_CHARS:
            checks.append(Check("status size", False,
                                f"status body is {size} chars (budget {STATUS_BUDGET_CHARS}); compact it to current facts and link evidence (§9.6)"))

    tasks: list[Task] = []
    queue_path = bundle / QUEUE_DOC
    if queue_path.is_file():
        doc = load_doc(bundle, queue_path)
        problem = doc.error
        archived: list[Task] = []
        try:
            archived = _archived_tasks(bundle)
        except OkfError as error:
            problem = problem or str(error)
        errors = [issue for issue in _check_queue(doc, display(bundle, QUEUE_DOC), archived) if issue.level == "error"] if not problem else []
        if problem or errors:
            checks.append(Check("queue", False, problem or f"{len(errors)} error(s); first: {errors[0].message}"))
        else:
            tasks = archived + parse_queue(doc)
            detail = f"{len(tasks) - len(archived)} task(s)" + (f" plus {len(archived)} archived" if archived else "")
            checks.append(Check("queue", True, f"{detail}, no errors"))
    else:
        checks.append(Check("queue", False, f"{display(bundle, QUEUE_DOC)} is missing (run `okf.py init --autonomous`)"))

    states = effective_states(tasks)
    running = [t for t in tasks if states.get(t.id) == "IN_PROGRESS" and not t.get("Hold")]
    oversized = [t.id for t in running if len(t.text) > TASK_BUDGET_CHARS]
    if oversized:
        checks.append(Check("task size", False,
                            f"IN_PROGRESS task entry over {TASK_BUDGET_CHARS} chars: {', '.join(oversized)}; "
                            "split it into separately gated tasks or compact it (§9.2)"))
    wide = [t.id for t in running if len(_ACCEPTANCE_COMMAND_RE.findall(t.text)) > ACCEPTANCE_COMMAND_CAP]
    if wide:
        checks.append(Check("acceptance commands", False,
                            f"IN_PROGRESS task lists more than {ACCEPTANCE_COMMAND_CAP} acceptance commands: {', '.join(wide)}; "
                            "split it into separately gated tasks (§9.2)"))
    spent = [f"{t.id} ({_session_count(t)})" for t in running if _session_count(t) > SESSION_CAP]
    if spent:
        checks.append(Check("sessions", False,
                            f"IN_PROGRESS task used more than {SESSION_CAP} sessions: {', '.join(spent)}; "
                            "split it into separately gated tasks that start at zero, or close it (§9.2)"))

    active = sections.get("Active task", "").split()
    active_id =active[0].rstrip(".,:;") if active else ""
    if active_id and active_id.lower() not in EMPTY_VALUES and sections:
        states = effective_states(tasks)
        state = states.get(active_id)
        ok = state == "IN_PROGRESS"
        detail = f"{active_id} is IN_PROGRESS" if ok else f"{active_id} is {state or 'not in the queue'}, expected IN_PROGRESS"
        checks.append(Check("active task", ok, detail))

    if _git_text(repo, "rev-parse", "--is-inside-work-tree") != "true":
        checks.append(Check("git", False, f"{repo} is not a git work tree"))
    else:
        # Porcelain lines are "XY path"; the leading column can be a space, so do not strip them.
        dirty = [line for line in _run_git(repo, "status", "--porcelain").stdout.splitlines() if line.strip()]
        checks.append(Check("clean tree", not dirty, "all work committed" if not dirty else f"{len(dirty)} uncommitted path(s), e.g. {dirty[0][3:]}"))
        head = _git_text(repo, "rev-parse", "HEAD")
        # Resumability depends on the records' contents, not which commit last touched them.
        # handoff() always supplies the actual branch and HEAD alongside those records.
        checks.append(Check("git HEAD", bool(head), "current HEAD available to handoff" if head else "no commits yet"))
        if audit:
            checks.append(_merge_driver_check(bundle))

    if audit:
        errors = [issue for issue in validate(bundle) if issue.level == "error"]
        checks.append(Check("okf validate", not errors, "0 errors" if not errors else f"{len(errors)} error(s); first: {errors[0].render()}"))
    return checks


def _git_summary(repo: Path) -> str:
    branch = _git_text(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if branch is None:
        return f"Repository: {repo} (not a git work tree)"
    head = _git_text(repo, "log", "-1", "--format=%h %s") or "no commits"
    return f"Repository: {repo}  Branch: {branch}  HEAD: {head}"


SESSION_SCOPE = {
    "solo": (
        "Session scope: one bounded integrated batch of related requirements that delivers a usable end-to-end flow. "
        "Continue the checkpoint's active batch, or select a batch starting from READY work. "
        f"A batch has at most {SESSION_CAP} sessions (the queue's Sessions count; a further session is refused). Preserve unfinished "
        "implementation in a safe checkpoint (`okf.py checkpoint` prints SAFE); do not run a full gate merely to end a session. "
        "Close every independently passing, reviewed part as DONE with its own scoped Evidence instead of holding it for the rest, "
        "and split anything that will not close within the cap into separately gated tasks."
    ),
    "orchestrator": (
        "Role: orchestrator (.ai/agents/orchestrator.md). Session scope: one batch round. "
        "Continue or select a bounded batch of related requirements delivering a usable end-to-end flow. "
        "Dispatch independent work in parallel only with disjoint files/fixtures and no dependency edge; "
        f"integrate and review reports, and write a safe checkpoint. A batch has at most {SESSION_CAP} sessions (queue Sessions count); "
        "continue unfinished implementation next session without a full gate merely for handoff, close independently passing "
        "reviewed parts as DONE with scoped Evidence, and split what will not close within the cap. "
        "Validate once the planned batch acceptance is implemented and reviewed."
    ),
}


def handoff(bundle: Path, mode: str = "state", task_id: str | None = None, role: str = "solo") -> str:
    """Resume material built from repository state only: `state`, `prompt` or a worker `task` brief."""
    repo = bundle.parent
    _, tasks = _load_queue(bundle)
    states = effective_states(tasks)
    sections = _status_sections(bundle)
    checks = checkpoint(bundle, audit=False)
    failed = [c for c in checks if not c.ok and c.name not in ("status", "clean tree")]
    verdict = "READY" if not failed else "BLOCKED (" + "; ".join(f"{c.name}: {c.detail}" for c in failed) + ")"
    checkpoint_note = "Checkpoint: NOT AUDITED; full checkpoint required at handoff/validation, not before implementation."
    dirty = next((c.detail for c in checks if c.name == "clean tree" and not c.ok), None)
    tree_note = (f"Uncommitted work: {dirty}; inspect `git status` and `git diff`, preserve work and resolve ownership before overlapping edits."
                 if dirty else "Working tree: committed base available.")

    if mode == "task":
        task = next((t for t in tasks if t.id == task_id), None)
        if task is None:
            raise OkfError(f"no task {task_id!r} in {display(bundle, QUEUE_DOC)}")
        return "\n".join(
            [
                f"You are a worker agent assigned exactly one task: {task.id} — {task.title} (state {states[task.id]}).",
                _git_summary(repo),
                "Follow AGENTS.md, including Gates 1-4 and the completeness mandate, in the implementer role.",
                "This brief replaces `okf.py context` and the autonomy protocol: skip both. Load the docs the task",
                "entry cites with `okf.py show --section`, and find others with `okf.py search`.",
                "Do not edit the work queue, its archive, or the status checkpoint; the run branch owns them.",
                "The assigned task may represent a coherent flow or an owned portion of the recorded batch;",
                "follow the supplied batch membership, dependency order, file ownership and test plan. Do not take unrelated work.",
                "External prerequisites must be DONE. An unfinished prerequisite must be an earlier member of this batch;",
                "start downstream work only after it is reviewed, merged into the batch head and passes focused acceptance checks.",
                "Parallel work requires disjoint files/fixtures and no dependency edge. Provisional integration does not mean DONE.",
                "Do not open a task PR. All milestone work belongs to the same milestone PR, titled M<N>: <Title>",
                "for the overall milestone scope. It stays draft until the entire milestone passes review, validation",
                "and exit criteria. Before reporting, merge the assigned milestone branch into your branch (never rebase or force-push),",
                "resolve conflicts, rerun affected focused checks, and push. During implementation use focused checks and tests;",
                "report their exact commands/outcomes and deferred full Validation commands for the integrated batch gate.",
                "Do not mark tasks DONE or check completed PR requirements before the integrated gate passes. The integrator runs",
                "the union of required full commands once at the integrated commit, deduplicated across batch members;",
                "rerun affected validation only after relevant code, fixes or base changes invalidate that evidence.",
                "Commit on your task branch. Finish with the implementer completion report: changed files, OKF docs",
                "updated, and every validation command with its outcome.",
                "",
                "Batch context from the checkpoint (read-only):",
                f"In flight: {sections.get('In flight', 'none recorded')}",
                f"Key decisions: {sections.get('Key decisions', 'none recorded')}",
                f"Next step: {sections.get('Next step', 'none recorded')}",
                f"Last validation: {sections.get('Last validation', 'none recorded')}",
                "",
                "Task entry:",
                task.text,
            ]
        )

    if mode == "prompt":
        objective = " ".join(sections.get("Objective", "none set").split())
        active = sections.get("Active task", "none") or "none"
        next_step = sections.get("Next step", "") or "Select a bounded flow batch starting from READY work."
        ready = next_tasks(tasks)[:5]
        selection = ("Queue empty: bootstrap the first eligible flow from the objective's roadmap and acceptance, "
                     "then start implementation in this session. Expand the remaining queue alongside disjoint worker "
                     "work and finish scope/dependency records by the real handoff; do not end a records-only bootstrap session."
                     if not tasks else "Next READY: " + ("; ".join(f"{t.id} — {t.title}" for t in ready) or "none"))
        return "\n".join(
            [
                "Resume autonomous work on this repository in a fresh session. Prior conversation is not available and not needed.",
                _git_summary(repo),
                f"Startup: {verdict}",
                checkpoint_note,
                tree_note,
                f"Objective: {objective}",
                f"Active task: {active.splitlines()[0]}",
                f"Next step: {' '.join(next_step.split())}",
                selection,
                "Execution holds: " + ("; ".join(f"{t.id}: {t.get('Hold')} (resume: {t.get('Unblock')})"
                    for t in tasks if t.get("Hold")) or "none"),
                "A held task is unfinished but not executable, even when IN_PROGRESS. Continue only eligible unheld work; do not repeat unchanged blocker checks.",
                f"Follow the Autonomous Execution Protocol ({PROTOCOL_DOC}; load it by section with `okf.py show`).",
                SESSION_SCOPE[role],
                "Select flows from this repository's objective, current roadmap, acceptance and queue; do not import another project's priorities.",
                "Reuse the recorded batch and claim. State only the task, owner, worktree and next check before dispatch.",
                "Start implementation without a planning/claim commit, push, or SAFE certification. Commit records at a real handoff.",
                "The handoff replaces a broad okf.py context inventory; load only missing task-specific docs/role sections.",
                "Discover document paths/headings once with okf.py list/search/show --outline, then read only needed sections; reuse loaded material.",
                "Do not load a whole role/protocol or repeat a broad discovery round before an otherwise specified worker can start.",
                "External prerequisites must be DONE; unfinished prerequisites must be earlier members of this same batch.",
                "Start downstream work only after prerequisites are reviewed, merged into the batch head and pass focused acceptance checks.",
                "Keep a task IN_PROGRESS until the gate covering its own acceptance passes; do not mark DONE to unlock a wave. Computed READY semantics stay unchanged.",
                "Use focused checks during implementation; run the union of full required commands once per integrated batch, deduplicated.",
                "A session boundary alone does not close a batch: keep unfinished acceptance IN_PROGRESS with focused evidence and deferred full commands, but the batch has a hard session cap and every part that passes its own acceptance and review is closed as DONE with scoped Evidence now. Split what cannot close within the cap into separately gated tasks (§9.2). Acceptance runs unattended in an isolated virtual display, never the user's.",
                "Record exact commands/outcomes and the integrated commit as shared evidence for every batch member; rerun affected validation",
                "only after relevant code, fixes or base changes invalidate it. Keep one milestone PR with a checkbox per requirement/task;",
                "check items only after review and the integrated gate pass, reopening them if later changes invalidate completion.",
                "Do not start unrelated work or another batch in this session: the next session continues from the checkpoint with fresh context.",
                "This prompt is the startup handoff; do not rerun handoff unless state changed or required recovery detail is missing.",
            ]
        )

    counts = {state: sum(1 for s in states.values() if s == state) for state in TASK_STATES}
    by_id = {task.id: task for task in tasks}
    lines = [
        "# Autonomous handoff (okf.py handoff)",
        "Repository state is authoritative; do not rely on prior conversation.",
        f"Follow the Autonomous Execution Protocol ({PROTOCOL_DOC}; load it by section with `okf.py show`).",
        _git_summary(repo),
        f"Startup: {verdict}",
        checkpoint_note,
        tree_note,
        "Queue: " + (", ".join(f"{n} {s}" for s, n in counts.items() if n) or "empty — bootstrap it from the canonical backlog"),
    ]
    for tid, state in states.items():
        task = by_id[tid]
        if state == "IN_PROGRESS":
            lines.append(f"In progress: {tid} — {task.title} (owner {task.get('Owner')})")
        elif state == "BLOCKED":
            lines.append(f"Blocked: {tid} — {task.get('Blocker')} (unblock: {task.get('Unblock')})")
        if task.get("Hold"):
            lines.append(f"Held: {tid} — {task.get('Hold')} (unblock: {task.get('Unblock')})")
    ready = next_tasks(tasks)[:5]
    lines.append("Next READY: " + ("; ".join(f"{t.id} — {t.title} [P{t.priority}]" for t in ready) or "none"))
    if failed:
        lines.append("Startup prerequisites are BLOCKED: resolve the named queue/Git inconsistency before affected work.")
    if sections:
        lines += ["", f"## Status checkpoint ({display(bundle, STATUS_DOC)})"]
        for name, body in sections.items():
            is_list = any(re.match(r"\s*(?:[-*]|\d+\.)\s", line) for line in body.splitlines())
            lines.append(f"{name}:\n{body}" if is_list else f"{name}: {' '.join(body.split())}")
    return "\n".join(lines)


QUEUE_TEMPLATE = """\
# Work queue

Execution state for planned work. Requirements, acceptance criteria and phase definitions stay in
their canonical documents; each entry references them by ID or link and never copies them. The
rules are in the Autonomous Execution Protocol in `.ai/autonomous-execution.md`. Inspect with
`okf.py queue`; move closed tasks to the archive with `okf.py queue --archive`.

## Tasks

Entry format (examples inside code fences are not parsed):

```markdown
### ID — Short title
- State: NOT_READY | READY | IN_PROGRESS | BLOCKED | DONE | DEFERRED | CANCELLED
- Priority: 100
- Group: phase or workstream name
- Parent: parent task ID, for subtasks
- Depends: comma-separated task IDs
- Acceptance: links or IDs of the canonical acceptance criteria
- Validation: `exact command` (repeat or comma-separate)
- Owner: agent-id@branch while IN_PROGRESS
- Evidence: link to the history record or log entry (DONE)
- Blocker / Unblock / Parallel: required detail when BLOCKED
- Hold / Unblock: suspend executable dispatch without claiming DONE; requires a concrete resume condition
- Reason / Decision: required detail when DEFERRED or CANCELLED
```
"""

STATUS_TEMPLATE = """\
# Current status

Recovery checkpoint for a fresh agent. Overwrite these sections in place at every checkpoint;
history belongs in `log.md` and `history/`. Keep it under about 60 lines.
Record the bounded batch's requirement IDs, dependency waves and file/fixture owners in In flight
and Key decisions. Record the focused/full test plan and deferred commands in Next step and
Last validation, with exact outcomes and integrated commit evidence shared by batch members.

## Objective

none set

## Active task

none

## In flight

nothing

## Next step

Bootstrap the work queue from the project's canonical roadmap or backlog, following
"Bootstrapping the queue" in the Autonomous Execution Protocol (`.ai/autonomous-execution.md`).

## Blockers

none

## Known failures

none recorded

## Key decisions

none

## Last validation

none recorded
"""


ARCHIVE_TEMPLATE = """\
# Work queue archive

Closed tasks moved out of the work queue by `okf.py queue --archive`, oldest first, so agents that
read the queue do not pay for finished work. Archived IDs stay reserved and still satisfy `Depends`
and `Parent` in the queue. Do not edit or reopen entries here; add a new task instead.

## Tasks
"""

AUTONOMY_DOCS = {
    QUEUE_DOC: ("Work Queue", "Work queue", "Execution state of planned tasks, referencing canonical requirements by ID.", QUEUE_TEMPLATE),
    STATUS_DOC: ("Status Checkpoint", "Current status", "Recovery checkpoint a fresh agent reads to resume work.", STATUS_TEMPLATE),
    ARCHIVE_DOC: ("Work Queue Archive", "Work queue archive", "Closed tasks moved out of the work queue; IDs stay reserved.", ARCHIVE_TEMPLATE),
}


def _create_autonomy_doc(bundle: Path, rel: str) -> Path:
    doc_type, title, description, body = AUTONOMY_DOCS[rel]
    path = bundle / rel
    meta: dict[str, object] = {
        "type": doc_type,
        "title": title,
        "description": description,
        "tags": ["autonomy", "workflow"],
        "status": "draft",
        "evidence": "project-documentation",
        "generated": {"by": default_actor(), "at": utc_now()},
    }
    if (bundle.parent / PROTOCOL_DOC).is_file():
        meta["sources"] = _parse_sources(bundle, path, [f"{PROTOCOL_DOC}=Autonomous Execution Protocol"])
    frontmatter = [line for key, value in meta.items() for line in dump_entry(key, value)]
    write_text(path, "---\n" + "\n".join(frontmatter) + "\n---\n\n" + body)
    return path


def _init_autonomy(bundle: Path) -> list[Path]:
    return [_create_autonomy_doc(bundle, rel) for rel in (QUEUE_DOC, STATUS_DOC) if not (bundle / rel).exists()]


def archive_closed(bundle: Path) -> list[str]:
    """Move DONE and CANCELLED tasks from the queue to the archive; return their IDs.

    Refuses while the queue has errors, so a malformed entry is never archived out of sight.
    """
    doc, tasks = _load_queue(bundle)
    archived = [task for task in tasks if task.archived]
    errors = [issue for issue in _check_queue(doc, display(bundle, QUEUE_DOC), archived) if issue.level == "error"]
    if errors:
        raise OkfError(f"queue has {len(errors)} error(s), first: {errors[0].message} (fix them, see `okf.py validate`)")
    closed = [task for task in tasks if not task.archived and task.state in CLOSED_STATES]
    if not closed:
        return []
    lines = read_text(doc.path).split("\n")
    # A task's block runs from its heading to the next heading outside fences (headings use file lines).
    starts = [lineno for lineno, _, _ in headings(doc)]
    moved: set[int] = set()
    blocks: list[str] = []
    for task in closed:
        end = next((start for start in starts if start > task.line), len(lines) + 1)
        span = range(task.line - 1, end - 1)
        moved.update(span)
        blocks.append("\n".join(lines[i] for i in span).rstrip())
    # Archive first: an interruption between the writes leaves a duplicate ID that `validate`
    # reports, never a lost task.
    archive_path = bundle / ARCHIVE_DOC
    if not archive_path.is_file():
        _create_autonomy_doc(bundle, ARCHIVE_DOC)
    archive_text = read_text(archive_path).rstrip("\n")
    write_text(archive_path, archive_text + "\n\n" + "\n\n".join(blocks) + "\n")
    kept = "\n".join(line for i, line in enumerate(lines) if i not in moved)
    write_text(doc.path, kept.rstrip("\n") + "\n")
    reindex(bundle)
    return [task.id for task in closed]


# --------------------------------------------------------------------------
# Git merge driver for bundle files that every branch touches
# --------------------------------------------------------------------------
#
# Each branch appends to log.md under the same date, regenerates index.md listings, and edits
# its own blocks of the queue or status. Line-based merges conflict on all of these although the
# edits are independent. These merges work per entry, per task, or per section instead: a key
# changed on one side takes that side; a key changed differently on both sides is a conflict
# (status.md keeps the current branch's side, since the run branch owns the checkpoint).

MERGE_DRIVER = "okf"
MERGED_FILES = ("log.md", "index.md", Path(QUEUE_DOC).name, Path(ARCHIVE_DOC).name, Path(STATUS_DOC).name)


def _merge3(base: str | None, ours: str | None, theirs: str | None) -> tuple[str | None, bool]:
    """Three-way merge of one value (None = absent); returns (value, conflicted)."""
    if ours == theirs or theirs == base:
        return ours, False
    if ours == base:
        return theirs, False
    return ours, True


def _merge_keyed(
    base: dict[str, str], ours: dict[str, str], theirs: dict[str, str], *, prefer_ours: bool = False
) -> tuple[dict[str, str], list[str]]:
    """Merge ordered key->text maps: our order first, then keys only the other side added."""
    merged: dict[str, str] = {}
    conflicts: list[str] = []
    for key in [*ours, *(k for k in theirs if k not in ours)]:
        value, conflicted = _merge3(base.get(key), ours.get(key), theirs.get(key))
        if conflicted and not prefer_ours:
            conflicts.append(key)
        if value is not None:
            merged[key] = value
    return merged, conflicts


def _merge_lines(base: list[str], ours: list[str], theirs: list[str]) -> list[str]:
    """Set-like merge of independent lines: keep ours, add theirs' additions, drop theirs' removals."""
    removed = {line for line in base if line not in theirs}
    return [line for line in ours if line not in removed] + [
        line for line in theirs if line not in ours and line not in base
    ]


def _chunks(text: str, boundary: re.Pattern[str], key: object) -> dict[str, str]:
    """Split at lines matching `boundary` outside code fences; `key(match)` names each chunk."""
    chunks: dict[str, list[str]] = {"": []}
    current = ""
    fence: str | None = None
    for line in text.split("\n"):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            fence = None if fence == stripped[:3] else fence or stripped[:3]
        match = boundary.match(line) if fence is None else None
        if match:
            current = key(match)  # type: ignore[operator]
            while current in chunks:  # a repeated heading keeps its own chunk
                current += "'"
            chunks[current] = []
        chunks[current].append(line)
    return {k: "\n".join(v).strip("\n") for k, v in chunks.items()}


def _join_chunks(chunks: dict[str, str]) -> str:
    return "\n\n".join(text for text in chunks.values() if text) + "\n"


def _merge_sections(texts: tuple[str, str, str], boundary: re.Pattern[str], key: object, *, prefer_ours: bool = False) -> str | None:
    base, ours, theirs = (_chunks(text, boundary, key) for text in texts)
    merged, conflicts = _merge_keyed(base, ours, theirs, prefer_ours=prefer_ours)
    return None if conflicts else _join_chunks(merged)


def _log_days(text: str) -> tuple[str, dict[str, list[str]]]:
    """(preamble, {date: entries}); an entry is a bullet plus any continuation lines."""
    preamble: list[str] = []
    days: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text.split("\n"):
        if line.startswith("## "):
            current = days.setdefault(line[3:].strip(), [])
        elif current is None:
            preamble.append(line)
        elif line.startswith("- "):
            current.append(line)
        elif line.strip() and current:
            current[-1] += "\n" + line
    return "\n".join(preamble).strip("\n"), days


def _merge_log(base: str, ours: str, theirs: str) -> str | None:
    (pre_b, days_b), (pre_o, days_o), (pre_t, days_t) = _log_days(base), _log_days(ours), _log_days(theirs)
    preamble, conflicted = _merge3(pre_b, pre_o, pre_t)
    if conflicted:
        return None
    days = {day: _merge_lines(days_b.get(day, []), days_o.get(day, []), days_t.get(day, [])) for day in {*days_o, *days_t}}
    parts = [preamble or LOG_TITLE]
    for day in sorted((d for d, entries in days.items() if entries), reverse=True):
        parts.append(f"## {day}\n\n" + "\n".join(days[day]))
    return "\n\n".join(parts) + "\n"


def _index_parts(text: str) -> tuple[str, list[str], str] | None:
    start, end = text.find(INDEX_BEGIN), text.find(INDEX_END)
    if start == -1 or end < start:
        return None
    lines = [line for line in text[start + len(INDEX_BEGIN) : end].split("\n") if line.strip()]
    return text[:start], lines, text[end + len(INDEX_END) :]


def _index_order(line: str) -> tuple[int, str]:
    """reindex order: directories, then documents by file name, then the change log."""
    target = re.search(r"\]\(([^)]*)\)", line)
    path = target.group(1) if target else line
    if path.endswith("/index.md"):
        return 0, path
    return (2, path) if path == "log.md" else (1, path)


def _merge_index(base: str, ours: str, theirs: str) -> str | None:
    parts = [_index_parts(text) for text in (base, ours, theirs)]
    if any(part is None for part in parts):
        return None
    (pre_b, lines_b, post_b), (pre_o, lines_o, post_o), (pre_t, lines_t, post_t) = parts  # type: ignore[misc]
    pre, pre_conflict = _merge3(pre_b, pre_o, pre_t)
    post, post_conflict = _merge3(post_b, post_o, post_t)
    if pre_conflict or post_conflict:
        return None
    placeholder = "No documents yet."
    lines = [line for line in _merge_lines(lines_b, lines_o, lines_t) if line != placeholder]
    lines = sorted(lines, key=_index_order) or [placeholder]
    return f"{pre}{INDEX_BEGIN}\n" + "\n".join(lines) + f"\n{INDEX_END}{post}"


def merge_bundle_file(path: str, base: str, ours: str, theirs: str) -> str | None:
    """Merged text for a bundle file the driver handles, or None when it conflicts."""
    name = Path(path).name
    if name == "log.md":
        return _merge_log(base, ours, theirs)
    if name == "index.md":
        return _merge_index(base, ours, theirs)
    if name in (Path(QUEUE_DOC).name, Path(ARCHIVE_DOC).name):
        # Frontmatter, preamble and non-task headings are chunks too, keyed by their heading line.
        boundary = re.compile(r"^(#{1,6}\s+.*)$")
        return _merge_sections((base, ours, theirs), boundary, lambda m: (_TASK_HEADING_RE.match(m.group(1)) or m).group(1))
    if name == Path(STATUS_DOC).name:
        return _merge_sections((base, ours, theirs), re.compile(r"^##\s+(.+?)\s*$"), lambda m: m.group(1), prefer_ours=True)
    return None


def run_merge_driver(base_path: str, ours_path: str, theirs_path: str, path: str) -> int:
    """Git merge driver: write the merge to `ours_path`; exit 0 when clean, 1 with conflict markers."""
    texts = [read_text(Path(p)) for p in (base_path, ours_path, theirs_path)]
    merged = merge_bundle_file(path, *texts)
    if merged is not None:
        Path(ours_path).write_text(merged, encoding="utf-8")
        return 0
    # Fall back to git's line merge so the conflict is presented the usual way.
    subprocess.run(["git", "merge-file", "-L", "ours", "-L", "base", "-L", "theirs", ours_path, base_path, theirs_path], check=False)
    return 1


def _gitattributes_lines(bundle: Path, repo: Path) -> list[str]:
    prefix = bundle.relative_to(repo).as_posix()
    patterns = [f"{prefix}/**/log.md", f"{prefix}/**/index.md", f"{prefix}/{QUEUE_DOC}", f"{prefix}/{ARCHIVE_DOC}", f"{prefix}/{STATUS_DOC}"]
    return [f"{pattern} merge={MERGE_DRIVER}" for pattern in patterns]


def git_setup(bundle: Path) -> list[str]:
    """Register the merge driver in the repository's git config and .gitattributes; return what changed."""
    repo = bundle.parent
    if _git_text(repo, "rev-parse", "--is-inside-work-tree") != "true":
        raise OkfError(f"{repo} is not a git work tree")
    # Git runs drivers from the top of the work tree being merged, so a repo-relative path makes
    # each worktree use its own copy of okf.py.
    script_path = Path(__file__).resolve()
    top = Path(_git_text(repo, "rev-parse", "--show-toplevel") or repo).resolve()
    script = script_path.relative_to(top).as_posix() if _is_within(script_path, top) else str(script_path)
    wanted = {
        f"merge.{MERGE_DRIVER}.name": "OKF bundle merge (okf.py merge-driver)",
        f"merge.{MERGE_DRIVER}.driver": f"python3 {script} merge-driver %O %A %B %P",
    }
    changed: list[str] = []
    for key, value in wanted.items():
        if _git_text(repo, "config", "--get", key) != value:
            _run_git(repo, "config", key, value)
            changed.append(f"git config {key}")
    attributes = repo / ".gitattributes"
    existing = read_text(attributes) if attributes.is_file() else ""
    missing = [line for line in _gitattributes_lines(bundle, repo) if line not in existing.split("\n")]
    if missing:
        header = ["# Merge OKF bundle files per entry, task and section (python3 .ai/scripts/okf.py git-setup)"]
        block = ([] if "okf.py git-setup" in existing else header) + missing
        write_text(attributes, (existing.rstrip("\n") + "\n\n" if existing.strip() else "") + "\n".join(block) + "\n")
        changed.append(".gitattributes")
    return changed


def _merge_driver_check(bundle: Path) -> Check:
    repo = bundle.parent
    attributes = repo / ".gitattributes"
    lines = read_text(attributes).split("\n") if attributes.is_file() else []
    missing = [line for line in _gitattributes_lines(bundle, repo) if line not in lines]
    configured = bool(_git_text(repo, "config", "--get", f"merge.{MERGE_DRIVER}.driver"))
    if missing or not configured:
        what = ".gitattributes entries" if missing else "git config"
        return Check("merge driver", False, f"{what} missing: parallel branches will conflict on log, index, queue and status (run `okf.py git-setup`)")
    return Check("merge driver", True, "bundle files merge per entry, task and section")


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def _print_written(bundle: Path, paths: list[Path], verb: str = "updated") -> None:
    for path in paths:
        print(f"{verb} {display(bundle, path.relative_to(bundle).as_posix())}")


def cmd_init(bundle: Path, args: argparse.Namespace) -> int:
    bundle.mkdir(parents=True, exist_ok=True)
    for name in STANDARD_SECTIONS:
        (bundle / name).mkdir(exist_ok=True)
    if not (bundle / "log.md").exists():
        append_log(bundle, "Initialized OKF bundle (`okf.py init`).", date.today())
        print(f"created {display(bundle, 'log.md')}")
    if args.autonomous:
        _print_written(bundle, _init_autonomy(bundle), "created")
        if _git_text(bundle.parent, "rev-parse", "--is-inside-work-tree") == "true":
            for change in git_setup(bundle):
                print(f"updated {change}")
    _print_written(bundle, reindex(bundle))
    return 0


def cmd_queue(bundle: Path, args: argparse.Namespace) -> int:
    require_bundle(bundle)
    if args.record_session:
        if os.environ.get("OKF_AUTONOMOUS") == "1":
            print("driver child: the driver already counted this session")
            return 0
        reason = session_gate(bundle)
        if reason:
            raise OkfError(reason)
        recorded = record_session(bundle)
        print(f"{recorded[0]}: session {recorded[1]} of {SESSION_CAP}" if recorded else "no IN_PROGRESS active task to count")
        return 0
    if args.archive:
        moved = archive_closed(bundle)
        print(f"archived {len(moved)} task(s) to {display(bundle, ARCHIVE_DOC)}: {', '.join(moved)}" if moved else "no DONE or CANCELLED tasks to archive")
        return 0
    _, tasks = _load_queue(bundle)
    states = effective_states(tasks)
    if args.next:
        selected = next_tasks(tasks)[: args.limit]
    else:
        wanted = args.state.upper() if args.state else None
        if wanted and wanted not in TASK_STATES:
            raise OkfError(f"--state must be one of {', '.join(TASK_STATES)}")
        # Archived tasks are listed only when asked for by state.
        selected = [t for t in tasks if (states[t.id] == wanted if wanted else not t.archived)]
    rows = [
        {
            "id": t.id,
            "title": t.title,
            "state": states[t.id],
            "priority": t.priority,
            "depends": t.depends,
            "parent": t.parent,
            "owner": t.get("Owner"),
            "line": t.line,
            "archived": t.archived,
        }
        for t in selected
    ]
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    if not rows:
        print("no matching tasks" if tasks else "queue is empty", file=sys.stderr)
        return 0
    width = max(len(row["id"]) for row in rows)
    for row in rows:
        owner = f"  @{row['owner']}" if row["owner"] else ""
        print(f"{row['id']:<{width}}  {row['state']:<11}  P{row['priority']:<4} {row['title']}{owner}")
    return 0


def cmd_checkpoint(bundle: Path, args: argparse.Namespace) -> int:
    require_bundle(bundle)
    checks = checkpoint(bundle)
    safe = all(check.ok for check in checks)
    if args.json:
        print(json.dumps({"safe": safe, "checks": [check.__dict__ for check in checks]}, indent=2))
    else:
        for check in checks:
            print(f"{'PASS' if check.ok else 'FAIL'} {check.name}: {check.detail}")
        print("SAFE" if safe else "UNSAFE")
    return 0 if safe else 1


def cmd_git_setup(bundle: Path, args: argparse.Namespace) -> int:
    require_bundle(bundle)
    changes = git_setup(bundle)
    print("\n".join(f"updated {change}" for change in changes) if changes else "merge driver already configured")
    return 0


def cmd_merge_driver(bundle: Path, args: argparse.Namespace) -> int:
    return run_merge_driver(args.base, args.ours, args.theirs, args.path)


def cmd_handoff(bundle: Path, args: argparse.Namespace) -> int:
    require_bundle(bundle)
    mode = "task" if args.task else "prompt" if args.prompt else "state"
    print(handoff(bundle, mode, args.task, args.role))
    return 0


def cmd_list(bundle: Path, args: argparse.Namespace) -> int:
    require_bundle(bundle)
    docs = [doc for doc in iter_docs(bundle) if doc.kind == "concept"]
    if args.type:
        docs = [d for d in docs if d.field("type").lower() == args.type.lower()]
    if args.status:
        docs = [d for d in docs if d.field("status") == args.status]
    if args.tag:
        docs = [d for d in docs if args.tag in d.tags()]
    if args.under:
        prefix = bundle_path(bundle, args.under).relative_to(bundle).as_posix().rstrip("/") + "/"
        docs = [d for d in docs if prefix == "./" or d.rel.startswith(prefix)]
    rows = [
        {
            "path": display(bundle, d.rel),
            "type": d.field("type"),
            "status": d.field("status"),
            "title": d.title,
            "description": d.field("description"),
            "tags": d.tags(),
        }
        for d in docs
    ]
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0
    if not rows:
        print("no matching documents", file=sys.stderr)
        return 0
    widths = {key: max(len(row[key]) for row in rows) for key in ("path", "type", "status")}
    for row in rows:
        print(
            f"{row['path']:<{widths['path']}}  {row['type'] or '-':<{widths['type']}}  "
            f"{row['status'] or '-':<{widths['status']}}  {row['title']}"
        )
        if args.long and row["description"]:
            print(f"    {row['description']}")
    return 0


def _find_section(doc: Doc, name: str) -> str:
    found = headings(doc)
    wanted = name.strip().lower()
    match = next((h for h in found if h[2].lower() == wanted), None)
    match = match or next((h for h in found if wanted in h[2].lower()), None)
    if match is None:
        available = ", ".join(h[2] for h in found) or "none"
        raise OkfError(f"section {name!r} not found in {doc.rel} (headings: {available})")
    lineno, level, _ = match
    end = next(
        (h[0] for h in found if h[0] > lineno and h[1] <= level),
        doc.body_line + len(doc.body.split("\n")),
    )
    lines = doc.body.split("\n")[lineno - doc.body_line : end - doc.body_line]
    return "\n".join(lines).rstrip()


def _load_for_show(bundle: Path, raw: str) -> tuple[Doc, str]:
    doc = markdown_outside_bundle(bundle, raw)
    if doc is not None:
        return doc, doc.rel
    require_bundle(bundle)
    doc = existing_doc(bundle, raw)
    return doc, display(bundle, doc.rel)


def _line_range(spec: str) -> tuple[int, int | None]:
    match = re.fullmatch(r"(\d+)(?:-(\d*))?", spec.strip())
    if not match or int(match.group(1)) < 1:
        raise OkfError(f"--lines must look like 20-60, 20-, or 20; got {spec!r}")
    start = int(match.group(1))
    if match.group(2) is None:
        return start, start
    return start, int(match.group(2)) if match.group(2) else None


def _show_payload(doc: Doc, label: str, args: argparse.Namespace) -> dict[str, object]:
    show_all = not (args.meta or args.outline or args.section or args.body or args.lines)
    payload: dict[str, object] = {"path": label, "kind": doc.kind}
    if args.meta or show_all:
        payload["meta"] = doc.meta
    if args.outline or show_all:
        payload["outline"] = [
            {"line": n, "level": lv, "text": t}
            for n, lv, t in headings(doc)
            if args.depth is None or lv <= args.depth
        ]
    if args.section:
        payload["sections"] = {name: _find_section(doc, name) for name in args.section}
    if args.lines:
        start, end = _line_range(args.lines)
        lines = read_text(doc.path).split("\n")
        payload["lines"] = [{"line": n, "text": lines[n - 1]} for n in range(start, min(end or len(lines), len(lines)) + 1)]
    if args.body:
        payload["body"] = doc.body
    return payload


def cmd_show(bundle: Path, args: argparse.Namespace) -> int:
    targets = [_load_for_show(bundle, raw) for raw in args.paths]
    for doc, label in targets:
        if doc.error:
            raise OkfError(f"{label}: {doc.error}")
    payloads = [_show_payload(doc, label, args) for doc, label in targets]
    if args.json:
        print(json.dumps(payloads[0] if len(payloads) == 1 else payloads, indent=2, ensure_ascii=False))
        return 0
    for payload in payloads:
        if len(payloads) > 1:
            print(f"==> {payload['path']} <==")
        if "meta" in payload:
            for key, value in (payload["meta"] or {}).items():
                print("\n".join(dump_entry(key, value)))
            if "outline" in payload:
                print()
        for entry in payload.get("outline", []):
            print(f"{entry['line']:>5}  {'#' * entry['level']} {entry['text']}")
        for text in payload.get("sections", {}).values():
            print(text)
            print()
        for entry in payload.get("lines", []):
            print(f"{entry['line']:>5}  {entry['text']}")
        if "body" in payload:
            print(str(payload["body"]).strip("\n"))
        if len(payloads) > 1:
            print()
    return 0


def _frontmatter_entries(directory: Path) -> list[tuple[str, str]]:
    entries = []
    for path in sorted(directory.glob("*.md")):
        try:
            fm, _, _ = split_frontmatter(read_text(path))
            meta = parse_frontmatter(fm) if fm is not None else {}
        except FrontmatterError:
            meta = {}
        entries.append((path.stem, str(meta.get("description") or "")))
    return entries


def cmd_context(bundle: Path, args: argparse.Namespace) -> int:
    ai = Path(__file__).resolve().parents[1]
    for heading, directory in (("Roles", ai / "agents"), ("Personas", ai / "personas")):
        print(f"{heading} (okf.py show {directory.relative_to(ai.parent).as_posix()}/NAME.md --outline --depth 2):")
        for name, description in _frontmatter_entries(directory):
            print(f"  {name}: {description[:140]}")
    print()
    if not (bundle / "index.md").is_file():
        print(f"Knowledge: no bundle at {bundle.name}/ (run `okf.py init`)")
        return 0
    print("Knowledge (okf.py show PATH --section HEADING):")
    for doc in iter_docs(bundle):
        if doc.kind == "concept":
            print(f"  {display(bundle, doc.rel)}  [{doc.field('type') or '-'}/{doc.field('status') or '-'}]  {doc.title}")
    log_path = bundle / "log.md"
    if log_path.is_file():
        days: list[tuple[str, list[str]]] = []
        for line in read_text(log_path).split("\n"):
            if line.startswith("## "):
                days.append((line[3:].strip(), []))
            elif line.startswith("- ") and days:
                days[-1][1].append(line[2:][:160])
        # Dates are newest-first; entries within a date are appended oldest-first.
        entries = [f"  {day} {text}" for day, texts in days for text in reversed(texts)][: args.log]
        print(f"\nRecent log ({len(entries)} newest):")
        print("\n".join(entries))
    return 0


def cmd_search(bundle: Path, args: argparse.Namespace) -> int:
    require_bundle(bundle)
    flags = 0 if args.case_sensitive else re.IGNORECASE
    pattern = re.compile(args.pattern if args.regex else re.escape(args.pattern), flags)
    root = bundle_path(bundle, args.under) if args.under else bundle
    if not root.exists():
        raise OkfError(f"no such bundle path: {args.under}{_suggest(bundle, args.under)}")
    paths = [root] if root.is_file() else sorted(p for p in root.rglob("*.md") if not _is_hidden(p, bundle))
    if not args.include_log:
        paths = [p for p in paths if p == root or p.name != "log.md"]
    total = 0
    for path in paths:
        rel = display(bundle, path.relative_to(bundle).as_posix())
        lines = read_text(path).split("\n")
        if args.count:
            count = sum(1 for line in lines if pattern.search(line))
            if count:
                print(f"{rel}: {count}")
            continue
        for lineno, line in enumerate(lines, start=1):
            if pattern.search(line):
                total += 1
                if total <= args.limit:
                    print(f"{rel}:{lineno}: {line.strip()[:160]}")
    if total > args.limit:
        print(f"... {total - args.limit} more matches (raise --limit)")
    return 0


def _parse_sources(bundle: Path, doc_path: Path, raw_sources: list[str]) -> list[dict[str, object]]:
    """Turn repo-relative ``--source`` values into doc-relative OKF paths (SPEC §6.2)."""
    sources: list[dict[str, object]] = []
    for raw in raw_sources:
        given, sep, title = raw.partition("=")
        given = given.strip()
        if not given:
            raise OkfError(f"empty --source value: {raw!r}")
        resource = given
        if not _SCHEME_RE.match(given) and not given.startswith("/"):
            resource = Path(os.path.relpath(bundle.parent / given, doc_path.parent)).as_posix()
        entry: dict[str, object] = {"id": _slug(given), "resource": resource}
        if sep and title.strip():
            entry["title"] = title.strip()
        sources.append(entry)
    return sources


def cmd_new(bundle: Path, args: argparse.Namespace) -> int:
    require_bundle(bundle)
    path = bundle_path(bundle, args.path)
    if path.suffix != ".md" or path.name in ("index.md", "log.md"):
        raise OkfError("concept documents must be .md files other than index.md/log.md")
    if path.exists():
        raise OkfError(f"already exists: {display(bundle, path.relative_to(bundle).as_posix())}")
    meta: dict[str, object] = {
        "type": args.type,
        "title": args.title,
        "description": args.description,
        "tags": [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else [],
        "status": args.status,
        "evidence": args.evidence,
        "generated": {"by": args.by, "at": utc_now()},
    }
    sources = _parse_sources(bundle, path, args.source or [])
    if sources:
        meta["sources"] = sources
    frontmatter = [line for key, value in meta.items() for line in dump_entry(key, value)]
    text = "---\n" + "\n".join(frontmatter) + f"\n---\n\n# {args.title}\n\n{args.description}\n"
    write_text(path, text)
    _print_written(bundle, [path], "created")
    _print_written(bundle, reindex(bundle))
    return 0


def _edit_frontmatter(bundle: Path, raw_path: str, updates: dict[str, object]) -> Path:
    doc = existing_doc(bundle, raw_path)
    if doc.kind != "concept":
        raise OkfError(f"{doc.rel}: only concept documents carry editable frontmatter")
    if doc.error:
        raise OkfError(f"{doc.rel}: {doc.error}")
    write_text(doc.path, update_frontmatter(read_text(doc.path), updates))
    return doc.path


def cmd_set(bundle: Path, args: argparse.Namespace) -> int:
    require_bundle(bundle)
    updates: dict[str, object] = {}
    for assignment in args.assignments:
        key, sep, value = assignment.partition("=")
        if not sep or not _FIELD_NAME_RE.match(key):
            raise OkfError(f"expected KEY=VALUE, got {assignment!r}")
        updates[key] = parse_scalar(value)
    _print_written(bundle, [_edit_frontmatter(bundle, args.path, updates)])
    _print_written(bundle, reindex(bundle))
    return 0


def cmd_stamp(bundle: Path, args: argparse.Namespace) -> int:
    require_bundle(bundle)
    at = args.at or utc_now()
    if not _TIMESTAMP_RE.match(at):
        raise OkfError(f"--at must be an ISO-8601 timestamp like 2026-07-27T00:00:00Z, got {at!r}")
    written = [_edit_frontmatter(bundle, raw, {args.field: {"by": args.by, "at": at}}) for raw in args.paths]
    _print_written(bundle, written)
    return 0


def cmd_log(bundle: Path, args: argparse.Namespace) -> int:
    require_bundle(bundle)
    try:
        day = date.fromisoformat(args.date) if args.date else date.today()
    except ValueError as error:
        raise OkfError(f"--date must be YYYY-MM-DD, got {args.date!r}") from error
    message = " ".join(args.message).strip()
    if not message:
        raise OkfError("log message is empty")
    _print_written(bundle, [append_log(bundle, message, day)])
    return 0


def cmd_reindex(bundle: Path, args: argparse.Namespace) -> int:
    require_bundle(bundle)
    changed = reindex(bundle, check=args.check)
    if args.check:
        _print_written(bundle, changed, "stale")
        return 1 if changed else 0
    _print_written(bundle, changed)
    return 0


def cmd_validate(bundle: Path, args: argparse.Namespace) -> int:
    issues = validate(bundle)
    errors = sum(issue.level == "error" for issue in issues)
    warnings = len(issues) - errors
    if args.json:
        print(json.dumps([issue.__dict__ for issue in issues], indent=2, ensure_ascii=False))
    else:
        for issue in issues:
            print(issue.render())
        print(f"{'FAIL' if errors or (args.strict and warnings) else 'OK'}: {errors} errors, {warnings} warnings")
    return 1 if errors or (args.strict and warnings) else 0


def cmd_records(bundle: Path, args: argparse.Namespace) -> int:
    require_bundle(bundle)
    failed = []
    errors = [issue for issue in validate(bundle) if issue.level == "error"]
    for issue in errors:
        print(issue.render())
    print(f"validate: {'FAIL' if errors else 'OK'} ({len(errors)} errors)")
    failed += ["validate"] if errors else []
    stale = reindex(bundle, check=True)
    _print_written(bundle, stale, "stale")
    print(f"reindex --check: {'FAIL' if stale else 'OK'}")
    failed += ["reindex"] if stale else []
    repo = bundle.parent
    if _run_git(repo, "rev-parse", "--is-inside-work-tree").returncode == 0:
        has_head = _run_git(repo, "rev-parse", "--verify", "--quiet", "HEAD^{commit}").returncode == 0
        target = args.base or ("HEAD" if has_head else "--cached")
        diff = _run_git(repo, "diff", "--check", target)
        if diff.returncode and not diff.stdout:
            raise OkfError(f"git diff --check {target} failed: {diff.stderr.strip()}")
        if diff.stdout:
            print(diff.stdout.rstrip())
        print(f"git diff --check {target}: {'FAIL' if diff.returncode else 'OK'}")
        failed += ["whitespace"] if diff.returncode else []
    else:
        print("git diff --check: skipped (not a git work tree)")
    print(f"records: {'FAIL (' + ', '.join(failed) + ')' if failed else 'OK'}")
    return 1 if failed else 0


def cmd_affected(bundle: Path, args: argparse.Namespace) -> int:
    require_bundle(bundle)
    repo = bundle.parent
    changed = [_repo_relative(repo, raw) for raw in args.paths]
    if args.git is not None or not args.paths:
        changed += _git_changed(repo, args.git or "HEAD")
    hits, uncovered = affected(bundle, changed)
    if args.json:
        print(json.dumps({"affected": hits, "uncovered": uncovered}, indent=2))
        return 0
    if not hits and not uncovered:
        print("no changed files outside the bundle")
        return 0
    for doc_path, files in hits.items():
        print(doc_path)
        for path in files:
            print(f"  <- {path}")
    if uncovered:
        print("uncovered (no OKF doc lists these in sources):")
        for path in uncovered:
            print(f"  {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="okf.py",
        description="Token-cheap, deterministic operations on the OKF knowledge bundle.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Doc paths may be bundle-relative (capabilities/x.md) or repo-relative\n"
            "(knowledge/capabilities/x.md). Bundle: --bundle, $OKF_BUNDLE, or <repo>/knowledge.\n"
            "\n"
            "Frontmatter rules enforced by `validate`:\n"
            "  errors:   concept docs need frontmatter with a non-empty `type`; index.md/log.md\n"
            "            take none (root index.md: only okf_version); log headings are\n"
            "            `## YYYY-MM-DD`, newest first, no duplicates; links must resolve\n"
            f"  warnings: missing recommended fields ({', '.join(RECOMMENDED_FIELDS)});\n"
            f"            status not in {{{', '.join(sorted(STATUS_VALUES))}}};\n"
            f"            evidence not in {{{', '.join(sorted(EVIDENCE_VALUES))}}};\n"
            "            evidence validated-runtime without a non-scan `verified.by`;\n"
            "            sources[].resource not found; stale index.md (run `reindex`)\n"
            f"Work queue ({QUEUE_DOC}) errors: duplicate task IDs; State not in\n"
            f"  {{{', '.join(TASK_STATES)}}};\n"
            "  unknown Depends/Parent IDs (archived IDs count); dependency cycles; non-integer\n"
            "  Priority; missing required fields: "
            + "; ".join(f"{state} needs {', '.join(fields)}" for state, fields in TASK_REQUIRED_FIELDS.items())
            + "\n"
            f"Archive ({ARCHIVE_DOC}) errors: a State other than DONE or CANCELLED; IDs that\n"
            "  also appear in the queue; the same required fields\n"
            "Subcommand options: okf.py COMMAND --help. Do not read this script's source."
        ),
    )
    parser.add_argument("--bundle", help="path to the OKF bundle directory")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("init", help="create the bundle skeleton (idempotent)")
    p.add_argument(
        "--autonomous", action="store_true",
        help=f"also create {QUEUE_DOC} and {STATUS_DOC} for autonomous execution",
    )
    p.set_defaults(handler=cmd_init)

    p = sub.add_parser("context", help="session start: roles, personas, knowledge docs, recent log in one call")
    p.add_argument("--log", type=int, default=5, metavar="N", help="recent log entries to show")
    p.set_defaults(handler=cmd_context)

    p = sub.add_parser("list", help="one line per concept doc: path, type, status, title")
    p.add_argument("--type", help="filter by frontmatter type (case-insensitive)")
    p.add_argument("--status", help="filter by status")
    p.add_argument("--tag", help="filter by tag")
    p.add_argument("--under", help="only docs below this directory")
    p.add_argument("--long", action="store_true", help="also print descriptions")
    p.add_argument("--json", action="store_true")
    p.set_defaults(handler=cmd_list)

    p = sub.add_parser(
        "show",
        help="print parts of a doc or any repo Markdown file, e.g. a persona (default: frontmatter + outline)",
    )
    p.add_argument(
        "paths", nargs="+", metavar="PATH",
        help="bundle docs, or any .md paths such as .ai/personas/go-principal-engineer.md (several allowed)",
    )
    p.add_argument("--meta", action="store_true", help="frontmatter only")
    p.add_argument("--outline", action="store_true", help="headings with file line numbers")
    p.add_argument("--depth", type=int, metavar="N", help="outline only headings of level <= N")
    p.add_argument("--lines", metavar="A-B", help="numbered file lines A..B (also 'A-' or 'A'), as in the outline")
    p.add_argument("--section", action="append", metavar="HEADING", help="one section's text (repeatable)")
    p.add_argument("--body", action="store_true", help="full body without frontmatter")
    p.add_argument("--json", action="store_true")
    p.set_defaults(handler=cmd_show)

    p = sub.add_parser("search", help="search bundle files (log.md excluded); prints path:line: text")
    p.add_argument("pattern")
    p.add_argument("--regex", action="store_true", help="treat pattern as a regular expression, e.g. 'parser|renderer'")
    p.add_argument("--case-sensitive", action="store_true")
    p.add_argument("--under", metavar="PATH", help="only this bundle directory or file")
    p.add_argument("--count", action="store_true", help="print match counts per file instead of lines")
    p.add_argument("--include-log", action="store_true", help="also search log.md files")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(handler=cmd_search)

    p = sub.add_parser("new", help="create a concept doc with complete frontmatter, then reindex")
    p.add_argument("path", help="e.g. capabilities/build.md")
    p.add_argument("--type", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--description", required=True)
    p.add_argument("--tags", help="comma-separated")
    p.add_argument("--status", default="draft", choices=sorted(STATUS_VALUES))
    p.add_argument("--evidence", default="project-documentation", choices=sorted(EVIDENCE_VALUES))
    p.add_argument(
        "--source",
        action="append",
        metavar="PATH[=TITLE]",
        help="repo-relative path or URL, stored doc-relative per OKF §6.2 (repeatable)",
    )
    p.add_argument("--by", default=default_actor(), help="generated.by actor (default: $OKF_ACTOR)")
    p.set_defaults(handler=cmd_new)

    p = sub.add_parser("set", help="set frontmatter fields in place (VALUE parsed as inline YAML)")
    p.add_argument("path")
    p.add_argument("assignments", nargs="+", metavar="KEY=VALUE")
    p.set_defaults(handler=cmd_set)

    p = sub.add_parser("stamp", help="set generated/verified to {by, at: now} on docs")
    p.add_argument("field", choices=("generated", "verified"))
    p.add_argument("paths", nargs="+")
    p.add_argument("--by", required=True, help="actor, e.g. 'process:make test' or 'agent/model'")
    p.add_argument("--at", help="timestamp (default: now, UTC)")
    p.set_defaults(handler=cmd_stamp)

    p = sub.add_parser("log", help="append an entry under today's date in log.md")
    p.add_argument("message", nargs="+")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.set_defaults(handler=cmd_log)

    p = sub.add_parser("reindex", help="regenerate index.md listings")
    p.add_argument("--check", action="store_true", help="exit 1 if any index is stale; write nothing")
    p.set_defaults(handler=cmd_reindex)

    p = sub.add_parser("validate", help="check OKF structure, frontmatter, links, evidence; exit 1 on errors")
    p.add_argument("--strict", action="store_true", help="treat warnings as failures")
    p.add_argument("--json", action="store_true")
    p.set_defaults(handler=cmd_validate)

    p = sub.add_parser("records", help="commit-boundary records gate: validate errors + reindex --check + git diff --check")
    p.add_argument("--base", metavar="REV", help="whitespace-check the work tree against REV (default: HEAD)")
    p.set_defaults(handler=cmd_records)

    p = sub.add_parser("affected", help="list docs whose sources cover changed files")
    p.add_argument("paths", nargs="*", help="changed repo-relative paths (default: git changes vs HEAD)")
    p.add_argument("--git", nargs="?", const="HEAD", metavar="REV", help="also include git changes vs REV")
    p.add_argument("--json", action="store_true")
    p.set_defaults(handler=cmd_affected)

    p = sub.add_parser("queue", help="work queue tasks with computed states; --next lists what to start")
    action = p.add_mutually_exclusive_group()
    action.add_argument("--next", action="store_true", help="unowned READY tasks, lowest Priority first, then queue order")
    action.add_argument("--state", help=f"only tasks in this effective state ({', '.join(TASK_STATES)}); includes archived ones")
    action.add_argument("--archive", action="store_true", help=f"move DONE and CANCELLED tasks to {ARCHIVE_DOC}")
    action.add_argument("--record-session", action="store_true",
                        help=f"interactive sessions: count one session on the active task, refusing past {SESSION_CAP}; the driver does this itself")
    p.add_argument("--limit", type=int, default=5, help="maximum rows for --next")
    p.add_argument("--json", action="store_true")
    p.set_defaults(handler=cmd_queue)

    p = sub.add_parser("checkpoint", help="check that a fresh agent could resume now; exit 1 if unsafe")
    p.add_argument("--json", action="store_true")
    p.set_defaults(handler=cmd_checkpoint)

    p = sub.add_parser("handoff", help="resume material from repository state: digest, --prompt, or --task ID")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--prompt", action="store_true", help="short resume prompt for a fresh agent")
    group.add_argument("--task", metavar="ID", help="assignment brief for a worker agent owning one task")
    p.add_argument("--role", choices=ROLES, default="solo", help="session scope stated by --prompt (default: solo)")
    p.set_defaults(handler=cmd_handoff)

    p = sub.add_parser("git-setup", help="register the bundle merge driver in git config and .gitattributes (idempotent)")
    p.set_defaults(handler=cmd_git_setup)

    p = sub.add_parser("merge-driver", help="git merge driver for log, index, queue and status files (git calls it)")
    for name in ("base", "ours", "theirs", "path"):
        p.add_argument(name)
    p.set_defaults(handler=cmd_merge_driver)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(find_bundle(args.bundle), args)
    except OkfError as error:
        print(f"okf: error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
