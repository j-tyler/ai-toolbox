"""Harbor agents that run a *process version* through the Copilot SDK.

Each class below is one condition in the experiment. Harbor installs the Copilot CLI and the SDK
in the task container, uploads the eval driver and the process directory, and runs
``driver/run_process.py``. Everything the driver leaves in ``/app/.eval`` is available to the
verifier; the SDK events are also copied into Harbor's agent logs directory.

Run from the eval/ directory, with Docker, a Copilot-entitled token in COPILOT_GITHUB_TOKEN, and
EVAL_REVIEWER_MODEL set to a model from another vendor (the driver refuses a same-model reviewer
otherwise). Harbor imports `module:Class` with importlib and does not add the current directory to
sys.path, so PYTHONPATH=. is required:

    export COPILOT_GITHUB_TOKEN=... EVAL_REVIEWER_MODEL=<reviewer model from another vendor>
    # plumbing pilot, one arm (k=3 cannot show a difference: the minimum permutation p is 0.10)
    PYTHONPATH=. harbor run -p tasks/ledger-budgets -a agents.copilot_process:Baseline -m <model> -k 3

    # a comparison: every arm in ONE job so trials interleave (Harbor nests agents innermost in its plan),
    # rather than one arm per run where server-side drift between runs would be confounded with the arm
    cat > job.yaml <<'YAML'
    agents:
      - import_path: agents.copilot_process:Baseline
        model_name: <model>
      - import_path: agents.copilot_process:ChangeIntentV1
        model_name: <model>
    datasets:
      - path: tasks/ledger-budgets    # one entry per task; the agent finds each trial's task itself
      - path: tasks/cloudbill-report
      - path: tasks/cloudbill-sqlite
    n_attempts: 20
    YAML
    PYTHONPATH=. harbor run -c job.yaml

Run order: a baseline pilot at k of about 5 first. If its mean correctness is at least 0.95 (or the
all-pass rate at least 0.9) the task cannot discriminate on the primary endpoint; add a task or a
lighter-brief variant before spending on the full run.

Optional environment forwarded to the driver: EVAL_CAP_AUTHOR, EVAL_CAP_IMPLEMENT, EVAL_CAP_REVIEW,
EVAL_CAP_FIXED_REVIEW (seconds), EVAL_STAND_IN_MODEL, EVAL_ALLOW_SAME_REVIEWER=1.

Add a process version by generating or copying a directory under processes/ and adding a
two-line subclass that names it.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

from harbor.agents.installed.copilot_cli import CopilotCli
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from .task_select import resolve_task, task_config_path

EVAL_ROOT = Path(__file__).resolve().parents[1]  # .../eval
REMOTE_EVAL = "/eval"
REMOTE_BRIEF = "/eval/brief.md"
REMOTE_TASK_CONFIG = "/eval/task_config.json"  # next to the driver, never inside the workspace
REMOTE_OUT = "/app/.eval"


class CopilotProcessAgent(CopilotCli):
    """Base class: Copilot CLI install from Harbor's own agent, plus the SDK and our driver.

    The task is the class's TASK, else EVAL_TASK in the host environment, else the one task whose
    instruction.md the trial's instruction contains (agents/task_select.py). Its task_config.json is
    uploaded next to the driver, so one class serves every task and one job can mix tasks; pin a task
    with a subclass (``class BaselineReport(Baseline): TASK = "cloudbill-report"``) if you prefer."""

    PROCESS: str = ""  # name of a directory under eval/processes/
    TASK: str | None = None  # name of a directory under eval/tasks/; None: EVAL_TASK, else matched from the instruction
    STAND_IN: str = "scripted"
    FROZEN_INTENT: str | None = None  # local path to an intent file for author.mode = frozen
    REMOTE_INTENT: str | None = None
    DRIVER_BUDGET_SEC: int = 9600  # caps 1800+3600+900+3x900 = 9000 plus overhead; task.toml agent timeout is 10500

    @staticmethod
    def name() -> str:
        return "copilot-process"

    SDK_PIN = "github-copilot-sdk==1.0.23"

    async def install(self, environment: BaseEnvironment) -> None:
        # Harbor's Copilot CLI install is kept so `copilot` exists for debugging in the container; the
        # driver itself talks to the SDK's bundled runtime, which is pre-downloaded here so the first
        # stage does not spend its time budget on it.
        await super().install(environment)
        await self.exec_as_root(
            environment,
            command=(
                f"python3 -m pip install --no-cache-dir --break-system-packages '{self.SDK_PIN}' "
                f"|| pip install --no-cache-dir '{self.SDK_PIN}'"
            ),
        )
        await self.exec_as_agent(environment, command="python3 -m copilot download-runtime || true")

    async def _upload_tree(self, environment: BaseEnvironment, local: Path, remote: str) -> None:
        await self.exec_as_root(environment, command=f"mkdir -p {shlex.quote(remote)}")
        for path in sorted(local.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts:
                continue
            target = f"{remote}/{path.relative_to(local).as_posix()}"
            await self.exec_as_root(environment, command=f"mkdir -p {shlex.quote(str(Path(target).parent))}")
            await environment.upload_file(path, target)
        if environment.default_user is not None:
            await self.exec_as_root(environment, command=f"chown -R {shlex.quote(str(environment.default_user))} {shlex.quote(remote)}")

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        if not self.PROCESS:
            raise ValueError("subclass must set PROCESS")
        task = resolve_task(instruction, self.TASK or os.environ.get("EVAL_TASK"))  # refuses a mismatch
        # Same precedence Harbor's own Copilot agent uses; written out so it works across Harbor versions.
        token = os.environ.get("COPILOT_GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        env: dict[str, str] = {"COPILOT_GITHUB_TOKEN": token} if token else {}
        connection = getattr(self, "model_connection", None)  # newer Harbor: BYOK env resolved from -m
        if connection is not None and getattr(connection, "env", None):
            env.update(connection.env)
        for key in ("COPILOT_PROVIDER_TYPE", "COPILOT_PROVIDER_BASE_URL", "COPILOT_PROVIDER_API_KEY", "COPILOT_PROVIDER_WIRE_API",
                    "EVAL_REVIEWER_MODEL", "EVAL_STAND_IN_MODEL", "EVAL_CAP_AUTHOR", "EVAL_CAP_IMPLEMENT", "EVAL_CAP_REVIEW",
                    "EVAL_CAP_FIXED_REVIEW", "EVAL_LABELS"):
            if key in os.environ and key not in env:
                env[key] = os.environ[key]
        # Provenance computed on the host, where the harness checkout is; the container has no .git.
        try:
            env["EVAL_HARNESS_SHA"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=EVAL_ROOT, text=True, capture_output=True).stdout.strip()
            env["EVAL_HARNESS_DIRTY"] = "1" if subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=EVAL_ROOT, text=True, capture_output=True).stdout.strip() else "0"
        except Exception:
            pass

        await self._upload_tree(environment, EVAL_ROOT / "driver", f"{REMOTE_EVAL}/driver")
        await self._upload_tree(environment, EVAL_ROOT / "processes" / self.PROCESS, f"{REMOTE_EVAL}/processes/{self.PROCESS}")
        await self._upload_tree(environment, EVAL_ROOT / "reviewer", f"{REMOTE_EVAL}/reviewer")
        await environment.upload_file(task_config_path(task), REMOTE_TASK_CONFIG)
        frozen = self.FROZEN_INTENT or os.environ.get("EVAL_INTENT_FILE")  # HOST environment, read at run time
        process_cfg = json.loads((EVAL_ROOT / "processes" / self.PROCESS / "process.json").read_text(encoding="utf-8"))
        if process_cfg.get("author", {}).get("mode") == "frozen" or frozen:
            if not frozen or not Path(frozen).expanduser().is_file():
                raise FileNotFoundError(
                    f"process {self.PROCESS} needs a frozen intent: export EVAL_INTENT_FILE=/path/to/intent.md on the host "
                    f"(not --ae, which only reaches the container) or set FROZEN_INTENT on the agent class; got {frozen!r}"
                )
            src = Path(frozen).expanduser().resolve()
            self.REMOTE_INTENT = f"{REMOTE_EVAL}/intent/{src.name}"
            await self.exec_as_root(environment, command=f"mkdir -p {REMOTE_EVAL}/intent")
            await environment.upload_file(src, self.REMOTE_INTENT)
        await self._upload_config_text(environment, content=instruction, remote_path=REMOTE_BRIEF, filename="brief.md")

        model_flag = ""
        if self.model_name:
            # Copilot uses bare model ids; strip a Harbor-style provider prefix ("vendor/name" -> "name").
            model_flag = f"--model {shlex.quote(self.model_name.rsplit('/', 1)[-1])}"
        provider_flag = ""  # providers travel in the environment, never on the command line (the key would land in logs)
        if env.get("COPILOT_PROVIDER_BASE_URL") and "EVAL_PROVIDER_JSON" not in env:
            provider = {
                "type": env.get("COPILOT_PROVIDER_TYPE", "openai"),
                "base_url": env["COPILOT_PROVIDER_BASE_URL"],
                "api_key": env.get("COPILOT_PROVIDER_API_KEY"),
            }
            if env.get("COPILOT_PROVIDER_WIRE_API"):
                provider["wire_api"] = env["COPILOT_PROVIDER_WIRE_API"]
            env["EVAL_PROVIDER_JSON"] = json.dumps(provider)
        for key in ("EVAL_PROVIDER_JSON", "EVAL_REVIEWER_PROVIDER_JSON", "EVAL_STAND_IN_PROVIDER_JSON"):
            if key in os.environ and key not in env:
                env[key] = os.environ[key]

        same_reviewer_flag = "--allow-same-reviewer" if os.environ.get("EVAL_ALLOW_SAME_REVIEWER") == "1" else ""
        intent_flag = f"--intent-file {shlex.quote(self.REMOTE_INTENT)}" if self.REMOTE_INTENT else ""
        # One shell command: run the driver with an absolute deadline inside Harbor's agent timeout
        # (task.toml: 9000 s; driver budget 7800 s leaves margin for start-up, abort, git, and the copy),
        # then ALWAYS copy artifacts next to Harbor's agent logs, then exit with the driver's code.
        await self.exec_as_agent(
            environment,
            command=(
                'export PATH="$HOME/.local/bin:$PATH"; mkdir -p /logs/agent/eval; start=$(date +%s); cd /app && '
                f"timeout --kill-after=60 {self.DRIVER_BUDGET_SEC + 600} "
                f"python3 {REMOTE_EVAL}/driver/run_process.py --workspace /app "
                f"--process {REMOTE_EVAL}/processes/{self.PROCESS} --task-config {REMOTE_TASK_CONFIG} "
                f"--brief {REMOTE_BRIEF} --out {REMOTE_OUT} "
                f"--work-dir /logs/agent/eval-work --backend copilot --stand-in {self.STAND_IN} {model_flag} {provider_flag} "
                f"{same_reviewer_flag} {intent_flag} --deadline-epoch $((start + {self.DRIVER_BUDGET_SEC})) "
                f"> /logs/agent/driver.log 2>&1; rc=$?; "
                f"cp -r {REMOTE_OUT}/. /logs/agent/eval/ 2>/dev/null; exit $rc"
            ),
            env=env,
        )

    def populate_context_post_run(self, context: AgentContext) -> None:
        summary = self.logs_dir / "eval" / "summary.json"
        if not summary.exists():
            return
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        n_in = n_out = 0
        for stage in data.get("stages", {}).values():
            usage = stage.get("usage") or {}
            for k, v in usage.items():
                if not isinstance(v, int):
                    continue
                if "input" in k or "prompt" in k:
                    n_in += v
                elif "output" in k or "completion" in k:
                    n_out += v
        if n_in:
            context.n_input_tokens = n_in
        if n_out:
            context.n_output_tokens = n_out


class Baseline(CopilotProcessAgent):
    PROCESS = "baseline"

    @staticmethod
    def name() -> str:
        return "copilot-process-baseline"


class ChangeIntentV1(CopilotProcessAgent):
    PROCESS = "change-intent-v1"

    @staticmethod
    def name() -> str:
        return "copilot-process-change-intent-v1"


class ChangeIntentV1Frozen(CopilotProcessAgent):
    """change-intent-v1 guidance with a pre-authored intent. Export EVAL_INTENT_FILE=/path on the HOST before
    `harbor run` (Harbor's --ae only reaches the container), or subclass with FROZEN_INTENT set; the file is
    uploaded into the container and passed as --intent-file. The run refuses to start without it."""

    PROCESS = "change-intent-v1-frozen"
    # The file comes from EVAL_INTENT_FILE in the HOST environment at run time (see run()).

    @staticmethod
    def name() -> str:
        return "copilot-process-change-intent-v1-frozen"


class ChangeIntentV1ModelAuthor(ChangeIntentV1):
    """Same process, but the stand-in author is a pinned model answering in character."""

    STAND_IN = "model"

    @staticmethod
    def name() -> str:
        return "copilot-process-change-intent-v1-model-author"
