"""Reproducible PDF report builder using ReportLab and matplotlib.

Generates the executive PDF strictly from stored ``report.content``, ``report.metrics_snapshot``,
``report.verification``, and ``recommendations`` so that downloading a report is deterministic
and reproducible at any time.
"""

import io
from typing import Any

import matplotlib

matplotlib.use("Agg")
from xml.sax.saxutils import escape

import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.db.models import Recommendation, Report

SECTION_TITLES: tuple[tuple[str, str], ...] = (
    ("business_performance_insights", "1. Business Performance Insights"),
    ("revenue_and_expense_analysis", "2. Revenue & Expense Analysis"),
    ("customer_behavior_analysis", "3. Customer (Patient) Behavior Analysis"),
    ("operational_problems", "4. Operational Problems"),
    ("business_risk_identification", "5. Business Risk Identification"),
    ("growth_opportunities", "6. Growth Opportunities"),
    ("strategic_recommendations", "7. Strategic Recommendations"),
    ("actionable_business_improvement_plan", "8. Actionable Business Improvement Plan"),
)

KEY_SUMMARY_METRICS: tuple[tuple[str, str], ...] = (
    ("finance.net_revenue", "Invoiced Net Revenue (INR)"),
    ("finance.approved_expenses", "Approved Expenses (INR)"),
    ("finance.pending_expenses", "Pending Expense Exposure (INR)"),
    ("finance.rejected_expenses", "Rejected Expenses — Non-Cost (INR)"),
    ("finance.approved_margin", "Approved-Expense Margin (INR)"),
    ("finance.approved_margin_pct", "Approved-Expense Margin (%)"),
    ("appointments.total", "Total Appointments"),
    ("appointments.completed", "Completed Appointments"),
    ("appointments.scheduled", "Scheduled Pipeline Appointments"),
    ("appointments.completion_rate", "Completion Rate (%)"),
    ("appointments.no_show_rate", "No-Show Rate (%)"),
    ("appointments.avg_wait_minutes", "Average Wait Time (min)"),
    ("patients.total", "Registered Patients"),
    ("patients.repeat_visit_rate", "Repeat-Visit Rate (%)"),
    ("inventory.low_stock_items", "Low-Stock Items (<= Reorder Level)"),
    ("inventory.expiring_90d_items", "Items Expiring <= 90 Days"),
)


def _format_metric_val(metric: dict[str, Any] | None) -> str:
    if not metric:
        return "n/a"
    val = metric.get("value", 0)
    unit = metric.get("unit", "")
    if unit == "INR":
        return f"INR {float(val):,.2f}"
    if unit == "percent":
        return f"{float(val):.2f}%"
    if unit == "minutes":
        return f"{float(val):.2f} min"
    return f"{int(val):,}" if isinstance(val, int) or float(val).is_integer() else f"{val}"


def _render_finance_chart(snapshot: dict[str, Any]) -> io.BytesIO:
    rev = float(snapshot.get("finance.net_revenue", {}).get("value", 0)) / 1e6
    app_e = float(snapshot.get("finance.approved_expenses", {}).get("value", 0)) / 1e6
    pen_e = float(snapshot.get("finance.pending_expenses", {}).get("value", 0)) / 1e6
    rej_e = float(snapshot.get("finance.rejected_expenses", {}).get("value", 0)) / 1e6

    fig, ax = plt.subplots(figsize=(6.2, 2.4), dpi=140)
    labels = [
        "Invoiced\nNet Revenue",
        "Approved\nExpenses",
        "Pending\nExposure",
        "Rejected\n(Non-Cost)",
    ]
    values = [rev, app_e, pen_e, rej_e]
    bar_colors = ["#0E7C86", "#B91C1C", "#B45309", "#64748B"]
    bars = ax.bar(labels, values, color=bar_colors, width=0.52)
    ax.set_ylabel("INR (Millions)", fontsize=8)
    ax.set_title(
        "Revenue vs Expense Breakdown by Approval Status (INR Millions)",
        fontsize=9,
        fontweight="bold",
    )
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for bar, v in zip(bars, values, strict=False):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.4,
            f"{v:.2f}M",
            ha="center",
            va="bottom",
            fontsize=7.5,
        )
    ax.set_ylim(0, max([*values, 1.0]) * 1.22)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


