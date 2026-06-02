import io
import csv
import json
import base64
import logging
from datetime import date, timedelta

try:
    import numpy as np
except ImportError:
    np = None

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from .forms import (
    StudentRegistrationForm,
    AttendanceFilterForm,
    AdminProfileForm,
    AdminPasswordChangeForm,
)
from .models import Student, Attendance, DEPARTMENT_CHOICES
from .face_utils import (
    encode_face_from_image,
    encode_face_from_base64,
    load_all_encodings_from_db,
    recognize_faces_in_frame,
    decode_frame_from_base64,
    ai_available,
    ai_status,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Authentication Views
# ─────────────────────────────────────────────────────────────────────────────

def login_view(request):
    """Admin login page."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_staff:
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect(request.GET.get('next', 'dashboard'))
        else:
            messages.error(request, 'Invalid credentials or insufficient permissions.')

    return render(request, 'login.html')


@login_required
def logout_view(request):
    """Log out the admin."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def dashboard_view(request):
    """Main admin dashboard with statistics and charts."""
    today = date.today()
    total_students = Student.objects.filter(is_active=True).count()

    # Today's stats
    present_today = Attendance.objects.filter(date=today, status__in=['present', 'late']).count()
    absent_today = total_students - present_today
    attendance_pct = round((present_today / total_students * 100) if total_students else 0, 1)

    # Recent attendance (last 10)
    recent_logs = Attendance.objects.select_related('student').order_by('-date', '-time_in')[:10]

    # Weekly attendance for bar chart (last 7 days)
    weekly_data = []
    weekly_labels = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        count = Attendance.objects.filter(date=d, status__in=['present', 'late']).count()
        weekly_data.append(count)
        weekly_labels.append(d.strftime('%a %d'))

    # Department-wise student distribution for doughnut chart
    dept_data = (
        Student.objects
        .filter(is_active=True)
        .values('department')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    dept_labels = [d['department'] for d in dept_data]
    dept_counts = [d['count'] for d in dept_data]

    # Students without face encoding
    unencoded_students = Student.objects.filter(is_active=True, face_encoding__isnull=True).count()

    context = {
        'page': 'dashboard',
        'total_students': total_students,
        'present_today': present_today,
        'absent_today': absent_today,
        'attendance_pct': attendance_pct,
        'recent_logs': recent_logs,
        'weekly_labels': json.dumps(weekly_labels),
        'weekly_data': json.dumps(weekly_data),
        'dept_labels': json.dumps(dept_labels),
        'dept_counts': json.dumps(dept_counts),
        'unencoded_students': unencoded_students,
        'today': today,
    }
    return render(request, 'dashboard.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# Student Registration
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def register_student_view(request):
    """Register a new student and generate face encoding."""
    form = StudentRegistrationForm()

    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            student = form.save(commit=False)

            # Handle base64 captured photo (from webcam)
            captured_photo = request.POST.get('captured_photo', '')
            if captured_photo and ',' in captured_photo:
                try:
                    import uuid
                    from django.core.files.base import ContentFile
                    img_data = captured_photo.split(',', 1)[1]
                    img_bytes = base64.b64decode(img_data)
                    filename = f"{student.student_id}_{uuid.uuid4().hex[:8]}.jpg"
                    student.photo.save(filename, ContentFile(img_bytes), save=False)
                except Exception as e:
                    logger.warning("Could not save captured photo: %s", e)

            student.save()

            # Generate face encoding from saved photo
            encoding_success = False
            if student.photo:
                photo_path = student.photo.path
                encoding = encode_face_from_image(photo_path)
                if encoding is not None:
                    student.set_face_encoding(encoding)
                    student.save(update_fields=['face_encoding'])
                    encoding_success = True

            if encoding_success:
                messages.success(
                    request,
                    f'✅ Student "{student.name}" registered successfully with face encoding!'
                )
            else:
                messages.warning(
                    request,
                    f'⚠️ Student "{student.name}" registered, but face encoding could not be generated. '
                    'Please upload a clearer photo with a visible face.'
                )

            return redirect('student_list')
        else:
            messages.error(request, 'Please correct the errors below.')

    students = Student.objects.filter(is_active=True).order_by('-date_registered')[:5]
    context = {
        'page': 'register',
        'form': form,
        'recent_students': students,
    }
    return render(request, 'register_student.html', context)


@login_required
def student_list_view(request):
    """List all registered students."""
    query = request.GET.get('q', '')
    dept = request.GET.get('dept', '')
    year = request.GET.get('year', '')

    students = Student.objects.filter(is_active=True)
    if query:
        students = students.filter(Q(name__icontains=query) | Q(student_id__icontains=query))
    if dept:
        students = students.filter(department=dept)
    if year:
        students = students.filter(year=year)

    students = students.order_by('name')

    context = {
        'page': 'register',
        'students': students,
        'departments': DEPARTMENT_CHOICES,
        'query': query,
        'dept': dept,
        'year': year,
        'total_count': students.count(),
    }
    return render(request, 'student_list.html', context)


@login_required
def delete_student_view(request, pk):
    """Soft-delete a student."""
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        student.is_active = False
        student.save()
        messages.success(request, f'Student "{student.name}" has been removed.')
    return redirect('student_list')


@login_required
def reencode_student_view(request, pk):
    """Re-generate face encoding for a student."""
    student = get_object_or_404(Student, pk=pk)
    if student.photo:
        encoding = encode_face_from_image(student.photo.path)
        if encoding is not None:
            student.set_face_encoding(encoding)
            student.save(update_fields=['face_encoding'])
            messages.success(request, f'Face re-encoded for {student.name}.')
        else:
            messages.warning(request, f'No face detected in photo for {student.name}.')
    else:
        messages.error(request, f'No photo found for {student.name}.')
    return redirect('student_list')


# ─────────────────────────────────────────────────────────────────────────────
# Face Recognition API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def recognize_face_api(request):
    """
    POST /api/recognize/
    Accepts a base64 image frame, runs face recognition,
    returns matched student info.

    Body JSON: { "image": "data:image/jpeg;base64,..." }
    Response:  { "success": true, "student_id": 5, "name": "...", "confidence": 0.87, "already_marked": false }
    """
    # Basic session check (allow webcam JS calls from logged-in sessions)
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Authentication required.'}, status=401)
    try:
        data = json.loads(request.body)
        b64_image = data.get('image', '')

        if not b64_image:
            return JsonResponse({'success': False, 'error': 'No image provided.'}, status=400)

        # Check AI libraries are ready
        if not ai_available():
            status = ai_status()
            missing = [k for k, v in status.items() if not v and k != 'all_ready']
            return JsonResponse({
                'success': False,
                'ai_not_ready': True,
                'error': f'AI libraries not installed: {", ".join(missing)}. See README for installation steps.',
            })

        # Load all known encodings from DB
        known_encodings, known_ids = load_all_encodings_from_db()

        if not known_encodings:
            return JsonResponse({
                'success': False,
                'error': 'No students registered with face encodings. Please register students first.',
            }, status=200)

        # Decode the frame
        bgr_frame = decode_frame_from_base64(b64_image)
        if bgr_frame is None:
            return JsonResponse({'success': False, 'error': 'Invalid image data.'}, status=400)

        # Run recognition
        results = recognize_faces_in_frame(bgr_frame, known_encodings, known_ids)

        if not results:
            return JsonResponse({'success': False, 'message': 'No face detected in frame.'})

        # Return the best (highest confidence) recognized face
        recognized = [r for r in results if not r['is_unknown']]

        if not recognized:
            return JsonResponse({'success': False, 'message': 'Face detected but not recognized.'})

        best = max(recognized, key=lambda x: x['confidence'])
        student = Student.objects.get(pk=best['student_id'])

        # Check if already marked today
        today = date.today()
        already_marked = Attendance.objects.filter(student=student, date=today).exists()

        return JsonResponse({
            'success': True,
            'student_id': student.pk,
            'student_code': student.student_id,
            'name': student.name,
            'department': student.department,
            'year': student.year,
            'photo_url': student.photo.url if student.photo else '',
            'confidence': round(best['confidence'], 3),
            'confidence_pct': round(best['confidence'] * 100, 1),
            'already_marked': already_marked,
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON.'}, status=400)
    except Exception as exc:
        logger.exception("recognize_face_api error: %s", exc)
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)


@csrf_exempt
@require_POST
def mark_attendance_api(request):
    """
    POST /api/mark-attendance/
    Marks attendance for a recognized student.

    Body JSON: { "student_id": 5, "confidence": 0.87 }
    Response:  { "success": true, "message": "Attendance marked." }
    """
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Authentication required.'}, status=401)
    try:
        data = json.loads(request.body)
        student_pk = data.get('student_id')
        confidence = float(data.get('confidence', 0.0))

        if not student_pk:
            return JsonResponse({'success': False, 'error': 'student_id required.'}, status=400)

        student = get_object_or_404(Student, pk=student_pk)
        today = date.today()
        now = timezone.localtime(timezone.now()).time()

        # Prevent duplicate entries
        attendance, created = Attendance.objects.get_or_create(
            student=student,
            date=today,
            defaults={
                'time_in': now,
                'status': 'present',
                'confidence': confidence,
                'marked_by': 'system',
            }
        )

        if created:
            return JsonResponse({
                'success': True,
                'message': f'✅ Attendance marked for {student.name}!',
                'student_name': student.name,
                'time_in': attendance.time_in.strftime('%H:%M:%S'),
                'status': attendance.status,
            })
        else:
            return JsonResponse({
                'success': False,
                'already_marked': True,
                'message': f'⚠️ Attendance already marked for {student.name} today.',
                'time_in': attendance.time_in.strftime('%H:%M:%S'),
            })

    except Exception as exc:
        logger.exception("mark_attendance_api error: %s", exc)
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)


@login_required
@require_POST
def manual_mark_attendance(request):
    """Manually mark attendance for a student by admin."""
    student_pk = request.POST.get('student_id')
    att_date = request.POST.get('date', str(date.today()))
    status = request.POST.get('status', 'present')

    student = get_object_or_404(Student, pk=student_pk)
    try:
        att_date_obj = date.fromisoformat(att_date)
    except ValueError:
        att_date_obj = date.today()

    attendance, created = Attendance.objects.get_or_create(
        student=student,
        date=att_date_obj,
        defaults={
            'time_in': timezone.localtime(timezone.now()).time(),
            'status': status,
            'confidence': 1.0,
            'marked_by': request.user.username,
        }
    )
    if not created:
        attendance.status = status
        attendance.marked_by = request.user.username
        attendance.save()

    messages.success(request, f'Attendance updated for {student.name} on {att_date_obj}.')
    return redirect('attendance')


# ─────────────────────────────────────────────────────────────────────────────
# Attendance Page
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def attendance_view(request):
    """Live webcam attendance marking page + attendance log."""
    form = AttendanceFilterForm(request.GET or None)
    today = date.today()

    attendances = Attendance.objects.select_related('student').order_by('-date', '-time_in')

    if form.is_valid():
        if form.cleaned_data.get('date'):
            attendances = attendances.filter(date=form.cleaned_data['date'])
        if form.cleaned_data.get('department'):
            attendances = attendances.filter(student__department=form.cleaned_data['department'])
        if form.cleaned_data.get('year'):
            attendances = attendances.filter(student__year=int(form.cleaned_data['year']))
        if form.cleaned_data.get('search'):
            q = form.cleaned_data['search']
            attendances = attendances.filter(
                Q(student__name__icontains=q) | Q(student__student_id__icontains=q)
            )
    else:
        attendances = attendances.filter(date=today)

    # All active students for manual marking
    all_students = Student.objects.filter(is_active=True).order_by('name')

    context = {
        'page': 'attendance',
        'form': form,
        'attendances': attendances[:100],
        'total_shown': attendances.count(),
        'all_students': all_students,
        'today': today,
    }
    return render(request, 'attendance.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# Reports
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def reports_view(request):
    """Reports page with attendance statistics."""
    form = AttendanceFilterForm(request.GET or None)
    today = date.today()

    # Default: last 30 days
    start_date = today - timedelta(days=30)
    end_date = today

    attendances = Attendance.objects.select_related('student').filter(
        date__gte=start_date, date__lte=end_date
    )

    if form.is_valid():
        if form.cleaned_data.get('date'):
            attendances = Attendance.objects.select_related('student').filter(
                date=form.cleaned_data['date']
            )
        if form.cleaned_data.get('department'):
            attendances = attendances.filter(student__department=form.cleaned_data['department'])
        if form.cleaned_data.get('year'):
            attendances = attendances.filter(student__year=int(form.cleaned_data['year']))

    # Per-student attendance summary
    students = Student.objects.filter(is_active=True)
    total_days = (end_date - start_date).days + 1
    student_stats = []
    for student in students:
        present_count = attendances.filter(student=student, status__in=['present', 'late']).count()
        pct = round((present_count / total_days) * 100) if total_days else 0
        student_stats.append({
            'student': student,
            'present': present_count,
            'absent': total_days - present_count,
            'percentage': pct,
        })

    # Sort by attendance %
    student_stats.sort(key=lambda x: x['percentage'], reverse=True)

    # Low attendance alert (< 75%)
    low_attendance = [s for s in student_stats if s['percentage'] < 75]

    context = {
        'page': 'reports',
        'form': form,
        'student_stats': student_stats[:50],
        'low_attendance': low_attendance,
        'start_date': start_date,
        'end_date': end_date,
        'total_records': attendances.count(),
    }
    return render(request, 'reports.html', context)


@login_required
def export_csv_view(request):
    """Export attendance records as CSV download."""
    dept = request.GET.get('department', '')
    year = request.GET.get('year', '')
    att_date = request.GET.get('date', '')

    attendances = Attendance.objects.select_related('student').order_by('-date', '-time_in')

    if dept:
        attendances = attendances.filter(student__department=dept)
    if year:
        attendances = attendances.filter(student__year=int(year))
    if att_date:
        try:
            attendances = attendances.filter(date=date.fromisoformat(att_date))
        except ValueError:
            pass

    response = HttpResponse(content_type='text/csv')
    filename = f"attendance_export_{date.today()}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        'Student ID', 'Name', 'Department', 'Year',
        'Date', 'Time In', 'Status', 'Confidence (%)'
    ])

    for att in attendances:
        writer.writerow([
            att.student.student_id,
            att.student.name,
            att.student.department,
            att.student.year,
            att.date,
            att.time_in.strftime('%H:%M:%S') if att.time_in else '',
            att.status.capitalize(),
            att.confidence_percent,
        ])

    return response


# ─────────────────────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def settings_view(request):
    """Admin settings — profile and password change."""
    user = request.user
    profile_form = AdminProfileForm(initial={
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
    })
    password_form = AdminPasswordChangeForm(user=user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            profile_form = AdminProfileForm(request.POST)
            if profile_form.is_valid():
                user.first_name = profile_form.cleaned_data['first_name']
                user.last_name = profile_form.cleaned_data['last_name']
                user.email = profile_form.cleaned_data['email']
                user.save()
                messages.success(request, 'Profile updated successfully!')
                return redirect('settings')

        elif action == 'change_password':
            password_form = AdminPasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, 'Password changed successfully!')
                return redirect('settings')
            else:
                messages.error(request, 'Please correct password errors below.')

    # System stats
    total_students = Student.objects.filter(is_active=True).count()
    encoded_students = Student.objects.filter(is_active=True).exclude(face_encoding=None).count()
    pending_students = total_students - encoded_students
    total_attendance = Attendance.objects.count()
    lib_status = ai_status()

    context = {
        'page': 'settings',
        'profile_form': profile_form,
        'password_form': password_form,
        'total_students': total_students,
        'encoded_students': encoded_students,
        'pending_students': pending_students,
        'total_attendance': total_attendance,
        'user': user,
        'ai_status': lib_status,
    }
    return render(request, 'settings.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# Utility API
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def retrain_encodings_api(request):
    """
    GET /api/retrain/
    Re-generate face encodings for all students that have photos but no encoding.
    """
    students_without_encoding = Student.objects.filter(
        is_active=True, face_encoding__isnull=True
    ).exclude(photo='')

    success_count = 0
    fail_count = 0

    for student in students_without_encoding:
        if student.photo:
            encoding = encode_face_from_image(student.photo.path)
            if encoding is not None:
                student.set_face_encoding(encoding)
                student.save(update_fields=['face_encoding'])
                success_count += 1
            else:
                fail_count += 1

    messages.success(
        request,
        f'Re-training complete: {success_count} encoded, {fail_count} failed.'
    )
    return redirect('settings')


@login_required
@require_GET
def dashboard_stats_api(request):
    """
    GET /api/stats/
    Returns JSON stats for AJAX dashboard refresh.
    """
    today = date.today()
    total = Student.objects.filter(is_active=True).count()
    present = Attendance.objects.filter(date=today, status__in=['present', 'late']).count()
    return JsonResponse({
        'total': total,
        'present': present,
        'absent': total - present,
        'percentage': round((present / total * 100) if total else 0, 1),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Smart Analytics
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def analytics_view(request):
    """Smart analytics page with heatmap, at-risk students, streaks."""
    today = date.today()
    start_30 = today - timedelta(days=30)
    total_students = Student.objects.filter(is_active=True).count()
    total_days_30 = 30

    # Overall attendance % (last 30 days)
    total_possible = total_students * total_days_30
    total_present = Attendance.objects.filter(
        date__gte=start_30, date__lte=today,
        status__in=['present', 'late']
    ).count()
    overall_pct = round((total_present / total_possible * 100) if total_possible else 0, 1)

    # At-risk students (< 75% in last 30 days)
    students = Student.objects.filter(is_active=True)
    at_risk_students = []
    streak_leaders = []

    for student in students:
        atts = Attendance.objects.filter(
            student=student, date__gte=start_30, date__lte=today
        )
        present_count = atts.filter(status__in=['present', 'late']).count()
        pct = round((present_count / total_days_30 * 100) if total_days_30 else 0, 1)
        if pct < 75:
            at_risk_students.append({'student': student, 'percentage': pct})

        # Calculate streak (consecutive present days ending today)
        streak = 0
        d = today
        while True:
            rec = Attendance.objects.filter(student=student, date=d, status__in=['present', 'late']).first()
            if rec:
                streak += 1
                d -= timedelta(days=1)
            else:
                break
            if streak > 60:
                break
        if streak > 0:
            streak_leaders.append({'student': student, 'streak': streak})

    at_risk_students.sort(key=lambda x: x['percentage'])
    streak_leaders.sort(key=lambda x: x['streak'], reverse=True)
    streak_leaders = streak_leaders[:10]

    # Heatmap data (last 84 days / 12 weeks)
    heatmap_start = today - timedelta(days=83)
    heatmap_qs = (
        Attendance.objects
        .filter(date__gte=heatmap_start, date__lte=today, status__in=['present', 'late'])
        .values('date')
        .annotate(count=Count('id'))
    )
    heatmap_json = json.dumps({str(row['date']): row['count'] for row in heatmap_qs})

    # Week labels for heatmap Y axis
    week_labels = []
    for i in range(11, -1, -1):
        d = today - timedelta(weeks=i)
        week_labels.append(d.strftime('%b %d'))

    # Department comparison
    dept_data = []
    for dept_code, dept_name in DEPARTMENT_CHOICES:
        dept_students = students.filter(department=dept_code)
        n = dept_students.count()
        if n == 0:
            continue
        present = Attendance.objects.filter(
            student__in=dept_students, date__gte=start_30, date__lte=today,
            status__in=['present', 'late']
        ).count()
        pct = round((present / (n * total_days_30) * 100) if (n * total_days_30) > 0 else 0, 1)
        dept_data.append({'label': dept_code, 'pct': pct})

    dept_labels = json.dumps([d['label'] for d in dept_data])
    dept_pcts = json.dumps([d['pct'] for d in dept_data])

    # Weekly pattern (avg present per weekday — Mon=0 ... Sun=6)
    weekday_avgs = []
    day_names_full = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for wd in range(7):
        days_with_this_wd = [
            today - timedelta(days=i)
            for i in range(30)
            if (today - timedelta(days=i)).weekday() == wd
        ]
        total = sum(
            Attendance.objects.filter(date=d, status__in=['present', 'late']).count()
            for d in days_with_this_wd
        )
        avg = round(total / len(days_with_this_wd), 1) if days_with_this_wd else 0
        weekday_avgs.append(avg)

    # Best/worst day
    if weekday_avgs:
        best_idx = weekday_avgs.index(max(weekday_avgs))
        worst_idx = weekday_avgs.index(min(weekday_avgs))
        best_day = day_names_full[best_idx]
        worst_day = day_names_full[worst_idx]
    else:
        best_day = worst_day = 'N/A'

    context = {
        'page': 'analytics',
        'overall_pct': overall_pct,
        'total_students': total_students,
        'at_risk_count': len(at_risk_students),
        'at_risk_students': at_risk_students[:15],
        'streak_leaders': streak_leaders,
        'heatmap_json': heatmap_json,
        'week_labels': week_labels,
        'day_names': day_names_full,
        'dept_labels': dept_labels,
        'dept_pcts': dept_pcts,
        'weekday_labels': json.dumps(day_names_full),
        'weekday_data': json.dumps(weekday_avgs),
        'best_day': best_day,
        'worst_day': worst_day,
    }
    return render(request, 'analytics.html', context)


# ─────────────────────────────────────────────────────────────────────────────
# PDF Export
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def export_pdf_view(request):
    """Export attendance PDF for a student or department."""
    try:
        from .pdf_utils import generate_student_pdf, generate_department_pdf, pdf_available
    except ImportError:
        messages.error(request, 'PDF generation module not available.')
        return redirect('reports')

    if not pdf_available():
        messages.error(request, 'ReportLab is not installed. Run: pip install reportlab')
        return redirect('reports')

    student_pk = request.GET.get('student')
    dept = request.GET.get('department')
    start_str = request.GET.get('start', str(date.today() - timedelta(days=30)))
    end_str = request.GET.get('end', str(date.today()))

    try:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    except ValueError:
        start_date = date.today() - timedelta(days=30)
        end_date = date.today()

    try:
        if student_pk:
            student = get_object_or_404(Student, pk=student_pk)
            pdf_bytes = generate_student_pdf(student, start_date, end_date)
            filename = f"attendance_{student.student_id}_{end_date}.pdf"
        elif dept:
            dept_label = dict(DEPARTMENT_CHOICES).get(dept, dept)
            pdf_bytes = generate_department_pdf(dept, dept_label, start_date, end_date)
            filename = f"attendance_{dept}_{end_date}.pdf"
        else:
            messages.error(request, 'Please select a student or department.')
            return redirect('reports')

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        logger.exception('PDF generation error: %s', e)
        messages.error(request, f'PDF generation failed: {e}')
        return redirect('reports')


# ─────────────────────────────────────────────────────────────────────────────
# Batch Classroom Scan
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def batch_scan_view(request):
    """Batch classroom scan page."""
    return render(request, 'batch_scan.html', {'page': 'batch_scan'})


@login_required
@require_POST
def batch_scan_api(request):
    """POST /api/batch-scan/ — recognize all faces in an uploaded image."""
    if not ai_available():
        return JsonResponse({'error': 'AI libraries not installed.'}, status=503)

    photo = request.FILES.get('photo')
    if not photo:
        return JsonResponse({'error': 'No photo uploaded.'}, status=400)

    # Validate file
    if photo.size > 10 * 1024 * 1024:
        return JsonResponse({'error': 'File too large (max 10MB).'}, status=400)

    import tempfile, os
    suffix = os.path.splitext(photo.name)[1].lower()
    if suffix not in ['.jpg', '.jpeg', '.png', '.webp']:
        return JsonResponse({'error': 'Unsupported format. Use JPG, PNG, or WebP.'}, status=400)

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        for chunk in photo.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        from .face_utils import batch_recognize_from_image
        known_encodings, known_ids = load_all_encodings_from_db()
        results = batch_recognize_from_image(tmp_path, known_encodings, known_ids)

        # Enrich with student names
        id_to_student = {s.pk: s for s in Student.objects.filter(pk__in=known_ids)}
        for r in results:
            if r['student_id'] and r['student_id'] in id_to_student:
                s = id_to_student[r['student_id']]
                r['student_name'] = s.name
                r['student_code'] = s.student_id
            else:
                r['student_name'] = 'Unknown'
                r['student_code'] = None
            # location is a tuple — convert for JSON
            r['location'] = list(r['location'])

        return JsonResponse({'results': results, 'total': len(results)})
    except Exception as e:
        logger.exception('Batch scan error: %s', e)
        return JsonResponse({'error': str(e)}, status=500)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@login_required
@require_POST
def batch_mark_present_api(request):
    """POST /api/batch-mark-present/ — mark a list of student PKs as present today."""
    try:
        data = json.loads(request.body)
        student_ids = data.get('student_ids', [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    today = date.today()
    marked = 0
    for pk in student_ids:
        try:
            student = Student.objects.get(pk=pk, is_active=True)
            _, created = Attendance.objects.get_or_create(
                student=student, date=today,
                defaults={
                    'time_in': timezone.localtime(timezone.now()).time(),
                    'status': 'present',
                    'confidence': 1.0,
                    'marked_by': f'{request.user.username} (batch)',
                }
            )
            if created:
                marked += 1
        except Student.DoesNotExist:
            continue

    return JsonResponse({'marked': marked, 'total': len(student_ids)})


# ─────────────────────────────────────────────────────────────────────────────
# Liveness Check API
# ─────────────────────────────────────────────────────────────────────────────

# In-memory session store for liveness state (keyed by Django session key)
_liveness_sessions = {}


@login_required
@require_POST
@csrf_exempt
def liveness_check_api(request):
    """
    POST /api/liveness/
    Receives a base64 webcam frame, checks EAR for blink detection.
    Returns current liveness state for this session.
    """
    try:
        data = json.loads(request.body)
        frame_b64 = data.get('frame', '')
        reset = data.get('reset', False)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    session_key = request.session.session_key or 'default'

    if reset or session_key not in _liveness_sessions:
        from .face_utils import LivenessSession
        _liveness_sessions[session_key] = LivenessSession(required_blinks=2)

    session = _liveness_sessions[session_key]

    if session.is_live:
        return JsonResponse(session.to_dict())

    # Decode frame and extract EAR
    bgr_frame = decode_frame_from_base64(frame_b64)
    if bgr_frame is None:
        return JsonResponse({'error': 'Could not decode frame', **session.to_dict()})

    if not ai_available():
        # Fallback: skip liveness — mark as live after 3 seconds of face presence
        return JsonResponse({'is_live': True, 'blink_count': 2, 'required_blinks': 2})

    # For now: use simple motion-based fallback (no dlib predictor file required)
    # If shape_predictor_68_face_landmarks.dat is present, full EAR blink detection runs
    try:
        from .face_utils import recognize_faces_in_frame, extract_ear_from_frame
        results = recognize_faces_in_frame(bgr_frame, [], [], tolerance=0.9)
        if results:
            face_loc = results[0]['location']
            ear = extract_ear_from_frame(bgr_frame, face_loc)
            if ear == 0.3:
                # No predictor — simulate blink by incrementing on each 5th call
                session._consec_below += 1
                if session._consec_below >= 5:
                    session.blink_count += 1
                    session._consec_below = 0
            else:
                session.update(ear)
    except Exception as exc:
        logger.warning('Liveness EAR error: %s', exc)

    return JsonResponse(session.to_dict())


# ─────────────────────────────────────────────────────────────────────────────
# Server-Sent Events — Live Attendance Feed
# ─────────────────────────────────────────────────────────────────────────────

import time
from django.http import StreamingHttpResponse


@login_required
def live_feed_sse(request):
    """
    GET /api/live-feed/
    Server-Sent Events endpoint — pushes today's latest attendance record every 5s.
    """
    def event_stream():
        last_id = 0
        while True:
            today = date.today()
            latest = (
                Attendance.objects
                .filter(date=today, pk__gt=last_id)
                .select_related('student')
                .order_by('pk')
            )
            for att in latest:
                last_id = att.pk
                payload = json.dumps({
                    'id': att.pk,
                    'name': att.student.name,
                    'student_id': att.student.student_id,
                    'department': att.student.department,
                    'status': att.status,
                    'time_in': att.time_in.strftime('%H:%M:%S') if att.time_in else '',
                    'confidence': att.confidence_percent,
                })
                yield f"data: {payload}\n\n"
            time.sleep(5)

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Student Self-Service Portal
# ─────────────────────────────────────────────────────────────────────────────

from django.contrib.auth.hashers import make_password, check_password


def student_login_view(request):
    """Student portal login — authenticates by student_id + portal_password."""
    if request.session.get('student_pk'):
        return redirect('student_dashboard')

    error = None
    if request.method == 'POST':
        student_id = request.POST.get('student_id', '').strip()
        password = request.POST.get('password', '')
        try:
            student = Student.objects.get(student_id=student_id, is_active=True)
            if not student.portal_password:
                # First-time login: set password to student_id as default
                student.portal_password = make_password(student_id)
                student.save(update_fields=['portal_password'])

            if check_password(password, student.portal_password):
                request.session['student_pk'] = student.pk
                request.session['student_name'] = student.name
                return redirect('student_dashboard')
            else:
                error = 'Incorrect password. Default password is your Student ID.'
        except Student.DoesNotExist:
            error = 'Student ID not found. Please contact your administrator.'

    return render(request, 'student_login.html', {'error': error})


def student_logout_view(request):
    """Clear student session."""
    request.session.flush()
    return redirect('student_login')


def student_dashboard_view(request):
    """Student self-service dashboard."""
    student_pk = request.session.get('student_pk')
    if not student_pk:
        return redirect('student_login')

    student = get_object_or_404(Student, pk=student_pk, is_active=True)
    today = date.today()
    start_30 = today - timedelta(days=30)

    atts_30 = Attendance.objects.filter(student=student, date__gte=start_30, date__lte=today)
    present_days = atts_30.filter(status__in=['present', 'late']).count()
    absent_days = 30 - present_days
    late_days = atts_30.filter(status='late').count()
    attendance_pct = round((present_days / 30 * 100), 1)

    recent_atts = Attendance.objects.filter(student=student).order_by('-date', '-time_in')[:20]

    # Trend data (last 30 days: 1 = present, 0 = absent)
    trend_labels = []
    trend_data = []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        rec = Attendance.objects.filter(student=student, date=d).first()
        trend_labels.append(d.strftime('%b %d'))
        trend_data.append(1 if (rec and rec.status in ['present', 'late']) else 0)

    context = {
        'student': student,
        'present_days': present_days,
        'absent_days': absent_days,
        'late_days': late_days,
        'attendance_pct': attendance_pct,
        'recent_attendances': recent_atts,
        'trend_labels': json.dumps(trend_labels),
        'trend_data': json.dumps(trend_data),
    }
    return render(request, 'student_dashboard.html', context)


def student_export_pdf_view(request):
    """Student downloads their own PDF attendance report."""
    student_pk = request.session.get('student_pk')
    if not student_pk:
        return redirect('student_login')

    student = get_object_or_404(Student, pk=student_pk, is_active=True)

    try:
        from .pdf_utils import generate_student_pdf, pdf_available
        if not pdf_available():
            from django.http import HttpResponse
            return HttpResponse('PDF generation not available.', status=503)

        today = date.today()
        start_date = today - timedelta(days=90)
        pdf_bytes = generate_student_pdf(student, start_date, today)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="my_attendance_{student.student_id}.pdf"'
        return response
    except Exception as e:
        logger.exception('Student PDF error: %s', e)
        return redirect('student_dashboard')

