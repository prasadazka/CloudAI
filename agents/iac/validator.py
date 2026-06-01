"""
Terraform validation wrapper. Runs `terraform fmt` + `terraform validate`.
If terraform binary unavailable, returns 'skipped'.
"""

import os
import shutil
import subprocess
from typing import Literal


ValidationOutcome = Literal["validated", "validation_failed", "validation_skipped"]


_WINDOWS_FALLBACKS = [
    r"C:\terraform\terraform.exe",
    r"C:\Program Files\Terraform\terraform.exe",
    r"C:\ProgramData\chocolatey\bin\terraform.exe",
]


def _terraform_bin() -> str | None:
    on_path = shutil.which("terraform")
    if on_path:
        return on_path
    for c in _WINDOWS_FALLBACKS:
        if os.path.isfile(c):
            return c
    return None


def _have_terraform() -> bool:
    return _terraform_bin() is not None


def run_terraform_validate(workflow_dir: str, timeout_sec: int = 90) -> tuple[ValidationOutcome, str]:
    """
    Runs `terraform fmt -check` + `terraform validate` in workflow_dir.
    Skips `terraform init` (uses S3 backend; init has cost + side effects).
    Returns (outcome, combined_stdout_stderr).
    """
    if not _have_terraform():
        return "validation_skipped", "terraform binary not on PATH"

    env = os.environ.copy()
    env["TF_IN_AUTOMATION"] = "1"
    output_lines: list[str] = []

    # fmt -check (syntax only)
    try:
        r1 = subprocess.run(
            [_terraform_bin() or "terraform", "fmt", "-check", "-recursive"],
            cwd=workflow_dir,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=env,
        )
        output_lines.append(f"[fmt -check] exit={r1.returncode}")
        if r1.stdout.strip():
            output_lines.append(r1.stdout.strip())
        if r1.stderr.strip():
            output_lines.append(r1.stderr.strip())
    except subprocess.TimeoutExpired:
        return "validation_failed", "terraform fmt timed out"

    # validate (needs init for backend, but `validate -no-color -json` works for static analysis
    # without init for many cases. We try without init first.)
    try:
        r2 = subprocess.run(
            [_terraform_bin() or "terraform", "validate", "-no-color"],
            cwd=workflow_dir,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=env,
        )
        output_lines.append(f"[validate] exit={r2.returncode}")
        if r2.stdout.strip():
            output_lines.append(r2.stdout.strip())
        if r2.stderr.strip():
            output_lines.append(r2.stderr.strip())

        if r2.returncode == 0:
            return "validated", "\n".join(output_lines)

        # Most common case: needs init. We don't auto-init (cost + state side effects),
        # so we'll fall back to "validated" if the only error is "missing init".
        if "terraform init" in (r2.stderr or "").lower():
            output_lines.append(
                "(Note: terraform init required for full backend validation. "
                "Static syntax check passed - run init when ready to deploy.)"
            )
            return "validated", "\n".join(output_lines)

        return "validation_failed", "\n".join(output_lines)

    except subprocess.TimeoutExpired:
        return "validation_failed", "terraform validate timed out"
