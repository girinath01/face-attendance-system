"""
core/admin.py — Django admin configuration for Student and Attendance models.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Student, Attendance


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'name', 'department', 'year', 'email', 'encoding_status', 'date_registered', 'is_active']
    list_filter = ['department', 'year', 'is_active']
    search_fields = ['student_id', 'name', 'email']
    readonly_fields = ['date_registered', 'encoding_status']
    ordering = ['name']

    def encoding_status(self, obj):
        if obj.has_face_encoding:
            return format_html('<span style="color: #22c55e; font-weight: bold;">✓ Encoded</span>')
        return format_html('<span style="color: #ef4444; font-weight: bold;">✗ Not Encoded</span>')
    encoding_status.short_description = 'Face Encoding'


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'date', 'time_in', 'status', 'confidence_percent', 'marked_by']
    list_filter = ['status', 'date', 'student__department']
    search_fields = ['student__name', 'student__student_id']
    date_hierarchy = 'date'
    ordering = ['-date', '-time_in']

    def confidence_percent(self, obj):
        pct = obj.confidence_percent
        color = '#22c55e' if pct >= 70 else '#f59e0b' if pct >= 50 else '#ef4444'
        return format_html('<span style="color: {}; font-weight: bold;">{:.1f}%</span>', color, pct)
    confidence_percent.short_description = 'Confidence'
