"""
Audit PDF Generator for Cloud Siddhi (by Azkashine).
Pure Python, no LLM. Takes Intake + Policy results, produces compliance PDF.
"""

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from agents.common.schemas import (
    ArchitectureResult,
    DeploymentResult,
    IntakeResult,
    PolicyResult,
    ValidationResult,
)

VI_RED = colors.HexColor("#ED1C2E")
VI_YELLOW = colors.HexColor("#FFB81C")
VI_DARK = colors.HexColor("#1A1A1A")
GREY_LIGHT = colors.HexColor("#F4F4F4")
GREY_BORDER = colors.HexColor("#CCCCCC")
PASS_GREEN = colors.HexColor("#1B8A4D")
WARN_AMBER = colors.HexColor("#E68A00")
FAIL_RED = colors.HexColor("#C0202C")


def _draw_brand_mark(canvas, x_cm: float, y_cm: float, size_cm: float = 1.1) -> None:
    """
    Draws the Cloud Siddhi brand mark (white circle with red interwoven S) directly
    on the canvas. No external image dependency - same motif as the favicon.
    """
    cx = x_cm + size_cm / 2
    cy = y_cm + size_cm / 2
    r = size_cm / 2

    canvas.saveState()
    canvas.setFillColor(colors.white)
    canvas.circle(cx * cm, cy * cm, r * cm, stroke=0, fill=1)

    # Stylised S - two interlocking arcs in Vi red (kept for visual harmony
    # with the header bar but represents Cloud Siddhi's accomplishment mark).
    canvas.setStrokeColor(VI_RED)
    canvas.setLineWidth(2.2)
    canvas.setLineCap(1)  # round

    # upper bowl
    p1 = canvas.beginPath()
    p1.moveTo((cx - 0.32 * size_cm) * cm, (cy + 0.32 * size_cm) * cm)
    p1.curveTo(
        (cx - 0.32 * size_cm) * cm, (cy + 0.52 * size_cm) * cm,
        (cx + 0.05 * size_cm) * cm, (cy + 0.52 * size_cm) * cm,
        (cx + 0.05 * size_cm) * cm, (cy + 0.32 * size_cm) * cm,
    )
    p1.curveTo(
        (cx + 0.05 * size_cm) * cm, (cy + 0.10 * size_cm) * cm,
        (cx - 0.32 * size_cm) * cm, (cy + 0.10 * size_cm) * cm,
        (cx - 0.32 * size_cm) * cm, (cy - 0.10 * size_cm) * cm,
    )
    canvas.drawPath(p1, stroke=1, fill=0)

    # lower bowl
    p2 = canvas.beginPath()
    p2.moveTo((cx - 0.32 * size_cm) * cm, (cy - 0.10 * size_cm) * cm)
    p2.curveTo(
        (cx - 0.32 * size_cm) * cm, (cy - 0.32 * size_cm) * cm,
        (cx + 0.32 * size_cm) * cm, (cy - 0.32 * size_cm) * cm,
        (cx + 0.32 * size_cm) * cm, (cy - 0.10 * size_cm) * cm,
    )
    canvas.drawPath(p2, stroke=1, fill=0)

    # Accent dot = AI/orchestrator
    canvas.setFillColor(VI_YELLOW)
    canvas.circle((cx + 0.40 * size_cm) * cm, (cy + 0.40 * size_cm) * cm,
                  0.06 * size_cm * cm, stroke=0, fill=1)
    canvas.restoreState()


@dataclass
class AuditData:
    workflow_id: str
    customer_name: str
    intake: IntakeResult
    policy: PolicyResult
    generated_at: datetime
    approval_signoff: Optional[str] = None
    deployment_status: Optional[str] = None
    architecture: Optional[ArchitectureResult] = None
    deployment: Optional[DeploymentResult] = None
    validation: Optional[ValidationResult] = None


