"""
IaC file generation + on-disk writing.
"""

import os
from pathlib import Path

from agents.common.schemas import IntakeResult, TerraformArtifact
from agents.iac.templates import (
    render_backend,
    render_central_vpc,
    render_provider,
    render_sites_file,
    render_tgw,
)


def _project_root() -> Path:
    """Project root is two levels up from this file (agents/iac/generator.py)."""
    return Path(__file__).resolve().parent.parent.parent


def _module_path_for(workflow_dir: Path) -> str:
    """Compute relative path from workflow_dir to terraform/modules/branch_site."""
    module_abs = _project_root() / "terraform" / "modules" / "branch_site"
    rel = os.path.relpath(module_abs, workflow_dir.resolve())
    # Terraform prefers forward slashes even on Windows
    return rel.replace("\\", "/")


def write_workflow_files(
    workflow_id: str,
    customer_name: str,
    intake: IntakeResult,
    output_root: str = "iac_output",
    module_path: str | None = None,
) -> tuple[str, list[TerraformArtifact]]:
    """
    Writes a self-contained Terraform workspace for this workflow.
    Returns (workflow_dir_absolute_path, artifacts).
    """
    workflow_dir = Path(output_root) / workflow_id
    workflow_dir.mkdir(parents=True, exist_ok=True)

    # Resolve module_path now that workflow_dir exists
    resolved_module_path = module_path or _module_path_for(workflow_dir)

    files = {
        "backend.tf": render_backend(workflow_id),
        "provider.tf": render_provider(workflow_id, customer_name),
        "central_vpc.tf": render_central_vpc(),
        "tgw.tf": render_tgw(),
        "sites.tf": render_sites_file(intake.sites, resolved_module_path),
    }

    artifacts: list[TerraformArtifact] = []
    for filename, content in files.items():
        path = workflow_dir / filename
        path.write_text(content, encoding="utf-8")
        artifacts.append(TerraformArtifact(
            path=str(path),
            kind="tf",
            line_count=content.count("\n"),
        ))

    return str(workflow_dir.resolve()), artifacts


def estimate_planned_resources(intake: IntakeResult) -> int:
    """
    Rough count of AWS resources Terraform will create.
    Central: 1 VPC + 1 IGW + 2 subnets + 2 RTs + 2 RT assocs + 1 TGW + 1 attachment = 10
    Per site: VPC + IGW + subnet + RT + RT assoc + SG + IAM role + role attach +
              instance profile + EC2 + EIP + CGW + VPN + TGW route = 14
    """
    return 10 + 14 * len(intake.sites)
