"""
core/management/commands/seed_data.py
=======================================
Management command to populate the database with realistic sample data
for demonstration and testing purposes.

Usage:
    py manage.py seed_data
    py manage.py seed_data --students 20
    py manage.py seed_data --clear     # clear existing data first
"""
import random
from datetime import date, timedelta, time as dtime
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Student, Attendance, DEPARTMENT_CHOICES, YEAR_CHOICES


SAMPLE_NAMES = [
    "Arjun Kumar", "Priya Sharma", "Rahul Verma", "Anjali Singh",
    "Rohan Mehta", "Sneha Patel", "Vikram Rao", "Nisha Gupta",
    "Aarav Nair", "Divya Pillai", "Karan Malhotra", "Pooja Iyer",
    "Aditya Joshi", "Kavya Reddy", "Siddharth Menon", "Riya Chopra",
    "Aryan Shah", "Meera Krishnan", "Vivek Banerjee", "Tanvi Pandey",
    "Harsh Agarwal", "Simran Kaur", "Nikhil Bose", "Ankita Mishra",
    "Abhishek Tiwari", "Shreya Srivastava", "Kunal Saxena", "Ishita Bhatt",
    "Tarun Jain", "Neha Choudhary",
]


class Command(BaseCommand):
    help = "Seed the database with sample students and attendance data"

    def add_arguments(self, parser):
        parser.add_argument(
            '--students',
            type=int,
            default=15,
            help='Number of sample students to create (default: 15)',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days of attendance history (default: 30)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all existing student & attendance data first',
        )

    def handle(self, *args, **options):
        if options['clear']:
            Attendance.objects.all().delete()
            Student.objects.all().delete()
            self.stdout.write(self.style.WARNING("Cleared all existing data."))

        num_students = min(options['students'], len(SAMPLE_NAMES))
        num_days = options['days']
        departments = [code for code, _ in DEPARTMENT_CHOICES]
        years = [y for y, _ in YEAR_CHOICES]

        # Create students
        self.stdout.write(f"Creating {num_students} sample students...")
        students = []
        created_count = 0

        for i, name in enumerate(SAMPLE_NAMES[:num_students], start=1):
            sid = f"CS{2024000 + i}"
            dept = departments[i % len(departments)]
            year = years[i % len(years)]
            email = f"{name.lower().replace(' ', '.')}{i}@college.edu"

            student, created = Student.objects.get_or_create(
                student_id=sid,
                defaults={
                    'name': name,
                    'department': dept,
                    'year': year,
                    'email': email,
                    'phone': f"+91 9{random.randint(100000000, 999999999)}",
                    'is_active': True,
                    'date_registered': timezone.now() - timedelta(days=random.randint(1, 90)),
                },
            )
            if created:
                created_count += 1
                self.stdout.write(f"  + {student.name} ({student.student_id})")

            students.append(student)

        self.stdout.write(self.style.SUCCESS(
            f"  Created {created_count} new students ({num_students - created_count} already existed)."
        ))

        # Create attendance records
        self.stdout.write(f"\nGenerating {num_days} days of attendance history...")
        today = date.today()
        att_created = 0

        for day_offset in range(num_days - 1, -1, -1):
            att_date = today - timedelta(days=day_offset)

            # Skip Sundays (weekday 6)
            if att_date.weekday() == 6:
                continue

            for student in students:
                # 80% base attendance probability, with some random variation
                base_prob = 0.85 if student.year <= 2 else 0.75
                present = random.random() < base_prob

                if not present:
                    continue

                # Random time between 8:30 and 10:00
                hour = random.randint(8, 9)
                minute = random.randint(0, 59)
                status = 'late' if hour >= 9 and minute > 20 else 'present'

                _, created = Attendance.objects.get_or_create(
                    student=student,
                    date=att_date,
                    defaults={
                        'time_in': dtime(hour, minute, 0),
                        'status': status,
                        'confidence': round(random.uniform(0.72, 0.99), 3),
                        'marked_by': 'system',
                    },
                )
                if created:
                    att_created += 1

        self.stdout.write(self.style.SUCCESS(f"  Created {att_created} attendance records."))
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Seed complete! {Student.objects.filter(is_active=True).count()} students, "
            f"{Attendance.objects.count()} attendance records."
        ))
        self.stdout.write("   Dashboard: http://127.0.0.1:8000/dashboard/")