def build_report_pdf(
    report: Report,
    recommendations: list[Recommendation],
    *,
    dataset_name: str = "Hospital Operations (May 1 - Oct 31, 2026)",
) -> bytes:
    """Render a complete, multi-section executive PDF from stored report & snapshot data."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="MediOps Intelligence — Business Intelligence Report",
        author="MediOps Intelligence",
    )

    base_styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=base_styles["Heading1"],
        fontSize=17,
        leading=21,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=4,
    )
    meta_style = ParagraphStyle(
        "ReportMeta",
        parent=base_styles["Normal"],
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569"),
    )
    h2_style = ParagraphStyle(
        "SectionH2",
        parent=base_styles["Heading2"],
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0E7C86"),
        spaceBefore=10,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=base_styles["Normal"],
        fontSize=9.2,
        leading=13.5,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=6,
    )
    cell_style = ParagraphStyle(
        "TableCell",
        parent=base_styles["Normal"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1E293B"),
    )

    story: list[Any] = []
    verdict_str = report.verdict.value.upper()
    conf_str = report.confidence.value.upper()
    created_str = report.created_at.strftime("%Y-%m-%d %H:%M UTC")

    # ---- Cover Header ----
    story.append(
        Paragraph(
            "MediOps Intelligence — AI-Powered Hospital Operations &amp; Performance Intelligence.",
            title_style,
        )
    )
    story.append(
        Paragraph(
            f"<b>Dataset:</b> {escape(dataset_name)} &nbsp;|&nbsp; "
            f"<b>Period:</b> 2026-05-01 to 2026-10-31 &nbsp;|&nbsp; "
            f"<b>Generated:</b> {created_str}",
            meta_style,
        )
    )
    story.append(
        Paragraph(
            f"<b>Verification Verdict:</b> {verdict_str} &nbsp;|&nbsp; "
            f"<b>Confidence:</b> {conf_str} &nbsp;|&nbsp; "
            f"<b>Report ID:</b> {report.id}",
            meta_style,
        )
    )
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1")))
    story.append(Spacer(1, 8))

    content = report.content or {}
    snapshot = report.metrics_snapshot or {}
    verification = report.verification or {}

    # ---- Executive Summary ----
    story.append(Paragraph("Executive Summary", h2_style))
    story.append(Paragraph(escape(str(content.get("executive_summary", ""))), body_style))

    # ---- Deterministic KPI Snapshot Table ----
    story.append(Paragraph("Deterministic KPI Baseline (Single Source of Truth)", h2_style))
    kpi_rows = [["Metric", "Metric Key", "Value", "Basis"]]
    for mkey, label in KEY_SUMMARY_METRICS:
        m = snapshot.get(mkey)
        kpi_rows.append(
            [
                Paragraph(escape(label), cell_style),
                Paragraph(f"<font name='Courier'>{escape(mkey)}</font>", cell_style),
                Paragraph(escape(_format_metric_val(m)), cell_style),
                Paragraph(escape(str((m or {}).get("basis", ""))), cell_style),
            ]
        )
    kpi_table = Table(kpi_rows, colWidths=[56 * mm, 48 * mm, 34 * mm, 40 * mm], repeatRows=1)
    kpi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6F4F5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0A5860")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(kpi_table)
    story.append(Spacer(1, 8))

    # ---- Embedded Chart ----
    chart_buf = _render_finance_chart(snapshot)
    story.append(Image(chart_buf, width=165 * mm, height=64 * mm))
    story.append(Spacer(1, 6))

    # ---- Eight Report Sections ----
    sections = content.get("sections", {})
    for key, heading in SECTION_TITLES:
        story.append(Paragraph(escape(heading), h2_style))
        story.append(Paragraph(escape(str(sections.get(key, ""))), body_style))

    # ---- Verified Findings Table ----
    findings = content.get("findings", [])
    if findings:
        story.append(Paragraph("Verified Analytical Findings &amp; Metric Citations", h2_style))
        f_rows = [["Finding Statement", "Cited Metric Keys", "Confidence"]]
        for f in findings:
            f_rows.append(
                [
                    Paragraph(escape(str(f.get("statement", ""))), cell_style),
                    Paragraph(escape(", ".join(f.get("metric_keys", []))), cell_style),
                    Paragraph(escape(str(f.get("confidence", "high")).upper()), cell_style),
                ]
            )
        f_table = Table(f_rows, colWidths=[106 * mm, 48 * mm, 24 * mm], repeatRows=1)
        f_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(f_table)
        story.append(Spacer(1, 8))

    # ---- Recommendations & HITL Status Table ----
    story.append(Paragraph("Strategic Recommendations &amp; Human-in-the-Loop Status", h2_style))
    rec_rows = [["Recommendation", "Action Type", "Evidence Keys", "Approval Status"]]
    if recommendations:
        for rec in recommendations:
            rec_rows.append(
                [
                    Paragraph(
                        f"<b>{escape(rec.title)}</b><br/>{escape(rec.rationale)}", cell_style
                    ),
                    Paragraph(escape(rec.action_type), cell_style),
                    Paragraph(escape(", ".join(rec.evidence_metric_keys)), cell_style),
                    Paragraph(escape(rec.status.value), cell_style),
                ]
            )
    else:
        for r in content.get("recommendations", []):
            rec_rows.append(
                [
                    Paragraph(
                        f"<b>{escape(str(r.get('title', '')))}</b><br/>{escape(str(r.get('rationale', '')))}",
                        cell_style,
                    ),
                    Paragraph(escape(str(r.get("action_type", ""))), cell_style),
                    Paragraph(escape(", ".join(r.get("evidence_metric_keys", []))), cell_style),
                    Paragraph(
                        (
                            "no_approval_required"
                            if not r.get("requires_approval", True)
                            else "not_queued"
                        ),
                        cell_style,
                    ),
                ]
            )
    rec_table = Table(rec_rows, colWidths=[88 * mm, 24 * mm, 38 * mm, 28 * mm], repeatRows=1)
    rec_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6F4F5")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(rec_table)
    story.append(Spacer(1, 8))

    # ---- Verification Appendix & Data Limitations ----
    story.append(Paragraph("Verification Appendix &amp; Dataset Limitations", h2_style))
    det = verification.get("deterministic", {})
    story.append(
        Paragraph(
            f"<b>Deterministic Verifier:</b> Checked {det.get('checked', 0)} metric citations · "
            f"Passed {det.get('passed', 0)} · Failed {len(det.get('failed', []))} · "
            f"Unsupported numeric claims {len(det.get('unsupported', []))} · "
            f"Revision loops: {verification.get('revision_count', 0)}.",
            body_style,
        )
    )
    for lim in content.get("data_limitations", []):
        story.append(Paragraph(f"• {escape(str(lim))}", body_style))

    doc.build(story)
    return buf.getvalue()
