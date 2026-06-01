"""
Wraps terraform commands as subprocess calls.
Parses output to extract per-site deployment status.
"""

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Literal


# Common Windows install locations to fall back to when not on PATH
_WINDOWS_FALLBACKS = [
    r"C:\terraform\terraform.exe",
    r"C:\Program Files\Terraform\terraform.exe",
    r"C:\ProgramData\chocolatey\bin\terraform.exe",
]


def terraform_binary() -> str | None:
    """Find terraform: PATH first, then known Windows install locations."""
    on_path = shutil.which("terraform")
    if on_path:
        return on_path
    for candidate in _WINDOWS_FALLBACKS:
        if os.path.isfile(candidate):
            return candidate
    return None


def have_terraform() -> bool:
    return terraform_binary() is not None


@dataclass
class CommandResult:
    exit_code: int
    duration_sec: float
    stdout: str
    stderr: str


def _run(
    cmd: list[str], cwd: str, timeout_sec: int = 900
) -> CommandResult:
    # If first arg is "terraform", swap for resolved binary path
    if cmd and cmd[0] == "terraform":
        binpath = terraform_binary()
        if binpath:
            cmd = [binpath] + cmd[1:]

    env = os.environ.copy()
    env["TF_IN_AUTOMATION"] = "1"
    env.setdefault("TF_INPUT", "0")
    start = time.time()
    try:
        p = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=timeout_sec, env=env,
        )
        return CommandResult(
            exit_code=p.returncode,
            duration_sec=time.time() - start,
            stdout=p.stdout or "",
            stderr=p.stderr or "",
        )
    except subprocess.TimeoutExpired as e:
        return CommandResult(
            exit_code=-1,
            duration_sec=time.time() - start,
            stdout=e.stdout.decode() if e.stdout else "",
            stderr=f"TIMEOUT after {timeout_sec}s",
        )


def terraform_init(workflow_dir: str) -> CommandResult:
    return _run(
        ["terraform", "init", "-no-color", "-input=false"],
        cwd=workflow_dir, timeout_sec=300,
    )


def terraform_plan(workflow_dir: str) -> CommandResult:
    return _run(
        ["terraform", "plan", "-no-color", "-input=false", "-detailed-exitcode"],
        cwd=workflow_dir, timeout_sec=600,
    )


def terraform_apply(workflow_dir: str, parallelism: int = 5) -> CommandResult:
    return _run(
        [
            "terraform", "apply",
            "-no-color", "-input=false", "-auto-approve",
            f"-parallelism={parallelism}",
        ],
        cwd=workflow_dir, timeout_sec=2400,
    )


def terraform_destroy(workflow_dir: str) -> CommandResult:
    return _run(
        ["terraform", "destroy", "-no-color", "-input=false", "-auto-approve"],
        cwd=workflow_dir, timeout_sec=2400,
    )


SITE_MODULE_RE = re.compile(
    r"module\.(?P<site>[a-z0-9_]+)\.aws_(?P<kind>\w+)\.(?P<res>\w+):\s*(?P<action>Creating|Creation complete|Destroying|Destruction complete|Modifying|Modifications complete|Still creating|Still destroying)"
)


def parse_per_site_status(stdout: str) -> dict[str, dict]:
    """
    Extracts per-module deployment events. Returns:
        { "pune_01": {"created": 14, "in_progress": 0, "failed": 0, "last_event": "..."} , ... }
    """
    sites: dict[str, dict] = {}
    for line in stdout.splitlines():
        m = SITE_MODULE_RE.search(line)
        if not m:
            continue
        site = m.group("site")
        action = m.group("action")
        d = sites.setdefault(site, {
            "created": 0, "in_progress": 0, "failed": 0, "last_event": "",
        })
        d["last_event"] = action
        if "Creation complete" in action:
            d["created"] += 1
        elif "Creating" in action or "Still creating" in action:
            d["in_progress"] += 1
    return sites


def parse_plan_summary(stdout: str) -> tuple[int, int, int]:
    """Returns (to_add, to_change, to_destroy) from `terraform plan` output."""
    m = re.search(
        r"Plan:\s+(\d+)\s+to add,\s+(\d+)\s+to change,\s+(\d+)\s+to destroy",
        stdout,
    )
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return 0, 0, 0


def tail(s: str, n_lines: int = 120) -> str:
    lines = s.splitlines()
    return "\n".join(lines[-n_lines:])
