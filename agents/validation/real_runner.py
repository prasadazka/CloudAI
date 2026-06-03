"""
Real SSM-driven validation. After a successful terraform apply, the site
edges are real EC2 instances. This runner connects to them via AWS Systems
Manager Run Command and executes connectivity + IPsec checks.

Falls back gracefully if boto3 isn't available, if SSM agents haven't
registered yet, or if instances aren't tagged as expected.
"""

from __future__ import annotations

import time
from typing import Optional

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import BotoCoreError, ClientError
    _BOTO_OK = True
except ImportError:
    _BOTO_OK = False


_AWS_REGION = "ap-south-1"
_AWS_PROFILE = "vi-demo"


def boto_available() -> bool:
    return _BOTO_OK


def _clients():
    """Build EC2 + SSM clients with no-SSL-verify (matches our env)."""
    session = boto3.Session(profile_name=_AWS_PROFILE, region_name=_AWS_REGION)
    cfg = Config(retries={"max_attempts": 3, "mode": "standard"})
    return (
        session.client("ec2", config=cfg, verify=False),
        session.client("ssm", config=cfg, verify=False),
    )


def list_live_site_instances(workflow_id: Optional[str] = None) -> list[dict]:
    """
    Returns list of {instance_id, site_name, public_ip, private_ip}
    for live ViDemo SD-WAN edge EC2s. If workflow_id is given, restricts
    to that workflow.
    """
    if not _BOTO_OK:
        return []
    ec2, _ = _clients()
    filters = [
        {"Name": "tag:Role", "Values": ["sdwan-edge-simulator"]},
        {"Name": "instance-state-name", "Values": ["running"]},
    ]
    if workflow_id:
        filters.append({"Name": "tag:WorkflowID", "Values": [workflow_id]})
    try:
        resp = ec2.describe_instances(Filters=filters)
    except (ClientError, BotoCoreError):
        return []

    out: list[dict] = []
    for r in resp.get("Reservations", []):
        for i in r.get("Instances", []):
            tags = {t["Key"]: t["Value"] for t in i.get("Tags", [])}
            out.append({
                "instance_id": i["InstanceId"],
                "site_name": tags.get("Site") or tags.get("Name", i["InstanceId"]),
                "public_ip": i.get("PublicIpAddress"),
                "private_ip": i.get("PrivateIpAddress"),
            })
    return out


def wait_for_ssm_ready(
    instance_ids: list[str],
    max_wait_sec: int = 360,
    poll_every_sec: int = 30,
    progress: Optional[callable] = None,  # type: ignore[valid-type]
) -> dict:
    """
    Block until every instance shows PingStatus=Online in SSM, or the deadline
    passes. EC2 boot + cloud-init + SSM agent registration typically takes
    3-5 min after terraform reports the instance "running". Without this wait,
    validation races SSM and sees bogus 'timeout' results.

    Returns: {"all_ready": bool, "ready_ids": [...], "missing_ids": [...], "elapsed_sec": float}
    """
    if not _BOTO_OK or not instance_ids:
        return {"all_ready": False, "ready_ids": [], "missing_ids": instance_ids,
                "elapsed_sec": 0.0, "skipped": True}

    _, ssm = _clients()
    target = set(instance_ids)
    deadline = time.time() + max_wait_sec
    start = time.time()
    last_ready: set[str] = set()

    while time.time() < deadline:
        # SSM's PingStatus comes from a passive 5-min heartbeat - it can show
        # "ConnectionLost" while commands still execute successfully (the agent
        # reconnects on demand). Accept any instance that has *ever* registered
        # (PingStatus is set) as eligible; we verify command execution with
        # the actual ping test that follows.
        try:
            resp = ssm.describe_instance_information(MaxResults=50)
            ready = {
                i["InstanceId"] for i in resp.get("InstanceInformationList", [])
                if i["InstanceId"] in target and i.get("PingStatus") in ("Online", "ConnectionLost")
            }
        except (ClientError, BotoCoreError):
            ready = set()

        if ready != last_ready and progress is not None:
            try:
                progress(f"SSM ready: {len(ready)}/{len(target)} instances")
            except Exception:
                pass
            last_ready = ready

        if ready >= target:
            return {
                "all_ready": True, "ready_ids": list(ready),
                "missing_ids": [], "elapsed_sec": round(time.time() - start, 1),
            }
        time.sleep(poll_every_sec)

    return {
        "all_ready": False, "ready_ids": list(last_ready),
        "missing_ids": list(target - last_ready),
        "elapsed_sec": round(time.time() - start, 1),
    }


def run_ssm(instance_id: str, commands: list[str], timeout_sec: int = 90) -> dict:
    """Send a single Run Command and wait for result. Returns dict with status + output."""
    if not _BOTO_OK:
        return {"status": "skipped", "output": "boto3 unavailable", "ok": False}
    _, ssm = _clients()
    try:
        resp = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": commands},
            TimeoutSeconds=60,
        )
        cmd_id = resp["Command"]["CommandId"]
    except (ClientError, BotoCoreError) as e:
        return {"status": "error", "output": f"send_command: {e}", "ok": False}

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            r = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=instance_id)
            status = r.get("Status")
            if status in ("Success", "Failed", "Cancelled", "TimedOut"):
                return {
                    "status": status.lower(),
                    "output": (r.get("StandardOutputContent") or "")
                              + (r.get("StandardErrorContent") or ""),
                    "ok": status == "Success",
                    "exit_code": r.get("ResponseCode"),
                }
        except (ClientError, BotoCoreError):
            pass
        time.sleep(2)

    return {"status": "timeout", "output": "polling timeout", "ok": False}
