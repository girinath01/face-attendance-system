"""
core/management/commands/encode_students.py
============================================
Management command to batch-generate face encodings for all students
that have photos but no encoding stored.

Usage:
    py manage.py encode_students          # encode only missing
    py manage.py encode_students --all    # re-encode everyone
    py manage.py encode_students --id 5   # encode specific student PK
"""
from django.core.management.base import BaseCommand, CommandError
from core.models import Student
from core.face_utils import encode_face_from_image, ai_available, ai_status


class Command(BaseCommand):
    help = "Generate face encodings for students who have photos"

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            dest='encode_all',
            help='Re-encode ALL students, overwriting existing encodings',
        )
        parser.add_argument(
            '--id',
            type=int,
            dest='student_pk',
            help='Encode a specific student by DB primary key',
        )

    def handle(self, *args, **options):
        # Check AI libraries
        status = ai_status()
        if not status['all_ready']:
            missing = [k for k, v in status.items() if not v and k != 'all_ready']
            raise CommandError(
                f"AI libraries not fully installed. Missing: {', '.join(missing)}\n"
                "Run: pip install cmake wheel dlib opencv-python face-recognition"
            )

        # Filter students
        if options['student_pk']:
            students = Student.objects.filter(pk=options['student_pk'], is_active=True)
            if not students.exists():
                raise CommandError(f"No active student with pk={options['student_pk']}")
        elif options['encode_all']:
            students = Student.objects.filter(is_active=True).exclude(photo='')
        else:
            # Only students with photos but missing encodings
            students = Student.objects.filter(
                is_active=True, face_encoding__isnull=True
            ).exclude(photo='')

        total = students.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("No students need encoding."))
            return

        self.stdout.write(f"Processing {total} student(s)...")
        success_count = 0
        fail_count = 0

        for student in students:
            if not student.photo:
                self.stdout.write(
                    self.style.WARNING(f"  SKIP {student.name} — no photo")
                )
                continue

            self.stdout.write(f"  Encoding {student.name} ({student.student_id})... ", ending='')
            encoding = encode_face_from_image(student.photo.path)

            if encoding is not None:
                student.set_face_encoding(encoding)
                student.save(update_fields=['face_encoding'])
                self.stdout.write(self.style.SUCCESS("OK"))
                success_count += 1
            else:
                self.stdout.write(self.style.ERROR("FAILED — no face detected"))
                fail_count += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done: {success_count} encoded, {fail_count} failed."
        ))