def _header_footer(canvas, doc):
    canvas.saveState()

    # Red header bar (kept - visual signature)
    canvas.setFillColor(VI_RED)
    canvas.rect(0, A4[1] - 1.7 * cm, A4[0], 1.7 * cm, fill=1, stroke=0)

    # Cloud Siddhi brand mark drawn inline (no image file needed).
    # Logo top-left: x=1.3cm, y aligned with header bar
    mark_size = 1.05  # cm
    mark_x = 1.3
    mark_y = (A4[1] / cm) - 1.45
    _draw_brand_mark(canvas, mark_x, mark_y, mark_size)

    # Wordmark
    title_x = (mark_x + mark_size + 0.35) * cm
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 14)
    canvas.drawString(title_x, A4[1] - 1.0 * cm, "Cloud Siddhi")
    canvas.setFont("Helvetica", 8.5)
    canvas.drawString(title_x, A4[1] - 1.45 * cm, "Agentic AI · Cloud Orchestration")

    canvas.setFont("Helvetica", 9)
    canvas.drawRightString(
        A4[0] - 1.5 * cm, A4[1] - 1.1 * cm,
        "Agentic AI - Audit Report",
    )

    # Thin yellow accent line under header
    canvas.setFillColor(VI_YELLOW)
    canvas.rect(0, A4[1] - 1.75 * cm, A4[0], 0.08 * cm, fill=1, stroke=0)

    # Footer
    canvas.setFillColor(VI_DARK)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(
        1.5 * cm, 1.0 * cm,
        f"Cloud Siddhi by Azkashine  ·  Page {doc.page}",
    )
    canvas.drawRightString(
        A4[0] - 1.5 * cm, 1.0 * cm,
        "Confidential - Internal Use Only",
    )

    canvas.restoreState()


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(
        name="ViTitle",
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=VI_RED,
        spaceAfter=12,
        alignment=TA_LEFT,
    ))
    s.add(ParagraphStyle(
        name="ViSection",
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=VI_RED,
        spaceBefore=18,
        spaceAfter=8,
        borderPadding=4,
    ))
    s.add(ParagraphStyle(
        name="ViBody",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=VI_DARK,
        spaceAfter=6,
    ))
    s.add(ParagraphStyle(
        name="ViLabel",
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=VI_DARK,
    ))
    s.add(ParagraphStyle(
        name="ViMono",
        fontName="Courier",
        fontSize=9,
        leading=12,
        textColor=VI_DARK,
        backColor=GREY_LIGHT,
        borderPadding=8,
    ))
    return s


