#!/usr/bin/env python3
"""Select conservative feedback checks, never replace a required integrated gate."""
import argparse
import json
from pathlib import Path
import subprocess


STRUCTURE = [["python3", ".ai/scripts/okf.py", "validate", "--strict"],
             ["python3", ".ai/scripts/okf.py", "reindex", "--check"], ["git", "diff", "--check"]]
GOVERNANCE = ["python3", "-m", "unittest", "discover", "-s", ".ai/scripts/tests"]
CARGO_FULL = [["cargo", "build", "--workspace", "--all-targets", "--offline", "--locked"],
              ["cargo", "test", "--workspace", "--offline", "--locked"],
              ["cargo", "clippy", "--workspace", "--all-targets", "--offline", "--locked", "--", "-D", "warnings"],
              ["cargo", "fmt", "--all", "--", "--check"]]


def full_commands(packages):
    return [*(CARGO_FULL if packages else []), GOVERNANCE, *STRUCTURE]


def select(paths, packages, full=False, core=()):
    """Package metadata supplies actual reverse dependency edges; unknowns widen."""
    product = []
    tooling = False
    for name in paths:
        path = Path(name)
        if name.startswith(".ai/scripts/"):
            tooling = True
        elif (name.startswith(("knowledge/", ".ai/")) and path.suffix == ".md") or name == "AGENTS.md":
            continue
        else:
            product.append(name)
    affected = set()
    for name in product:
        matches = [p["name"] for p in packages if name.startswith(p["directory"] + "/")]
        if len(matches) != 1:
            full = True
        affected.update(matches)
    changed = True
    while changed:
        changed = False
        for package in packages:
            if package["name"] not in affected and affected.intersection(package["dependencies"]):
                affected.add(package["name"])
                changed = True
    full = full or bool(affected.intersection(core))
    if full:
        commands = full_commands(packages)
    else:
        commands = []
        if affected:
            options = [arg for name in sorted(affected) for arg in ("-p", name)]
            commands = [["cargo", "build", *options, "--all-targets", "--offline", "--locked"],
                        ["cargo", "test", *options, "--offline", "--locked"],
                        ["cargo", "clippy", *options, "--all-targets", "--offline", "--locked", "--", "-D", "warnings"],
                        ["cargo", "fmt", "--all", "--", "--check"]]
        if tooling:
            commands.append(GOVERNANCE)
        commands.extend(STRUCTURE)
    return {"kind": "feedback-checks", "broad_baseline": full, "affected_packages": sorted(affected),
            "commands": commands,
            "notice": "Feedback only. Preserve task-specific acceptance, installed-package checks and required integrated/milestone gates; this output is not a validation submission."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="reviewed baseline Git ref")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--core", action="append", default=[], metavar="PACKAGE",
                        help="shared package whose change selects the broad baseline (repeatable)")
    args = parser.parse_args()
    try:
        root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
        def git(*argv):
            return subprocess.check_output(["git", *argv], cwd=root)
        paths = set(git("diff", "--no-renames", "--name-only", "-z", args.base, "--").decode().rstrip("\0").split("\0"))
        paths.update(git("ls-files", "--others", "--exclude-standard", "-z").decode().rstrip("\0").split("\0"))
        paths.discard("")
        packages = []
        if (root / "Cargo.toml").is_file():
            metadata = json.loads(subprocess.check_output(["cargo", "metadata", "--format-version", "1", "--no-deps", "--offline", "--locked"], cwd=root))
            members = set(metadata["workspace_members"])
            packages = [{"name": p["name"], "directory": str(Path(p["manifest_path"]).parent.relative_to(root)),
                         "dependencies": [d["name"] for d in p["dependencies"]]} for p in metadata["packages"] if p["id"] in members]
        result = select(sorted(paths), packages, args.full, args.core)
        result["changed_paths"] = sorted(paths)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"validation-select: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
