"""Behavioral tests for repo.py. Run: python3 -m unittest discover -s .ai/scripts/tests"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import repo  # noqa: E402

FILES = {
    "app/lib/main.dart": "void main() {}\n",
    "app/lib/src/session/surfaces.dart": "// Renderer surfaces\nclass Surfaces {}\n",
    "app/android/app/src/main/kotlin/MainActivity.kt": "class MainActivity\n",
    "xtask/src/android.rs": "fn android() {}\nfn parser() {}\n",
    "build/out.dart": "generated\n",
    "assets/logo.png": "\0PNG",
}


class RepoTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root)
        for rel, text in FILES.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.env = mock.patch.dict(os.environ, {"REPO_ROOT": str(self.root), "GIT_CEILING_DIRECTORIES": str(self.root.parent)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = repo.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def lines(self, *argv: str) -> list[str]:
        code, out, err = self.run_cli(*argv)
        self.assertEqual(code, 0, err)
        return out.splitlines()


class FilesTests(RepoTestCase):
    def test_globs_under_and_depth(self) -> None:
        self.assertEqual(self.lines("files", "app/**/*.kt"), ["app/android/app/src/main/kotlin/MainActivity.kt"])
        self.assertEqual(
            self.lines("files", "*.dart", "--under", "app"),
            ["app/lib/main.dart", "app/lib/src/session/surfaces.dart"],
        )
        self.assertEqual(self.lines("files", "--under", "app/lib", "--depth", "1"), ["app/lib/main.dart"])

    def test_walk_skips_build_dirs_outside_git_and_limit_reports_rest(self) -> None:
        listed = self.lines("files", "--limit", "2")
        self.assertNotIn("build/out.dart", self.lines("files"))
        self.assertEqual(listed[-1], "... 3 more (raise --limit or narrow --under/--glob)")

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_git_respects_gitignore(self) -> None:
        (self.root / ".gitignore").write_text("xtask/\n")
        subprocess.run(["git", "-C", str(self.root), "init", "-q"], check=True)
        listed = self.lines("files")
        self.assertNotIn("xtask/src/android.rs", listed)
        self.assertIn("build/out.dart", listed)


class GrepTests(RepoTestCase):
    def test_literal_regex_glob_count_and_binary_skip(self) -> None:
        self.assertEqual(self.lines("grep", "Renderer"), ["app/lib/src/session/surfaces.dart:1: // Renderer surfaces"])
        self.assertEqual(
            self.lines("grep", "parser|Renderer", "--regex", "--glob", "*.rs"), ["xtask/src/android.rs:2: fn parser() {}"]
        )
        self.assertEqual(self.lines("grep", "fn", "--under", "xtask", "--count"), ["xtask/src/android.rs: 2"])
        self.assertEqual(self.run_cli("grep", "PNG")[2], "no matches\n")

    def test_bad_regex_is_one_line_error(self) -> None:
        code, _, err = self.run_cli("grep", "(", "--regex")
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("repo: error: bad --regex pattern"))


class ReadTests(RepoTestCase):
    def setUp(self) -> None:
        super().setUp()
        (self.root / "long.txt").write_text("".join(f"line {n}\n" for n in range(1, 11)))

    def test_ranges_are_numbered_and_inclusive(self) -> None:
        self.assertEqual(self.lines("read", "long.txt", "--lines", "3-4"), ["     3\tline 3", "     4\tline 4"])
        self.assertEqual(self.lines("read", "long.txt", "--lines", "10"), ["    10\tline 10"])
        self.assertEqual(self.lines("read", "long.txt", "--lines", "9-")[-1], "    10\tline 10")
        self.assertEqual(self.lines("read", str(self.root / "xtask/src/android.rs")), ["     1\tfn android() {}", "     2\tfn parser() {}"])

    def test_limit_bounds_output_and_names_the_next_range(self) -> None:
        out = self.lines("read", "long.txt", "--lines", "2-9", "--limit", "3")
        self.assertEqual(out[:3], ["     2\tline 2", "     3\tline 3", "     4\tline 4"])
        self.assertEqual(out[3], "... lines 5-9 not shown (of 10); continue with --lines 5-9")
        self.assertEqual(len(self.lines("read", "long.txt", "--limit", "10")), 10)

    def test_errors_are_one_line(self) -> None:
        for argv, message in (
            (("read", "missing.txt"), "no file at missing.txt"),
            (("read", "assets/logo.png"), "is binary"),
            (("read", "long.txt", "--lines", "5-2"), "end 2 is before start 5"),
            (("read", "long.txt", "--lines", "0"), "--lines must look like"),
            (("read", "long.txt", "--lines", "11"), "has 10 line(s); --lines starts at 11"),
        ):
            code, out, err = self.run_cli(*argv)
            self.assertEqual((code, out), (1, ""), argv)
            self.assertIn(message, err)
            self.assertTrue(err.startswith("repo: error: "))


if __name__ == "__main__":
    unittest.main()
