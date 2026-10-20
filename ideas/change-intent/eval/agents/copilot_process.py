"""Harbor agents that run a *process version* through the Copilot SDK.

Each class below is one condition in the experiment. Harbor installs the Copilot CLI and the SDK
in the task container, uploads the eval driver and the process directory, and runs
``driver/run_process.py``. Everything the driver leaves in ``/app/.eval`` is available to the
verifier; the SDK events are also copied into Harbor's agent logs directory.

Run from the eval/ directory, with Docker, a Copilot-entitled token in COPILOT_GITHUB_TOKEN, and
EVAL_REVIEWER_MODEL set to a model from another vendor (the driver refuses a same-model reviewer
otherwise). Harbor imports `module:Class` with importlib and does not add the current directory to
sys.path, so PYTHONPATH=. is required:

    export COPILOT_GITHUB_TOKEN=... EVAL_REVIEWER_MODEL=claude-sonnet-4.5
    PYTHONPATH=. harbor run -p tasks/ledger-budgets -a agents.copilot_process:ChangeIntentV1 -m gpt-5.4 -k 3
    PYTHONPATH=. harbor run -p tasks/ledger-budgets -a agents.copilot_process:Baseline        -m gpt-5.4 -k 3

Optional environment forwarded to the driver: EVAL_CAP_AUTHOR, EVAL_CAP_IMPLEMENT, EVAL_CAP_REVIEW,
EVAL_CAP_FIXED_REVIEW (seconds), EVAL_STAND_IN_MODEL, EVAL_ALLOW_SAME_REVIEWER=1.

Add a process version by generating or copying a directory under processes/ and adding a
two-line subclass that names it.
"""

from __future__ import annotations

import json
import os
import shlex
from pathlib import Path

from harbor.agents.installed.copilot_cli import CopilotCli
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

EVAL_ROOT = Path(__file__).resolve().parents[1]  # .../eval
REMOTE_EVAL = "/eval"
REMOTE_BRIEF = "/eval/brief.md"
REMOTE_OUT = "/app/.eval"


class CopilotProcessAgent(CopilotCli):
    """Base class: Copilot CLI install from Harbor's own agent, plus the SDK and our driver."""

    PROCESS: str = ""  # name of a directory under eval/processes/
    STAND_IN: str = "scripted"

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
        # Same precedence Harbor's own Copilot agent uses; written out so it works across Harbor versions.
        token = os.environ.get("COPILOT_GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        env: dict[str, str] = {"COPILOT_GITHUB_TOKEN": token} if token else {}
        connection = getattr(self, "model_connection", None)  # newer Harbor: BYOK env resolved from -m
        if connection is not None and getattr(connection, "env", None):
            env.update(connection.env)
        for key in ("COPILOT_PROVIDER_TYPE", "COPILOT_PROVIDER_BASE_URL", "COPILOT_PROVIDER_API_KEY", "COPILOT_PROVIDER_WIRE_API",
                    "EVAL_REVIEWER_MODEL", "EVAL_STAND_IN_MODEL", "EVAL_CAP_AUTHOR", "EVAL_CAP_IMPLEMENT", "EVAL_CAP_REVIEW",
                    "EVAL_CAP_FIXED_REVIEW"):
            if key in os.environ and key not in env:
                env[key] = os.environ[key]

        await self._upload_tree(environment, EVAL_ROOT / "driver", f"{REMOTE_EVAL}/driver")
        await self._upload_tree(environment, EVAL_ROOT / "processes" / self.PROCESS, f"{REMOTE_EVAL}/processes/{self.PROCESS}")
        await self._upload_tree(environment, EVAL_ROOT / "reviewer", f"{REMOTE_EVAL}/reviewer")
        await self._upload_config_text(environment, content=instruction, remote_path=REMOTE_BRIEF, filename="brief.md")

        model_flag = ""
        if self.model_name:
            # Copilot uses bare model ids; strip a Harbor-style provider prefix ("openai/gpt-5.4" -> "gpt-5.4").
            model_flag = f"--model {shlex.quote(self.model_name.rsplit('/', 1)[-1])}"
        provider_flag = ""
        if env.get("COPILOT_PROVIDER_BASE_URL"):
            provider = {
                "type": env.get("COPILOT_PROVIDER_TYPE", "openai"),
                "base_url": env["COPILOT_PROVIDER_BASE_URL"],
                "api_key": env.get("COPILOT_PROVIDER_API_KEY"),
            }
            if env.get("COPILOT_PROVIDER_WIRE_API"):
                provider["wire_api"] = env["COPILOT_PROVIDER_WIRE_API"]
            provider_flag = f"--provider-json {shlex.quote(json.dumps(provider))}"

        same_reviewer_flag = "--allow-same-reviewer" if os.environ.get("EVAL_ALLOW_SAME_REVIEWER") == "1" else ""
        # One shell command: run the driver, then ALWAYS copy artifacts next to Harbor's agent logs, then
        # exit with the driver's code (Harbor raises on non-zero and would otherwise skip the copy).
        await self.exec_as_agent(
            environment,
            command=(
                'export PATH="$HOME/.local/bin:$PATH"; mkdir -p /logs/agent/eval; cd /app && '
                f"python3 {REMOTE_EVAL}/driver/run_process.py --workspace /app "
                f"--process {REMOTE_EVAL}/processes/{self.PROCESS} --brief {REMOTE_BRIEF} --out {REMOTE_OUT} "
                f"--work-dir /logs/agent/eval-work --backend copilot --stand-in {self.STAND_IN} {model_flag} {provider_flag} "
                f"{same_reviewer_flag} > /logs/agent/driver.log 2>&1; rc=$?; "
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


class ChangeIntentV1ModelAuthor(ChangeIntentV1):
    """Same process, but the stand-in author is a pinned model answering in character."""

    STAND_IN = "model"

    @staticmethod
    def name() -> str:
        return "copilot-process-change-intent-v1-model-author"
