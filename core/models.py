"""
core/models.py — Database models for students and attendance records.
"""
import pickle
from django.db import models
from django.utils import timezone


DEPARTMENT_CHOICES = [
    ('CSE', 'Computer Science & Engineering'),
    ('ECE', 'Electronics & Communication'),
    ('EEE', 'Electrical & Electronics'),
    ('MECH', 'Mechanical Engineering'),
    ('CIVIL', 'Civil Engineering'),
    ('IT', 'Information Technology'),
    ('AIDS', 'Artificial Intelligence & Data Science'),
    ('OTHER', 'Other'),
]

YEAR_CHOICES = [
    (1, '1st Year'),
    (2, '2nd Year'),
    (3, '3rd Year'),
    (4, '4th Year'),
]


class Student(models.Model):
    """Model representing a registered student."""
    student_id = models.CharField(max_length=20, unique=True, verbose_name='Student ID')
    name = models.CharField(max_length=100, verbose_name='Full Name')
    department = models.CharField(max_length=10, choices=DEPARTMENT_CHOICES, default='CSE')
    year = models.IntegerField(choices=YEAR_CHOICES, default=1)
    email = models.EmailField(unique=True, verbose_name='Email Address')
    phone = models.CharField(max_length=15, blank=True, null=True)
    photo = models.ImageField(upload_to='student_photos/', blank=True, null=True)
    # Pickled numpy face encoding (binary blob)
    face_encoding = models.BinaryField(blank=True, null=True)
    date_registered = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    # Portal access — hashed via Django's make_password
    portal_password = models.CharField(max_length=128, blank=True, default='')

    class Meta:
        ordering = ['name']
        verbose_name = 'Student'
        verbose_name_plural = 'Students'

    def __str__(self):
        return f"{self.student_id} — {self.name}"

    def get_face_encoding(self):
        """Deserialize face encoding from binary field."""
        if self.face_encoding:
            return pickle.loads(bytes(self.face_encoding))
        return None

    def set_face_encoding(self, encoding_array):
        """Serialize and store numpy face encoding."""
        self.face_encoding = pickle.dumps(encoding_array)

    @property
    def has_face_encoding(self):
        return bool(self.face_encoding)

    @property
    def department_display(self):
        return dict(DEPARTMENT_CHOICES).get(self.department, self.department)


class Attendance(models.Model):
    """Model representing a daily attendance record."""

    STATUS_CHOICES = [
        ('present', 'Present'),
        ('late', 'Late'),
        ('absent', 'Absent'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(default=timezone.now)
    time_in = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')
    confidence = models.FloatField(default=0.0, help_text='Face recognition confidence (0–1)')
    marked_by = models.CharField(max_length=50, default='system', help_text='system or admin username')

    class Meta:
        unique_together = ('student', 'date')
        ordering = ['-date', '-time_in']
        verbose_name = 'Attendance Record'
        verbose_name_plural = 'Attendance Records'

    def __str__(self):
        return f"{self.student.name} — {self.date} — {self.status}"

    @property
    def confidence_percent(self):
        return round(self.confidence * 100, 1)


class SystemConfig(models.Model):
    """Key-value store for system configuration."""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True, default='')
    description = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'System Config'
        verbose_name_plural = 'System Configs'

    def __str__(self):
        return f"{self.key} = {self.value[:40]}"

    @classmethod
    def get(cls, key: str, default: str = '') -> str:
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key: str, value: str, description: str = '') -> None:
        cls.objects.update_or_create(
            key=key,
            defaults={'value': value, 'description': description}
        )
