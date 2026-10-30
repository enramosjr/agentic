"""Run the approved broken variants in disposable local clones, never the candidate."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".ai/scripts"))
from assurance_demo import _base

VARIANTS = (
    ("oracle-inputs", "OracleTests", "return {req.id for req in reqs if set(req.reads) & set(step.change)}",
     "return {req.id for req in reqs if set(req.inputs or ()) & set(step.change)}"),
    ("missing-read", "OracleTests", "Path(name).read_text() for name in reads", "Path(name).read_text() for name in reads if Path(name).exists()"),
    ("swap-counts", "MetricTests", "\"caught\": len(truth & flagged), \"false_stale\": len(flagged - truth)",
     "\"caught\": len(flagged - truth), \"false_stale\": len(truth & flagged)"),
    ("verified-flagged", "MetricTests", "if item[\"status\"] in {\"STALE\", \"FAILED\", \"UNVERIFIED\"}",
     "if item[\"status\"] in {\"STALE\", \"FAILED\", \"UNVERIFIED\", \"VERIFIED\"}"),
    ("scoped-baseline", "MetricTests", "\"baseline_reruns\": len(items)", "\"baseline_reruns\": sum(r.inputs is not None for r in reqs)"),
    ("changed-vs-flagged", "MetricTests", "\"changed_missed\": len(truth - listed)", "\"changed_missed\": len(truth - flagged)"),
    ("no-rerun", "RerunTests", "session.lifecycle(\"assure\", \"--run\", *sorted(flagged), ok=(0, 1))", "pass"),
    ("no-status-compare", "RerunTests", "if status != expected:", "if False:"),
    ("always-zero", "ExpectationTests", "return 1 if data[\"failures\"] else 0", "return 0"),
    ("compare-only-missed", "ExpectationTests", "if row[metric] != expected:", "if metric == \"missed\" and row[metric] != expected:"),
    ("no-limit", "ReportTests", "out.write(LIMIT + \"\\n\")", "out.write(\"\\n\")"),
    ("timestamp", "ReportTests", "out.write(LIMIT + \"\\n\")", "out.write(\"2026-10-28T00:00:00Z\\n\" + LIMIT + \"\\n\")"),
    ("schema-two", "ReportTests", "\"schema_version\": 1", "\"schema_version\": 2"),
    ("avoidance-off-one", "ReportTests", "contribution[\"reruns_avoided\"] += row[\"baseline_reruns\"] - row[\"reruns\"]",
     "contribution[\"reruns_avoided\"] += row[\"baseline_reruns\"] - row[\"reruns\"] + 1"),
    ("five-scenarios", "ScenarioTests", "for scenario in SCENARIOS:", "for scenario in SCENARIOS[:-1]:"),
    ("caller-write", "ScenarioTests", "for scenario in SCENARIOS:",
     "(HERE.parents[1] / \"AGENTS.md\").write_text(\"mutated caller\")\n    for scenario in SCENARIOS:"),
    ("no-cleanup", "CleanupTests", "shutil.rmtree(directory)", "pass"),
    ("no-sigterm", "CleanupTests", "signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(143))", "pass"),
    ("bad-base-one", "CleanupTests", "        return 2", "        return 1"),
    ("mechanism-edited", "ReportOnlyTests", None, None),
    ("zero-text-counts", "ReportTests", "f\"{value:15}\" for value in counts", "f\"{0:15}\" for value in counts"),
)


def main():
    results = []
    for name, test_class, old, new in VARIANTS:
        if len(sys.argv) > 1 and name not in sys.argv[1:]:
            continue
        with tempfile.TemporaryDirectory(prefix="measure-mutant-", dir=_base()) as directory:
            clone = Path(directory) / "repo"
            subprocess.run(["git", "clone", "-q", "--shared", str(ROOT), str(clone)], check=True, capture_output=True)
            for relative in (".ai/scripts/assurance_measure.py", ".ai/scripts/tests/test_assurance_measure.py"):
                shutil.copy2(ROOT / relative, clone / relative)
            path = clone / ".ai/scripts/assurance_measure.py"
            if old is None:
                path = clone / ".ai/scripts/assurance.py"
                path.write_text(path.read_text() + "\n# deliberately changed\n")
            else:
                text = path.read_text()
                if text.count(old) != 1:
                    raise RuntimeError(f"{name}: expected exactly one mutation site, found {text.count(old)}")
                changed = text.replace(old, new)
                path.write_text(changed)
                if path.read_text() != changed or changed == text or new not in changed:
                    raise RuntimeError(f"{name}: mutation not confirmed")
            result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", ".ai/scripts/tests",
                                     "-p", "test_assurance_measure.py", "-k", test_class],
                                    cwd=clone, capture_output=True, text=True, timeout=180)
            output = result.stdout + result.stderr
            killed = result.returncode != 0 and "FAIL:" in output
            results.append({"variant": name, "class": test_class, "killed": killed, "exit": result.returncode})
            print(name, "KILLED" if killed else "SURVIVED", flush=True)
            if not killed:
                print(output, flush=True)
    suffix = "-targeted" if len(sys.argv) > 1 else ""
    (ROOT / f"docs/assurance/mutations-7{suffix}.json").write_text(json.dumps(results, indent=2) + "\n")
    return 0 if all(r["killed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
