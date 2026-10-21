"""Black-box harness for the cloudbill hidden tests.

The tool under test is run as ``python -m <package> ...`` in a subprocess, with the workspace on
PYTHONPATH and a scratch directory as the working directory. Nothing here imports the workspace's code.
The package name comes from the task's ``task_config.json`` one directory up. Expected answers come
from ``billing_gen``'s oracle, computed from the generated records rather than from the CSV text.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import billing_gen as g  # noqa: E402

CONFIG = json.loads((HERE.parent / "task_config.json").read_text(encoding="utf-8"))
PACKAGE = CONFIG["package"]
WORKSPACE = Path(os.environ.get("EVAL_WORKSPACE") or os.environ.get("LEDGER_WORKSPACE") or "/app")
RUN_TIMEOUT = 120


def tool_env() -> dict:
    env = dict(os.environ, PYTHONPATH=str(WORKSPACE), PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    return env


QUESTIONS = {"costs", "daily", "top", "untagged", "credits", "mom", "daily-stats", "rejects"}
# "database" (cloudbill-sqlite): every question below is answered from a database loaded from the same
# files (`load --db`, then the question with `--db`), so this suite is the database's correctness oracle.
ANSWER_FROM = CONFIG.get("hidden_answers_from", "files")
_DATABASES: dict[tuple, Path] = {}


def _raw(args, cwd: Path, timeout: float) -> tuple[int, str, str]:
    try:
        proc = subprocess.run([sys.executable, "-m", PACKAGE, *args], cwd=cwd, env=tool_env(),
                              capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        pytest.fail(f"{PACKAGE} {' '.join(args)} did not finish in {timeout} s")
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


def run_tool(args, cwd: Path, timeout: float = RUN_TIMEOUT, answer_from: str | None = None) -> tuple[int, str, str]:
    args = [str(a) for a in args]
    files = [a for a in args[1:] if a.endswith(".csv")]  # every export in these tests is a .csv
    if (answer_from or ANSWER_FROM) != "database" or not args or args[0] not in QUESTIONS or not files:
        return _raw(args, cwd, timeout)
    key = tuple((f, *((Path(cwd, f).stat().st_size, Path(cwd, f).stat().st_mtime_ns) if Path(cwd, f).exists() else ())) for f in files)
    store = _DATABASES.get(key)
    if store is None:
        store = Path(tempfile.mkdtemp(prefix="answers-")) / "bill.db"
        loaded = _raw(["load", "--db", str(store), *files], cwd, timeout)
        if loaded[0] != 0:
            return loaded
        _DATABASES[key] = store
    return _raw([a for a in args if a not in files] + ["--db", str(store)], cwd, timeout)


@pytest.fixture
def cli(tmp_path: Path):
    def _run(*args, timeout: float = RUN_TIMEOUT):
        return run_tool(args, tmp_path, timeout)
    return _run


@pytest.fixture
def cli_files(tmp_path: Path):
    """Always straight from the files, whatever ``hidden_answers_from`` says."""
    def _run(*args, timeout: float = RUN_TIMEOUT):
        return run_tool(args, tmp_path, timeout, answer_from="files")
    return _run


def _json_runner(run):
    def _run(*args):
        code, out, err = run(*args, "--format", "json")
        assert code == 0, f"exit {code}: {err[-800:]}"
        try:
            doc = json.loads(out)
        except json.JSONDecodeError as exc:
            pytest.fail(f"--format json did not print JSON ({exc}): {out[:300]!r}")
        assert isinstance(doc, dict) and isinstance(doc.get("rows"), list), f"expected an object with rows: {out[:300]!r}"
        return doc
    return _run


@pytest.fixture
def cli_files_json(cli_files):
    return _json_runner(cli_files)


@pytest.fixture
def cli_json(cli):
    return _json_runner(cli)


# ---- values -----------------------------------------------------------------------------------

def num(value) -> Decimal | None:
    """A number from JSON or CSV: a number, or a string a person would read as one."""
    if value is None or isinstance(value, bool):
        return None
    s = str(value).strip().replace(",", "").replace("$", "").rstrip("%")
    if s == "":
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        pytest.fail(f"not a number: {value!r}")


def close(actual, expected, tol: Decimal = Decimal("0.01")) -> bool:
    a = num(actual)
    return a is not None and abs(a - Decimal(expected)) <= tol


def norm(key, by: str = "account"):
    """Group keys compared the way the brief defines them: services case-insensitively."""
    if key is None:
        return None
    k = str(key).strip()
    if k == "":
        return None
    return k.lower() if by == "service" else k


def by_key(rows: list[dict], by: str = "account", field: str = "key") -> dict:
    out: dict = {}
    for r in rows:
        k = norm(r.get(field), by)
        assert k not in out, f"two rows for {k!r}"
        out[k] = r
    return out


def csv_rows(text: str) -> list[dict]:
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    return list(csv.DictReader(io.StringIO("\n".join(lines))))


def mentions_rejected(text: str, n: int) -> bool:
    """The output reports n rejected rows: a line that says 'reject...' and the number, or a column named
    for rejects carrying it."""
    pattern = re.compile(rf"(?<![\d.]){n}(?![\d.])")
    if any("reject" in ln.lower() and pattern.search(ln) for ln in text.splitlines()):
        return True
    try:
        for row in csv.DictReader(io.StringIO(text)):
            if any(k and "reject" in k.lower() and str(v).strip() == str(n) for k, v in row.items()):
                return True
    except csv.Error:
        pass
    return False


# ---- a scenario with every rule in it -----------------------------------------------------------

A, B, C = "012000000001", "300000000002", "450000000003"
T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)


def build_scenario() -> list[g.Export]:
    """Two exports. August: complete, with a byte-order mark and CRLF lines; September: up to the 10th,
    another column order and no cost-center column. Every rule of the brief is exercised once at least."""
    g._ids["n"] = 4242
    aug: list[g.Item] = []
    sep: list[g.Item] = []
    for d in range(41):
        start = T0 + timedelta(days=d)
        target = aug if d < 31 else sep
        target.append(g.Item(g.new_id(), A, "Compute Engine", start, g.money(10 + d % 7 * 1.5), account_name="payments",
                             resource_id="vm-a1", tags={"team": "payments", "env": "prod", "cost-center": "CC-1"},
                             description="Instance hours, m6.large"))
        target.append(g.Item(g.new_id(), A, "object storage " if d % 2 else "Object Storage", start, g.money(2 + d % 3),
                             account_name="payments", resource_id="bucket-a", usage_unit="GB-Mo",
                             tags={"team": "", "env": "prod", "cost-center": "CC-1"}, description="Storage, standard tier"))
        cost = g.money(1000 + d * 37.25)
        target.append(g.Item(g.new_id(), B, "Managed Database", start, cost, account_name="warehouse" if d < 35 else "warehouse-prod",
                             resource_id="db-b1", cost_text=f" {cost:,.4f} ",
                             tags={"team": "data ", "env": "prod", "cost-center": "CC-2"}, description="DB hours, \"r6.16xlarge\""))
        target.append(g.Item(g.new_id(), C, "MONITORING", start, "0", account_name="sandbox", resource_id="mon-c",
                             tags={"team": "platform"}, description="Free tier"))
        # an hourly line in the evening UTC: still that UTC day, the previous day in local time
        late = start + timedelta(hours=2)
        target.append(g.Item(g.new_id(), C, "Data Transfer", late, g.money(0.5 + d % 5), end=late + timedelta(hours=1),
                             account_name="sandbox", resource_id="lb-c", usage_unit="GB", tags={"team": "platform"},
                             description="Data transfer out\nto the internet"))
    month = dict(start=T0, end=T0 + timedelta(days=31), last_updated=T0 + timedelta(days=31, hours=6), region="")
    aug += [
        g.Item(g.new_id(), A, "Tax", line_item_type="Tax", cost="31.2000", **month),
        g.Item(g.new_id(), B, "Support", line_item_type="Fee", cost="1250.0000", cost_text="1,250.0000", **month),
        g.Item(g.new_id(), A, "Compute Engine", line_item_type="Credit", cost="-40.0000", description='Promotional credit "pilot"', **month),
        g.Item(g.new_id(), A, "Managed Database", line_item_type="Refund", cost="-12.5000",
               description="Refund for incident:\ndatabase unavailable,\nSLA 4.2", **month),
        g.Item(g.new_id(), B, "Managed Database", line_item_type="Credit", cost="-300.0000", **month),
    ]
    # restatements: one after the original, one before it, one across files
    orig = aug[10]
    aug.append(g.Item(orig.line_item_id, orig.account_id, orig.service, orig.start, "3.3300", account_name=orig.account_name,
                      resource_id=orig.resource_id, tags=dict(orig.tags), last_updated=orig.last_updated + timedelta(days=9)))
    early = aug[20]
    aug.insert(3, g.Item(early.line_item_id, early.account_id, early.service, early.start, "999.0000", account_name=early.account_name,
                         resource_id=early.resource_id, tags=dict(early.tags), last_updated=early.last_updated + timedelta(days=12),
                         description="Instance hours (restated)"))
    cross = aug[40]
    sep.insert(5, g.Item(cross.line_item_id, cross.account_id, cross.service, cross.start, "77.7700", account_name=cross.account_name,
                         resource_id=cross.resource_id, tags=dict(cross.tags), last_updated=cross.last_updated + timedelta(days=30),
                         billing_period=cross.start.strftime("%Y-%m"), description="corrected in September"))
    # rejected rows
    aug.insert(8, g.Item(g.new_id(), A, "Compute Engine", T0, "5", description="hand edited, row", bad="long"))
    aug.insert(15, g.Item(g.new_id(), B, "Managed Database", T0, "5", bad="cost"))
    aug.insert(30, g.Item(g.new_id(), A, "Compute Engine", T0, "5", currency="EUR"))
    aug.insert(44, g.Item(g.new_id(), A, "Compute Engine", T0, "5", bad="id"))
    aug.insert(52, g.Item(g.new_id(), B, "Managed Database", T0 + timedelta(days=2), "5", bad="kind"))
    sep.insert(9, g.Item(g.new_id(), C, "Data Transfer", T0 + timedelta(days=33), "5", bad="start"))
    sep.append(g.Item(g.new_id(), C, "Data Transfer", T0 + timedelta(days=40), "5",
                      description="multi\nline and cut short", tags={"team": "x", "env": "y"}, bad="short"))
    sep_cols = [c for c in g.COLUMNS if c not in ("tag:cost-center", "description", "unblended_cost")]
    sep_cols.insert(2, "unblended_cost")
    sep_cols.insert(sep_cols.index("tag:team"), "description")
    return [g.Export(aug, bom=True, newline="\r\n"), g.Export(sep, columns=sep_cols)]


@pytest.fixture(scope="session")
def scenario(tmp_path_factory) -> tuple[list[g.Export], list[Path]]:
    d = tmp_path_factory.mktemp("scenario")
    exports = build_scenario()
    paths = [exports[0].write(d / "billing-2026-08.csv"), exports[1].write(d / "billing-2026-09.csv")]
    return exports, paths


@pytest.fixture(scope="session")
def sample(tmp_path_factory) -> tuple[list[g.Export], list[Path]]:
    written = g.write_sample(tmp_path_factory.mktemp("sample"))
    return [ex for _, ex in written], [p for p, _ in written]


# ---- the large export and peak-memory measurement ----------------------------------------------

CAP_MB = 100  # the brief: peak memory under 100 MB however big the input
# About 380 MB of export. Measured here: the streaming reference peaks at about 36 MB (load 27 MB, a
# question from the database 25 MB); a design that keeps anything per line item id does not pass, from a
# bare set of ids (183 MB) or an int per id (195 MB) to an id-to-last_updated map (270 MB) and an
# id-to-(last_updated, cost) map (419 MB). At 600,000 rows the id-to-last_updated map sat at 98 MB,
# inside the cap by less than the difference between two interpreters.
LARGE_ROWS = 1_500_000

# Runs the tool as its only child, so RUSAGE_CHILDREN is the tool's own peak resident set (KiB on Linux).
MEASURE = """
import resource, subprocess, sys
proc = subprocess.run(sys.argv[2:], stdout=open(sys.argv[1], "wb"), stderr=subprocess.PIPE)
sys.stderr.buffer.write(proc.stderr[-2000:])
print(proc.returncode, resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
"""


@pytest.fixture(scope="session")
def large(tmp_path_factory):
    path = tmp_path_factory.mktemp("large") / "export-large.csv"
    return path, g.write_large(path, rows=LARGE_ROWS)


# One pass over the large export may take this long. It is well under the grader's budget for the whole
# suite (hidden_timeout_sec in task_config.json), so a slow tool fails the large-export test and keeps
# every other result, instead of timing out the suite and scoring nothing.
MEASURE_TIMEOUT = 240


def measured(cwd: Path, *args) -> tuple[int, float, str, str]:
    """(exit code, peak RSS in MB, stdout, stderr) of one run of the tool."""
    out = Path(cwd) / "measured-stdout"
    cmd = [sys.executable, "-c", MEASURE, str(out), sys.executable, "-m", PACKAGE, *map(str, args)]
    try:
        proc = subprocess.run(cmd, cwd=cwd, env=tool_env(), capture_output=True, text=True, timeout=MEASURE_TIMEOUT)
    except subprocess.TimeoutExpired:
        pytest.fail(f"{PACKAGE} {' '.join(map(str, args))} did not finish in {MEASURE_TIMEOUT} s on the {LARGE_ROWS}-row export")
    try:
        code, rss_kib = (int(x) for x in proc.stdout.split())
    except ValueError:
        pytest.fail(f"the measuring process did not report a result: {proc.stderr[-800:]}")
    return code, rss_kib / 1024, out.read_text(encoding="utf-8", errors="replace"), proc.stderr
