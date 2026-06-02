"""
core/forms.py — Django forms for student registration and admin settings.
"""
from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from .models import Student, DEPARTMENT_CHOICES, YEAR_CHOICES


class StudentRegistrationForm(forms.ModelForm):
    """Form for registering a new student with optional photo upload."""

    class Meta:
        model = Student
        fields = ['student_id', 'name', 'department', 'year', 'email', 'phone', 'photo']
        widgets = {
            'student_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. CS2024001',
                'id': 'student_id',
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full Name',
                'id': 'name',
            }),
            'department': forms.Select(attrs={
                'class': 'form-select',
                'id': 'department',
            }),
            'year': forms.Select(attrs={
                'class': 'form-select',
                'id': 'year',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'student@example.com',
                'id': 'email',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+91 9876543210',
                'id': 'phone',
            }),
            'photo': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'id': 'photo',
            }),
        }

    def clean_student_id(self):
        sid = self.cleaned_data['student_id'].strip().upper()
        if Student.objects.filter(student_id=sid).exists():
            if not (self.instance and self.instance.student_id == sid):
                raise forms.ValidationError('A student with this ID already exists.')
        return sid

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            # Validate file size (max 5 MB)
            if hasattr(photo, 'size') and photo.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Photo file is too large. Maximum allowed size is 5 MB.')
            # Validate file type
            if hasattr(photo, 'content_type'):
                allowed_types = ['image/jpeg', 'image/png', 'image/webp']
                if photo.content_type not in allowed_types:
                    raise forms.ValidationError('Only JPEG, PNG, and WebP images are allowed.')
        return photo


class AttendanceFilterForm(forms.Form):
    """Form for filtering attendance records."""
    date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'id': 'filter_date'}),
        label='Date'
    )
    department = forms.ChoiceField(
        required=False,
        choices=[('', 'All Departments')] + DEPARTMENT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'filter_dept'}),
    )
    year = forms.ChoiceField(
        required=False,
        choices=[('', 'All Years')] + [(str(y), f'{y}{["st","nd","rd","th"][min(y-1,3)]} Year') for y in range(1, 5)],
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'filter_year'}),
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name or ID...',
            'id': 'filter_search',
        }),
    )


class AdminProfileForm(forms.Form):
    """Form for editing admin profile details."""
    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'first_name'}),
    )
    last_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'last_name'}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'id': 'admin_email'}),
    )


class AdminPasswordChangeForm(PasswordChangeForm):
    """Styled password change form."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