def _kv_table(rows: list[tuple[str, str]], col_widths=None) -> Table:
    cell_style = ParagraphStyle(
        name="CellWrap",
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=VI_DARK,
    )
    data = [[k, Paragraph(str(v), cell_style)] for k, v in rows]
    table = Table(
        data,
        colWidths=col_widths or [5 * cm, 12 * cm],
    )
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), VI_DARK),
        ("BACKGROUND", (0, 0), (0, -1), GREY_LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, GREY_BORDER),
        ("BOX", (0, 0), (-1, -1), 0.5, GREY_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def _status_color(status: str):
    return {
        "pass": PASS_GREEN,
        "warn": WARN_AMBER,
        "fail": FAIL_RED,
    }.get(status, VI_DARK)


def _checks_table(checks) -> Table:
    cell_style = ParagraphStyle(
        name="ChkCell",
        fontName="Helvetica",
        fontSize=9,
        leading=11,
        textColor=VI_DARK,
    )
    header = ["#", "Check", "Status", "Details", "Policy Ref"]
    data = [header]
    for i, c in enumerate(checks, 1):
        data.append([
            str(i),
            Paragraph(c.name, cell_style),
            c.status.upper(),
            Paragraph(c.details, cell_style),
            Paragraph(c.policy_ref or "-", cell_style),
        ])

    table = Table(
        data,
        colWidths=[0.7 * cm, 3.2 * cm, 1.5 * cm, 7.6 * cm, 3.0 * cm],
        repeatRows=1,
    )
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VI_RED),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, GREY_BORDER),
        ("BOX", (0, 0), (-1, -1), 0.4, GREY_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
    for i, c in enumerate(checks, 1):
        style.add("TEXTCOLOR", (2, i), (2, i), _status_color(c.status))
        style.add("FONT", (2, i), (2, i), "Helvetica-Bold", 9)
        if i % 2 == 0:
            style.add("BACKGROUND", (0, i), (-1, i), GREY_LIGHT)
    table.setStyle(style)
    return table


def _validation_table(validation: ValidationResult) -> Table:
    cell_style = ParagraphStyle(
        name="ValCell",
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=VI_DARK,
    )
    header = ["#", "Site", "Overall", "Ping", "Throughput", "QoS", "Encryption"]
    data = [header]
    for i, sv in enumerate(validation.sites_detail, 1):
        tests_by_name = {t.name: t for t in sv.tests}
        data.append([
            str(i),
            Paragraph(sv.site_name, cell_style),
            sv.overall.upper(),
            Paragraph(
                tests_by_name.get("ping").measured if "ping" in tests_by_name else "-",
                cell_style,
            ),
            Paragraph(
                tests_by_name.get("throughput").measured if "throughput" in tests_by_name else "-",
                cell_style,
            ),
            Paragraph(
                tests_by_name.get("qos").outcome.upper() if "qos" in tests_by_name else "-",
                cell_style,
            ),
            Paragraph(
                tests_by_name.get("encryption").outcome.upper() if "encryption" in tests_by_name else "-",
                cell_style,
            ),
        ])

    table = Table(
        data,
        colWidths=[0.7 * cm, 2.6 * cm, 1.6 * cm, 3.0 * cm, 4.0 * cm, 1.6 * cm, 2.5 * cm],
        repeatRows=1,
    )
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VI_RED),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (2, -1), "CENTER"),
        ("ALIGN", (5, 1), (6, -1), "CENTER"),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, GREY_BORDER),
        ("BOX", (0, 0), (-1, -1), 0.4, GREY_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
    for i, sv in enumerate(validation.sites_detail, 1):
        col_color = _status_color(sv.overall) if sv.overall != "skipped" else VI_DARK
        style.add("TEXTCOLOR", (2, i), (2, i), col_color)
        style.add("FONT", (2, i), (2, i), "Helvetica-Bold", 9)
        if i % 2 == 0:
            style.add("BACKGROUND", (0, i), (-1, i), GREY_LIGHT)
    table.setStyle(style)
    return table


def _infrastructure_tables(deployment: DeploymentResult) -> list:
    """
    Render two tables for the audit:
      1. Hub + resource-type counts (key/value rows)
      2. Per-site AWS IDs (VPC / EC2 / VPN / tunnel status)
    Returns a list of flowables (tables interleaved with Paragraphs/Spacers).
    """
    flowables: list = []
    infra = deployment.infrastructure
    if not infra:
        return flowables

    cell_style = ParagraphStyle(
        name="InfraCell", fontName="Helvetica", fontSize=7, leading=9, textColor=VI_DARK,
    )
    mono_style = ParagraphStyle(
        name="InfraMono", fontName="Courier", fontSize=6.5, leading=8, textColor=VI_DARK,
    )

    # --- 1. Hub + counts (kv) ---
    hub_rows = [("AWS Region", infra.region)]
    if infra.transit_gateway_id:
        hub_rows.append(("Transit Gateway", infra.transit_gateway_id))
    if infra.central_vpc_id:
        hub_rows.append(("Central VPC", f"{infra.central_vpc_id} ({infra.central_vpc_cidr or '—'})"))
    hub_rows.append(("Total Resources", str(infra.total_resources)))
    if infra.cost_per_hour_usd is not None:
        inr_hr = int(infra.cost_per_hour_usd * 83)
        hub_rows.append(
            ("Hourly Burn Rate", f"~Rs {inr_hr}/hr (${infra.cost_per_hour_usd:.4f}/hr)")
        )
    flowables.append(_kv_table(hub_rows))

    if infra.resource_counts:
        flowables.append(Spacer(1, 0.3 * cm))
        kinds = sorted(infra.resource_counts.keys())
        # 3-col grid: kind | count | kind | count ...
        rows: list[list] = [["Resource Type", "Count", "Resource Type", "Count"]]
        for i in range(0, len(kinds), 2):
            left_k = kinds[i]
            left_v = str(infra.resource_counts[left_k])
            if i + 1 < len(kinds):
                right_k = kinds[i + 1]
                right_v = str(infra.resource_counts[right_k])
            else:
                right_k, right_v = "", ""
            rows.append([left_k, left_v, right_k, right_v])
        rt = Table(rows, colWidths=[4.5 * cm, 1.8 * cm, 4.5 * cm, 1.8 * cm], repeatRows=1)
        rt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VI_RED),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
            ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("ALIGN", (3, 1), (3, -1), "RIGHT"),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, GREY_BORDER),
            ("BOX", (0, 0), (-1, -1), 0.4, GREY_BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        flowables.append(rt)

    # --- 2. Per-site detail ---
    if infra.sites:
        flowables.append(Spacer(1, 0.4 * cm))
        header = ["Site", "VPC ID / CIDR", "EC2 Instance", "Public IP", "VPN Connection", "T1", "T2"]
        rows = [header]
        for s in infra.sites:
            vpc_cell = Paragraph(
                f"{s.vpc_id or '—'}<br/><font color='#666666'>{s.vpc_cidr or ''}</font>",
                mono_style,
            )
            ec2_cell = Paragraph(
                f"{s.instance_id or '—'}<br/><font color='#666666'>{s.instance_type or ''}</font>",
                mono_style,
            )
            t1 = (s.tunnel_1_status or "—").upper()
            t2 = (s.tunnel_2_status or "—").upper()
            rows.append([
                Paragraph(s.site_name, cell_style),
                vpc_cell,
                ec2_cell,
                Paragraph(s.public_ip or "—", mono_style),
                Paragraph(s.vpn_connection_id or "—", mono_style),
                t1,
                t2,
            ])

        site_table = Table(
            rows,
            colWidths=[2.0 * cm, 3.6 * cm, 3.6 * cm, 2.4 * cm, 3.4 * cm, 0.9 * cm, 0.9 * cm],
            repeatRows=1,
        )
        style = TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), VI_RED),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
            ("FONT", (5, 1), (6, -1), "Helvetica-Bold", 8),
            ("ALIGN", (5, 0), (6, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, GREY_BORDER),
            ("BOX", (0, 0), (-1, -1), 0.4, GREY_BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
        for i, s in enumerate(infra.sites, 1):
            if i % 2 == 0:
                style.add("BACKGROUND", (0, i), (-1, i), GREY_LIGHT)
            t1_color = PASS_GREEN if (s.tunnel_1_status or "").upper() == "UP" else FAIL_RED
            t2_color = PASS_GREEN if (s.tunnel_2_status or "").upper() == "UP" else FAIL_RED
            style.add("TEXTCOLOR", (5, i), (5, i), t1_color)
            style.add("TEXTCOLOR", (6, i), (6, i), t2_color)
        site_table.setStyle(style)
        flowables.append(site_table)

    return flowables


def _sites_table(intake: IntakeResult, policy: PolicyResult) -> Table:
    from agents.policy.rules import estimate_site_cost
    header = ["#", "City", "State", "Bandwidth (Mbps)", "Monthly Cost (Rs)"]
    data = [header]
    for i, s in enumerate(intake.sites, 1):
        cost = estimate_site_cost(
            s, intake.connectivity_type, intake.compliance_tier,
        )
        data.append([
            str(i),
            s.city,
            s.state or "-",
            str(s.bandwidth_mbps),
            f"{cost:,}",
        ])

    table = Table(
        data,
        colWidths=[0.8 * cm, 3.5 * cm, 3.5 * cm, 3.8 * cm, 4.4 * cm],
        repeatRows=1,
    )
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VI_RED),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
        ("ALIGN", (3, 1), (4, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, GREY_BORDER),
        ("BOX", (0, 0), (-1, -1), 0.4, GREY_BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.add("BACKGROUND", (0, i), (-1, i), GREY_LIGHT)
    table.setStyle(style)
    return table


def generate_audit_pdf(data: AuditData, output_path: str) -> str:
    """Generate the audit PDF. Returns the absolute output path."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=2.7 * cm,
        bottomMargin=2 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        title=f"Cloud Siddhi Audit Report - {data.workflow_id}",
        author="Cloud Siddhi by Azkashine",
    )

    styles = _styles()
    body = styles["ViBody"]
    section = styles["ViSection"]
    story = []

    # ---- Cover block ----
    story.append(Paragraph("Cloud Service Fulfillment Audit", styles["ViTitle"]))
    story.append(Paragraph(
        "Agentic AI-driven onboarding - automated compliance attestation",
        body,
    ))
    story.append(Spacer(1, 0.4 * cm))

    cover_rows = [
        ("Workflow ID", data.workflow_id),
        ("Customer", data.customer_name),
        ("Generated", data.generated_at.strftime("%Y-%m-%d %H:%M:%S %Z")),
        ("Overall Decision", data.policy.overall_status.upper().replace("_", " ")),
        ("Approval Level", data.policy.approval_level_required.upper()),
        ("Estimated Monthly Cost",
         f"Rs {data.policy.estimated_cost_inr_monthly:,}"),
        ("Estimated Annual Cost",
         f"Rs {data.policy.estimated_cost_inr_monthly * 12:,}"),
        ("Sites Requested", str(data.intake.site_count)),
        ("Connectivity Type", data.intake.connectivity_type),
        ("Compliance Tier", data.intake.compliance_tier),
        ("Deadline", data.intake.deadline or "Not specified"),
    ]
    story.append(_kv_table(cover_rows))

    # ---- Executive Summary ----
    story.append(Paragraph("Executive Summary", section))
    story.append(Paragraph(data.policy.summary, body))

    # ---- Original Request ----
    story.append(Paragraph("Original Customer Request", section))
    story.append(Paragraph(
        f"Captured verbatim from intake portal:",
        body,
    ))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(data.intake.raw_request, styles["ViMono"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        f"<b>Intake Confidence:</b> {data.intake.confidence:.2%} - "
        f"{'No clarification needed' if not data.intake.needs_clarification else 'Clarification requested'}",
        body,
    ))

    # ---- Compliance Validation ----
    story.append(PageBreak())
    story.append(Paragraph("Compliance Validation", section))
    story.append(Paragraph(
        f"Total of {len(data.policy.checks)} policy checks were executed automatically. "
        f"Each check references the relevant telco internal policy code.",
        body,
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(_checks_table(data.policy.checks))

    # ---- Sites Inventory ----
    if data.intake.sites:
        story.append(PageBreak())
        story.append(Paragraph("Sites Inventory", section))
        story.append(_sites_table(data.intake, data.policy))

    # ---- Provisioned Infrastructure (post-apply boto3 snapshot) ----
    if data.deployment and data.deployment.infrastructure:
        story.append(PageBreak())
        story.append(Paragraph("Provisioned AWS Infrastructure", section))
        story.append(Paragraph(
            "Live inventory pulled from AWS after terraform apply completed. "
            "Use these resource IDs for audit, billing reconciliation, and "
            "post-incident forensics.",
            body,
        ))
        story.append(Spacer(1, 0.3 * cm))
        for flow in _infrastructure_tables(data.deployment):
            story.append(flow)

    # ---- Validation Results ----
    if data.validation:
        story.append(PageBreak())
        story.append(Paragraph("End-to-End Validation Results", section))

        v = data.validation
        summary_rows = [
            ("Validation Status", v.status.upper().replace("_", " ")),
            ("Test Mode", v.mode.upper()),
            ("SLA Target Uptime", f"{v.sla_target_uptime_pct}%"),
            ("Sites Tested", str(v.sites_tested)),
            ("Sites Passed", str(v.sites_passed)),
            ("Sites Borderline", str(v.sites_borderline)),
            ("Sites Failed", str(v.sites_failed)),
        ]
        story.append(_kv_table(summary_rows))

        if v.disclaimer:
            story.append(Spacer(1, 0.3 * cm))
            story.append(Paragraph(
                f"<i>Note: {v.disclaimer}</i>",
                body,
            ))

        if v.sites_detail:
            story.append(Spacer(1, 0.3 * cm))
            story.append(_validation_table(v))

    # ---- Approval Chain ----
    story.append(PageBreak())
    story.append(Paragraph("Approval Chain", section))
    approval_rows = [
        ("Required Level", data.policy.approval_level_required.upper()),
        ("Status", data.approval_signoff or "PENDING"),
        ("Cost Threshold Breach",
         "Yes" if any("Cost Threshold" in c.name and c.status == "warn"
                      for c in data.policy.checks) else "No"),
        ("BFSI Review Required",
         "Yes" if data.intake.compliance_tier == "BFSI_equivalent" else "No"),
    ]
    story.append(_kv_table(approval_rows))

    # ---- Signature ----
    story.append(Paragraph("Signatures and Attestation", section))
    sig_rows = [
        ("Platform", "Cloud Siddhi v1.0 — Agentic Orchestration"),
        ("Vendor", "Azkashine"),
        ("AI Attestation",
         "All checks executed by deterministic policy engine; "
         "intake extraction by LLM with structured-output validation"),
        ("Cryptographic Reference", f"workflow:{data.workflow_id}"),
        ("Generated At", data.generated_at.strftime("%Y-%m-%d %H:%M:%S %Z")),
    ]
    story.append(_kv_table(sig_rows))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return os.path.abspath(output_path)


def build_audit(
    intake: IntakeResult,
    policy: PolicyResult,
    customer_name: str = "Unnamed Customer",
    output_dir: str = "audits",
    approval_signoff: Optional[str] = None,
    architecture: Optional[ArchitectureResult] = None,
    deployment: Optional[DeploymentResult] = None,
    validation: Optional[ValidationResult] = None,
    workflow_id: Optional[str] = None,
) -> str:
    """Convenience entry point - returns generated PDF path."""
    if not workflow_id:
        workflow_id = f"wf-{uuid.uuid4().hex[:12]}"
    filename = f"{workflow_id}.pdf"
    output_path = os.path.join(output_dir, filename)

    data = AuditData(
        workflow_id=workflow_id,
        customer_name=customer_name,
        intake=intake,
        policy=policy,
        generated_at=datetime.now(timezone.utc),
        approval_signoff=approval_signoff,
        architecture=architecture,
        deployment=deployment,
        validation=validation,
    )
    return generate_audit_pdf(data, output_path)
