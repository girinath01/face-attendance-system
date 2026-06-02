# AI Face Attendance Management System

A production-style, web-based attendance system that uses face recognition to automatically mark student attendance in real time via webcam. Built with Django, OpenCV, and a premium glassmorphism dark-theme UI.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Django](https://img.shields.io/badge/Django-4.2-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Features

- **AI Face Recognition** — Webcam-based attendance marking using OpenCV + `face_recognition`
- **Real-Time Dashboard** — Live stats, weekly bar charts, department distribution, auto-refresh
- **Student Management** — Register students with photos (upload or webcam capture), batch encoding
- **Attendance Tracking** — Live scanner, manual marking, filtering by date/department/year
- **Reports & Export** — Per-student attendance %, low-attendance alerts, CSV export
- **Admin Settings** — Profile management, password change, AI library status monitor
- **Responsive Design** — Mobile hamburger menu, collapsible sidebar, works on all devices
- **Security** — Login-protected pages, CSRF protection, session-based auth, file type/size validation

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.10+, Django 4.2 |
| Frontend | HTML5, CSS3 (Glassmorphism), JavaScript, Bootstrap 5 |
| Database | SQLite (default), PostgreSQL-ready |
| AI/ML | OpenCV, face_recognition, NumPy, dlib |
| Charts | Chart.js 4.x |
| Icons | Font Awesome 6 |
| Fonts | Inter (Google Fonts) |

---

## Quick Start

### 1. Clone & Setup

```bash
cd face-attendance-system
pip install django numpy pillow opencv-python
```

### 2. Initialize Database

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 3. Seed Sample Data (Optional)

```bash
python manage.py seed_data --students 15 --days 30
```

### 4. Run Development Server

```bash
python manage.py runserver
```

Visit **http://127.0.0.1:8000/** and log in with your superuser credentials.

---

## Installing Face Recognition (Optional)

The web app works without face recognition (all features except live AI scanning). To enable AI:

### Windows

1. Install **Visual Studio Build Tools** with C++ workload
2. Install dependencies:

```bash
pip install cmake wheel
pip install dlib
pip install face-recognition
```

### macOS / Linux

```bash
pip install cmake dlib face-recognition
```

### Verify Installation

Check the **Settings → AI Library Status** panel in the app, or run:

```bash
python -c "import cv2, face_recognition, numpy; print('All AI libraries ready!')"
```

---

## Management Commands

```bash
# Seed sample data
python manage.py seed_data --students 20 --days 30

# Batch encode student face photos
python manage.py encode_students         # encode missing only
python manage.py encode_students --all   # re-encode everyone
python manage.py encode_students --id 5  # encode specific student
```

---

## Project Structure

```
face-attendance-system/
├── face_attendance/          # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                     # Main application
│   ├── models.py             # Student & Attendance models
│   ├── views.py              # All views & API endpoints
│   ├── forms.py              # Django forms with validation
│   ├── admin.py              # Django admin configuration
│   ├── face_utils.py         # Face recognition wrapper (graceful degradation)
│   ├── urls.py               # URL routing
│   └── management/commands/  # Management commands
│       ├── seed_data.py      # Sample data seeder
│       └── encode_students.py # Batch face encoding
├── templates/                # HTML templates
│   ├── base.html             # Layout with sidebar & topbar
│   ├── login.html            # Auth page
│   ├── dashboard.html        # Main analytics dashboard
│   ├── attendance.html       # Live webcam scanner
│   ├── register_student.html # Student registration form
│   ├── student_list.html     # Student directory
│   ├── reports.html          # Attendance reports
│   ├── settings.html         # Admin settings & AI status
│   ├── 404.html              # Custom error page
│   └── 500.html              # Custom error page
├── static/
│   ├── css/style.css         # Full design system (1000+ lines)
│   ├── js/main.js            # Webcam, recognition, toasts
│   ├── js/dashboard.js       # Chart.js analytics
│   └── favicon.svg           # App icon
├── manage.py
├── requirements.txt
└── .gitignore
```

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/recognize/` | Send base64 frame → get recognized student |
| POST | `/api/mark-attendance/` | Mark attendance for student |
| GET | `/api/stats/` | Dashboard stats JSON |
| GET | `/api/retrain/` | Re-encode all unencoded students |

---

## Default Credentials

After running `createsuperuser`:
- **Username**: `admin`
- **Password**: *(whatever you set)*

---

## License

MIT License — Free for educational and commercial use.
