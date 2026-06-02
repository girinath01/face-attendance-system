"""
core/urls.py — URL routing for all pages and API endpoints.
"""
from django.urls import path
from . import views

urlpatterns = [
    # ── Authentication ────────────────────────────────────────────────────────
    path('', views.login_view, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # ── Dashboard ─────────────────────────────────────────────────────────────
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # ── Students ──────────────────────────────────────────────────────────────
    path('students/register/', views.register_student_view, name='register_student'),
    path('students/list/', views.student_list_view, name='student_list'),
    path('students/delete/<int:pk>/', views.delete_student_view, name='delete_student'),
    path('students/reencode/<int:pk>/', views.reencode_student_view, name='reencode_student'),

    # ── Attendance ────────────────────────────────────────────────────────────
    path('attendance/', views.attendance_view, name='attendance'),
    path('attendance/mark-manual/', views.manual_mark_attendance, name='manual_mark_attendance'),

    # ── Reports & Analytics ───────────────────────────────────────────────────
    path('reports/', views.reports_view, name='reports'),
    path('reports/export/csv/', views.export_csv_view, name='export_csv'),
    path('reports/export/pdf/', views.export_pdf_view, name='export_pdf'),
    path('analytics/', views.analytics_view, name='analytics'),

    # ── Batch Classroom Scan ──────────────────────────────────────────────────
    path('batch-scan/', views.batch_scan_view, name='batch_scan'),

    # ── Settings ──────────────────────────────────────────────────────────────
    path('settings/', views.settings_view, name='settings'),

    # ── Face Recognition API ──────────────────────────────────────────────────
    path('api/recognize/', views.recognize_face_api, name='recognize_face_api'),
    path('api/mark-attendance/', views.mark_attendance_api, name='mark_attendance_api'),
    path('api/retrain/', views.retrain_encodings_api, name='retrain_api'),
    path('api/stats/', views.dashboard_stats_api, name='stats_api'),

    # ── Liveness & Live Feed APIs ─────────────────────────────────────────────
    path('api/liveness/', views.liveness_check_api, name='liveness_api'),
    path('api/live-feed/', views.live_feed_sse, name='live_feed_sse'),

    # ── Batch Scan APIs ───────────────────────────────────────────────────────
    path('api/batch-scan/', views.batch_scan_api, name='batch_scan_api'),
    path('api/batch-mark-present/', views.batch_mark_present_api, name='batch_mark_present_api'),

    # ── Student Self-Service Portal ───────────────────────────────────────────
    path('portal/', views.student_login_view, name='student_login'),
    path('portal/logout/', views.student_logout_view, name='student_logout'),
    path('portal/dashboard/', views.student_dashboard_view, name='student_dashboard'),
    path('portal/report/pdf/', views.student_export_pdf_view, name='student_export_pdf'),
]
