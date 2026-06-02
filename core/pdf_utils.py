"""
core/pdf_utils.py
=================
PDF report generation using ReportLab.
Generates branded attendance reports for individual students or departments.
"""
import io
from datetime import date, timedelta

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph,
        Spacer, HRFlowable, KeepTogether
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# ── Brand colors ─────────────────────────────────────────────────────────────
PRIMARY = colors.HexColor('#6366f1')
ACCENT  = colors.HexColor('#06b6d4')
GREEN   = colors.HexColor('#10b981')
RED     = colors.HexColor('#ef4444')
AMBER   = colors.HexColor('#f59e0b')
DARK    = colors.HexColor('#1e1b4b')
BG      = colors.HexColor('#f8f9ff')
MID     = colors.HexColor('#e8eaf6')


def pdf_available() -> bool:
    return REPORTLAB_AVAILABLE


def _header_footer(canvas, doc):
    """Draw page header and footer on every page."""
    canvas.saveState()
    w, h = A4

    # Header bar
    canvas.setFillColor(DARK)
    canvas.rect(0, h - 2*cm, w, 2*cm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica-Bold', 14)
    canvas.drawString(1.5*cm, h - 1.3*cm, '🎓 FaceAttend AI')
    canvas.setFont('Helvetica', 9)
    canvas.drawRightString(w - 1.5*cm, h - 1.3*cm, f'Attendance Report — Generated {date.today()}')

    # Footer
    canvas.setFillColor(colors.HexColor('#9ca3af'))
    canvas.setFont('Helvetica', 8)
    canvas.drawString(1.5*cm, 0.8*cm, 'Confidential — AI Face Attendance Management System')
    canvas.drawRightString(w - 1.5*cm, 0.8*cm, f'Page {doc.page}')

    canvas.restoreState()


def generate_student_pdf(student, start_date: date, end_date: date) -> bytes:
    """
    Generate a detailed PDF attendance report for a single student.
    Returns PDF bytes.
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError('ReportLab is not installed.')

    from .models import Attendance

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=2.5*cm, bottomMargin=1.8*cm,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        title=f'Attendance Report — {student.name}',
        author='FaceAttend AI'
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Student Info Card ────────────────────────────────────────────────────
    name_style = ParagraphStyle(
        'Name', fontName='Helvetica-Bold', fontSize=20,
        textColor=DARK, spaceAfter=4
    )
    sub_style = ParagraphStyle(
        'Sub', fontName='Helvetica', fontSize=10,
        textColor=colors.HexColor('#6b7280'), spaceAfter=2
    )

    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(student.name, name_style))
    story.append(Paragraph(f'Student ID: {student.student_id}', sub_style))
    story.append(Paragraph(f'Department: {student.department_display}  |  Year: {student.year}', sub_style))
    story.append(Paragraph(f'Email: {student.email}', sub_style))
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width='100%', thickness=1, color=PRIMARY, spaceAfter=12))

    # ── Period Summary ────────────────────────────────────────────────────────
    attendances = Attendance.objects.filter(
        student=student, date__gte=start_date, date__lte=end_date
    ).order_by('date')

    total_days = (end_date - start_date).days + 1
    present_days = attendances.filter(status__in=['present', 'late']).count()
    absent_days = total_days - present_days
    late_days = attendances.filter(status='late').count()
    pct = round((present_days / total_days * 100) if total_days else 0, 1)

    period_style = ParagraphStyle(
        'Period', fontName='Helvetica-Bold', fontSize=11,
        textColor=PRIMARY, spaceAfter=8
    )
    story.append(Paragraph(f'Report Period: {start_date} to {end_date}', period_style))

    # Summary stats table
    pct_color = GREEN if pct >= 75 else (AMBER if pct >= 50 else RED)
    summary_data = [
        ['Total Days', 'Present', 'Absent', 'Late', 'Attendance %'],
        [str(total_days), str(present_days), str(absent_days), str(late_days), f'{pct}%'],
    ]
    summary_table = Table(summary_data, colWidths=[3*cm, 3*cm, 3*cm, 3*cm, 3.5*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWHEIGHT', (0, 0), (-1, -1), 0.7*cm),
        ('BACKGROUND', (0, 1), (-1, 1), BG),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 12),
        ('TEXTCOLOR', (4, 1), (4, 1), pct_color),
        ('BOX', (0, 0), (-1, -1), 1, PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.5*cm))

    # ── Detailed Log Table ────────────────────────────────────────────────────
    detail_style = ParagraphStyle(
        'Detail', fontName='Helvetica-Bold', fontSize=11,
        textColor=PRIMARY, spaceAfter=8
    )
    story.append(Paragraph('Detailed Attendance Log', detail_style))

    rows = [['#', 'Date', 'Day', 'Time In', 'Status', 'Confidence']]
    for i, att in enumerate(attendances, 1):
        status_text = att.status.capitalize()
        rows.append([
            str(i),
            str(att.date),
            att.date.strftime('%A'),
            att.time_in.strftime('%H:%M') if att.time_in else '—',
            status_text,
            f'{att.confidence_percent}%',
        ])

    detail_table = Table(rows, colWidths=[1*cm, 3*cm, 3*cm, 3*cm, 2.5*cm, 2.5*cm])
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWHEIGHT', (0, 0), (-1, -1), 0.6*cm),
        ('BOX', (0, 0), (-1, -1), 0.5, PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, MID]),
    ]
    # Color status cells
    for i, att in enumerate(attendances, 1):
        color = GREEN if att.status == 'present' else (AMBER if att.status == 'late' else RED)
        style.append(('TEXTCOLOR', (4, i), (4, i), color))
        style.append(('FONTNAME', (4, i), (4, i), 'Helvetica-Bold'))

    detail_table.setStyle(TableStyle(style))
    story.append(detail_table)
    story.append(Spacer(1, 1*cm))

    # Build PDF
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()


def generate_department_pdf(department: str, dept_label: str, start_date: date, end_date: date) -> bytes:
    """
    Generate a PDF summary report for all students in a department.
    Returns PDF bytes.
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError('ReportLab is not installed.')

    from .models import Student, Attendance

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=2.5*cm, bottomMargin=1.8*cm,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        title=f'Department Report — {dept_label}',
        author='FaceAttend AI'
    )

    styles = getSampleStyleSheet()
    story = []

    heading_style = ParagraphStyle(
        'Heading', fontName='Helvetica-Bold', fontSize=18,
        textColor=DARK, spaceAfter=6
    )
    sub_style = ParagraphStyle(
        'Sub', fontName='Helvetica', fontSize=10,
        textColor=colors.HexColor('#6b7280'), spaceAfter=4
    )

    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(f'Department: {dept_label}', heading_style))
    story.append(Paragraph(f'Report Period: {start_date} to {end_date}', sub_style))
    story.append(HRFlowable(width='100%', thickness=1, color=PRIMARY, spaceAfter=12))

    students = Student.objects.filter(is_active=True, department=department).order_by('name')
    total_days = (end_date - start_date).days + 1

    rows = [['#', 'Student ID', 'Name', 'Year', 'Present', 'Absent', 'Late', '%']]
    for i, student in enumerate(students, 1):
        atts = Attendance.objects.filter(
            student=student, date__gte=start_date, date__lte=end_date
        )
        present = atts.filter(status__in=['present', 'late']).count()
        late = atts.filter(status='late').count()
        absent = total_days - present
        pct = round((present / total_days * 100) if total_days else 0, 1)
        rows.append([
            str(i), student.student_id, student.name, str(student.year),
            str(present), str(absent), str(late), f'{pct}%'
        ])

    table = Table(rows, colWidths=[0.8*cm, 2.5*cm, 4.5*cm, 1.2*cm, 1.5*cm, 1.5*cm, 1.2*cm, 1.5*cm])
    tstyle = [
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWHEIGHT', (0, 0), (-1, -1), 0.6*cm),
        ('BOX', (0, 0), (-1, -1), 0.5, PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e5e7eb')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, MID]),
    ]
    for i, student in enumerate(students, 1):
        atts = Attendance.objects.filter(student=student, date__gte=start_date, date__lte=end_date)
        present = atts.filter(status__in=['present', 'late']).count()
        pct = round((present / total_days * 100) if total_days else 0, 1)
        color = GREEN if pct >= 75 else (AMBER if pct >= 50 else RED)
        tstyle.append(('TEXTCOLOR', (7, i), (7, i), color))
        tstyle.append(('FONTNAME', (7, i), (7, i), 'Helvetica-Bold'))

    table.setStyle(TableStyle(tstyle))
    story.append(table)
    story.append(Spacer(1, 0.8*cm))

    total_students = students.count()
    dept_style = ParagraphStyle('Dept', fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#9ca3af'))
    story.append(Paragraph(f'Total students in {dept_label}: {total_students}', dept_style))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
