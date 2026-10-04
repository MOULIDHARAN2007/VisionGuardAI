"""
VisionGuard AI 2.0 - Historical AI Analytics & Intelligence Routes
Calculates real-time SQL statistical aggregations from detections and complaints tables.
"""

import csv
import io
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from database.database import get_db
from database.models import Detection, Complaint, User, Worker, Assignment, UserRole
from auth.dependencies import get_current_user_optional, require_admin

router = APIRouter(prefix="/api/analytics", tags=["Historical AI Analytics"])


def _build_pdf_document(title: str, subtitle: str, headers: List[str], data_rows: List[List[str]], col_widths: Optional[List[float]] = None) -> bytes:
    """Generate a clean, high-precision ReportLab PDF document matching VisionGuard light-theme."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A")
    )
    sub_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#64748B")
    )
    cell_style = ParagraphStyle(
        "ReportCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#334155")
    )
    header_style = ParagraphStyle(
        "ReportHeaderCell",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=colors.white
    )

    elements = []
    # Title & Header
    elements.append(Paragraph(f"VisionGuard AI 2.0 &mdash; {title}", title_style))
    gen_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    elements.append(Paragraph(f"{subtitle} &bull; Generated: {gen_time} &bull; Total Records: {len(data_rows)}", sub_style))
    elements.append(Spacer(1, 14))

    # Build Table Data
    table_data = [[Paragraph(h, header_style) for h in headers]]
    for row in data_rows:
        table_data.append([Paragraph(str(val), cell_style) for val in row])

    # Table styling
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0284C7")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    elements.append(t)

    # Footer spacer
    elements.append(Spacer(1, 12))
    footer_text = "CONFIDENTIAL &bull; VisionGuard AI 2.0 Municipal Infrastructure Diagnostics &bull; Automated Real-Time SQL Audit"
    elements.append(Paragraph(footer_text, sub_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


# --- CSV & PDF EXPORTS ---

@router.get("/export-complaints-csv")
def export_complaints_csv(db: Session = Depends(get_db)):
    """Export all municipal complaints to CSV format."""
    complaints = db.query(Complaint).order_by(Complaint.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Complaint ID", "Title", "Issue Category", "Severity", "Status",
        "Latitude", "Longitude", "Description", "AI Model", "Detected Class",
        "Confidence", "Citizen ID", "Assigned Worker ID", "Created At", "Updated At"
    ])
    for c in complaints:
        writer.writerow([
            c.complaint_id, c.title or "", c.issue_type, c.severity, c.status,
            c.latitude or "", c.longitude or "", c.description or "",
            c.ai_model or "", c.detected_class or "", c.confidence or "",
            c.user_id, c.assigned_worker_id or "Unassigned",
            c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else "",
            c.updated_at.strftime("%Y-%m-%d %H:%M:%S") if c.updated_at else ""
        ])
    output.seek(0)
    filename = f"visionguard_complaints_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export-complaints-pdf")
def export_complaints_pdf(db: Session = Depends(get_db)):
    """Export municipal complaints report in high-resolution PDF."""
    complaints = db.query(Complaint).order_by(Complaint.created_at.desc()).all()
    headers = ["Complaint ID", "Category", "Severity", "Status", "GPS Coordinates", "AI Diagnostic", "Assigned", "Date"]
    rows = []
    for c in complaints:
        coords = f"{c.latitude:.4f}, {c.longitude:.4f}" if c.latitude and c.longitude else "N/A"
        ai_info = f"{c.detected_class or 'Hazard'} ({c.confidence:.0%})" if c.confidence else (c.detected_class or "Manual")
        worker_str = f"Worker #{c.assigned_worker_id}" if c.assigned_worker_id else "Unassigned"
        date_str = c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else ""
        rows.append([
            c.complaint_id,
            c.issue_type.replace("_", " ").title(),
            c.severity,
            c.status,
            coords,
            ai_info,
            worker_str,
            date_str
        ])
    pdf_bytes = _build_pdf_document(
        title="Municipal Complaints Master Audit",
        subtitle="Real-time report of reported road hazards, verification statuses, and maintenance lifecycles",
        headers=headers,
        data_rows=rows
    )
    filename = f"visionguard_complaints_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export-detections-csv")
def export_detections_csv(db: Session = Depends(get_db)):
    """Export AI detection logs to CSV format."""
    detections = db.query(Detection).order_by(Detection.created_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Detection ID", "AI Model", "Detected Class", "Confidence", "Source Type",
        "Latitude", "Longitude", "User ID", "Complaint ID", "Created At"
    ])
    for d in detections:
        writer.writerow([
            d.id, d.ai_model or "", d.detected_class or "", d.confidence or "",
            d.source_type or "IMAGE", d.latitude or "", d.longitude or "",
            d.user_id or "", d.complaint_id or "",
            d.created_at.strftime("%Y-%m-%d %H:%M:%S") if d.created_at else ""
        ])
    output.seek(0)
    filename = f"visionguard_detections_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export-detections-pdf")
def export_detections_pdf(db: Session = Depends(get_db)):
    """Export AI detection logs in high-resolution PDF."""
    detections = db.query(Detection).order_by(Detection.created_at.desc()).all()
    headers = ["ID", "AI Model", "Detected Class", "Confidence", "Source", "GPS Coordinates", "Linked CMP", "Date"]
    rows = []
    for d in detections:
        coords = f"{d.latitude:.4f}, {d.longitude:.4f}" if d.latitude and d.longitude else "N/A"
        cmp_str = f"CMP #{d.complaint_id}" if d.complaint_id else "Unlinked"
        date_str = d.created_at.strftime("%Y-%m-%d %H:%M") if d.created_at else ""
        rows.append([
            f"DET-{d.id}",
            (d.ai_model or "").replace("_", " ").title(),
            d.detected_class or "",
            f"{d.confidence:.1%}" if d.confidence else "N/A",
            d.source_type or "IMAGE",
            coords,
            cmp_str,
            date_str
        ])
    pdf_bytes = _build_pdf_document(
        title="AI Diagnostics & Computer Vision Detection Logs",
        subtitle="Complete database audit of inferences across Traffic Signs, Road Damage, Signals, and Condition Classifiers",
        headers=headers,
        data_rows=rows
    )
    filename = f"visionguard_detections_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export-workers-csv")
def export_workers_csv(db: Session = Depends(get_db)):
    """Export field worker activity and task assignments to CSV format."""
    workers = db.query(Worker).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Worker ID", "Employee ID", "Full Name", "Email", "Department",
        "Specialization", "Active Status", "Assigned Tasks", "In Progress", "Completed", "Created At"
    ])
    for w in workers:
        u = w.user
        assigned_cnt = db.query(Complaint).filter(Complaint.assigned_worker_id == w.id, Complaint.status == "ASSIGNED").count()
        in_prog_cnt = db.query(Complaint).filter(Complaint.assigned_worker_id == w.id, Complaint.status == "IN_PROGRESS").count()
        comp_cnt = db.query(Complaint).filter(Complaint.assigned_worker_id == w.id, Complaint.status == "COMPLETED").count()
        writer.writerow([
            w.id, w.employee_id, u.full_name if u else "", u.email if u else "",
            w.department, w.specialization or "General Maintenance",
            "Active" if w.is_active else "Inactive",
            assigned_cnt, in_prog_cnt, comp_cnt,
            w.created_at.strftime("%Y-%m-%d %H:%M:%S") if w.created_at else ""
        ])
    output.seek(0)
    filename = f"visionguard_workers_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export-workers-pdf")
def export_workers_pdf(db: Session = Depends(get_db)):
    """Export field worker activity report in high-resolution PDF."""
    workers = db.query(Worker).all()
    headers = ["ID", "Employee ID", "Staff Name", "Department", "Specialization", "Assigned", "In Progress", "Completed", "Status"]
    rows = []
    for w in workers:
        u = w.user
        assigned_cnt = db.query(Complaint).filter(Complaint.assigned_worker_id == w.id, Complaint.status == "ASSIGNED").count()
        in_prog_cnt = db.query(Complaint).filter(Complaint.assigned_worker_id == w.id, Complaint.status == "IN_PROGRESS").count()
        comp_cnt = db.query(Complaint).filter(Complaint.assigned_worker_id == w.id, Complaint.status == "COMPLETED").count()
        rows.append([
            f"W-{w.id}",
            w.employee_id,
            u.full_name if u else "N/A",
            w.department,
            w.specialization or "General",
            str(assigned_cnt),
            str(in_prog_cnt),
            str(comp_cnt),
            "Active" if w.is_active else "Inactive"
        ])
    pdf_bytes = _build_pdf_document(
        title="Field Worker Dispatch & Activity Audit",
        subtitle="Municipal workforce allocation, active work order status, and completion benchmarks",
        headers=headers,
        data_rows=rows
    )
    filename = f"visionguard_workers_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/historical")
def get_historical_analytics(
    days: int = Query(30, ge=1, le=365, description="Number of historical days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Generate dynamic, real-time analytics from database records.
    Returns 0/empty-states cleanly if no records exist.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # 1. Total detections count (All time vs In Period)
    total_detections_all_time = db.query(Detection).count()
    total_detections_period = db.query(Detection).filter(Detection.created_at >= cutoff_date).count()

    # 2. Detections by AI Model
    model_rows = db.query(
        Detection.ai_model,
        func.count(Detection.id).label("count")
    ).group_by(Detection.ai_model).all()
    detections_by_model = {row.ai_model: row.count for row in model_rows}

    # 3. Detections by Source Type (IMAGE, WEBCAM, VIDEO)
    source_rows = db.query(
        Detection.source_type,
        func.count(Detection.id).label("count")
    ).group_by(Detection.source_type).all()
    detections_by_source = {row.source_type: row.count for row in source_rows}

    # 4. Detections by Detected Class (Top classes across all models)
    class_rows = db.query(
        Detection.detected_class,
        func.count(Detection.id).label("count"),
        func.avg(Detection.confidence).label("avg_conf")
    ).group_by(Detection.detected_class).order_by(desc("count")).limit(12).all()

    top_classes = [
        {
            "class_name": r.detected_class,
            "count": r.count,
            "avg_confidence": round(float(r.avg_conf or 0.0), 4)
        }
        for r in class_rows
    ]

    # 5. Temporal Detections Over Time (Daily breakdown over last N days)
    # Using SQLite date function
    daily_rows = db.query(
        func.strftime("%Y-%m-%d", Detection.created_at).label("day"),
        func.count(Detection.id).label("count")
    ).filter(Detection.created_at >= cutoff_date).group_by("day").order_by("day").all()

    # Generate complete daily series
    timeline_dict = {r.day: r.count for r in daily_rows}
    timeline = []
    curr = cutoff_date.date()
    today = datetime.utcnow().date()
    while curr <= today:
        d_str = curr.strftime("%Y-%m-%d")
        timeline.append({
            "date": d_str,
            "count": timeline_dict.get(d_str, 0)
        })
        curr += timedelta(days=1)

    # 6. Specific Domain Distributions from Detections & Complaints
    # Road Damage distribution
    rd_rows = db.query(
        Detection.detected_class,
        func.count(Detection.id).label("count")
    ).filter(
        Detection.ai_model.ilike("%Road Damage%")
    ).group_by(Detection.detected_class).all()
    road_damage_dist = {r.detected_class: r.count for r in rd_rows}

    # Traffic Sign distribution
    ts_rows = db.query(
        Detection.detected_class,
        func.count(Detection.id).label("count")
    ).filter(
        Detection.ai_model.ilike("%Traffic Sign%")
    ).group_by(Detection.detected_class).all()
    traffic_sign_dist = {r.detected_class: r.count for r in ts_rows}

    # Traffic Signal distribution
    sig_rows = db.query(
        Detection.detected_class,
        func.count(Detection.id).label("count")
    ).filter(
        Detection.ai_model.ilike("%Signal%")
    ).group_by(Detection.detected_class).all()
    traffic_signal_dist = {r.detected_class: r.count for r in sig_rows}

    # Sign Condition distribution (from detection classes or sign condition model)
    sc_rows = db.query(
        Detection.detected_class,
        func.count(Detection.id).label("count")
    ).filter(
        Detection.ai_model.ilike("%Condition%")
    ).group_by(Detection.detected_class).all()
    sign_condition_dist = {r.detected_class: r.count for r in sc_rows}

    # 7. Complaints summary metrics
    total_complaints = db.query(Complaint).count()
    complaints_by_status = {
        status_val: db.query(Complaint).filter(Complaint.status == status_val).count()
        for status_val in ["SUBMITTED", "VERIFIED", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "REJECTED", "REOPENED"]
    }

    return {
        "status": "success",
        "days_window": days,
        "summary": {
            "total_detections_all_time": total_detections_all_time,
            "total_detections_in_window": total_detections_period,
            "total_complaints_all_time": total_complaints,
            "resolved_complaints": complaints_by_status.get("COMPLETED", 0)
        },
        "detections_by_model": detections_by_model,
        "detections_by_source": detections_by_source,
        "top_detected_classes": top_classes,
        "timeline_daily": timeline,
        "domain_distributions": {
            "road_damage": road_damage_dist,
            "traffic_signs": traffic_sign_dist,
            "traffic_signals": traffic_signal_dist,
            "sign_condition": sign_condition_dist
        },
        "complaints_by_status": complaints_by_status
    }
