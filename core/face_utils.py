"""
core/face_utils.py
==================
Face recognition utilities using OpenCV and the face_recognition library.

All AI libraries are optional — the Django application will start and serve
all pages even if dlib / face_recognition are not installed.  The API
endpoints simply return a descriptive error message in that case.

Key functions:
- encode_face_from_image()      : Generate a face encoding from an image file
- encode_face_from_base64()     : Encode from a base64 webcam frame
- recognize_faces_in_frame()    : Identify known faces in a webcam frame
- draw_recognition_results()    : Draw bounding boxes and labels on a frame
- load_all_encodings_from_db()  : Bulk-load all student encodings from DB
"""

import os
import base64
import logging
import pickle
from typing import Optional

logger = logging.getLogger(__name__)

# ── Optional AI libraries (imported lazily so Django can start without them) ──
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False
    logger.warning("numpy not installed.  Run: pip install numpy")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False
    logger.warning("opencv-python not installed.  Run: pip install opencv-python")

try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    face_recognition = None
    FACE_RECOGNITION_AVAILABLE = False
    logger.warning(
        "face_recognition not installed.  "
        "Run: pip install cmake wheel dlib face-recognition"
    )

# ─────────────────────────────────────────────────────────────────────────────
# Availability helper
# ─────────────────────────────────────────────────────────────────────────────

def ai_available() -> bool:
    """Return True only when all required AI libraries are present."""
    return NUMPY_AVAILABLE and CV2_AVAILABLE and FACE_RECOGNITION_AVAILABLE


def ai_status() -> dict:
    """Return installation status for all AI libraries."""
    return {
        "numpy": NUMPY_AVAILABLE,
        "opencv": CV2_AVAILABLE,
        "face_recognition": FACE_RECOGNITION_AVAILABLE,
        "all_ready": ai_available(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Encoding helpers
# ─────────────────────────────────────────────────────────────────────────────

def encode_face_from_image(image_path: str) -> Optional[object]:
    """
    Load an image from disk, detect a face, and return its 128-d encoding.

    Args:
        image_path: Absolute or relative path to the image file.

    Returns:
        numpy array (128,) on success, or None if no face was detected or
        if face_recognition is not installed.
    """
    if not ai_available():
        logger.error("AI libraries not fully installed — cannot encode face.")
        return None

    if not os.path.exists(image_path):
        logger.error("Image file not found: %s", image_path)
        return None

    try:
        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)

        if not encodings:
            logger.warning("No face detected in image: %s", image_path)
            return None

        if len(encodings) > 1:
            logger.info("Multiple faces found in %s; using the first.", image_path)

        return encodings[0]

    except Exception as exc:
        logger.exception("Error encoding face from %s: %s", image_path, exc)
        return None


def encode_face_from_base64(b64_data: str) -> Optional[object]:
    """
    Decode a base64-encoded image (from a webcam canvas capture) and
    return the 128-d face encoding of the first detected face.

    Args:
        b64_data: Base64 string, optionally prefixed with
                  'data:image/jpeg;base64,...'

    Returns:
        numpy array (128,) on success, or None.
    """
    if not ai_available():
        return None

    try:
        if ',' in b64_data:
            b64_data = b64_data.split(',', 1)[1]

        img_bytes = base64.b64decode(b64_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        bgr_frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if bgr_frame is None:
            logger.warning("Could not decode base64 image data.")
            return None

        rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb_frame)

        return encodings[0] if encodings else None

    except Exception as exc:
        logger.exception("Error decoding base64 image: %s", exc)
        return None


def decode_frame_from_base64(b64_data: str) -> Optional[object]:
    """
    Decode a base64 image string to a BGR numpy array (OpenCV format).

    Returns None if opencv is not installed or decoding fails.
    """
    if not CV2_AVAILABLE or not NUMPY_AVAILABLE:
        return None

    try:
        if ',' in b64_data:
            b64_data = b64_data.split(',', 1)[1]
        img_bytes = base64.b64decode(b64_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    except Exception as exc:
        logger.exception("Error decoding frame: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Recognition
# ─────────────────────────────────────────────────────────────────────────────

def recognize_faces_in_frame(
    bgr_frame,
    known_encodings: list,
    known_student_ids: list,
    tolerance: float = 0.5,
    model: str = "hog",
) -> list:
    """
    Detect and recognize all faces in a BGR webcam frame.

    Args:
        bgr_frame:         OpenCV BGR image (numpy array).
        known_encodings:   List of numpy 128-d face encoding arrays.
        known_student_ids: List of student DB primary keys, parallel to encodings.
        tolerance:         Lower = stricter matching (0.5 is good default).
        model:             Detection model — "hog" (fast/CPU) or "cnn" (accurate/GPU).

    Returns:
        List of dicts with keys:
            - student_id  : DB PK (int) or None if unknown
            - confidence  : float 0–1
            - location    : (top, right, bottom, left) bounding box
            - is_unknown  : bool
    """
    if not ai_available():
        return []

    results = []

    try:
        rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)

        # Downsample to 50% for speed, then scale locations back
        small_rgb = cv2.resize(rgb_frame, (0, 0), fx=0.5, fy=0.5)

        face_locations = face_recognition.face_locations(small_rgb, model=model)
        face_encodings_list = face_recognition.face_encodings(small_rgb, face_locations)

        for face_enc, face_loc in zip(face_encodings_list, face_locations):
            student_id = None
            confidence = 0.0
            is_unknown = True

            if known_encodings:
                face_distances = face_recognition.face_distance(known_encodings, face_enc)
                best_idx = int(np.argmin(face_distances))
                best_dist = float(face_distances[best_idx])

                if best_dist <= tolerance:
                    student_id = known_student_ids[best_idx]
                    confidence = max(0.0, min(1.0, 1.0 - best_dist))
                    is_unknown = False

            # Scale location back to original frame size
            top, right, bottom, left = face_loc
            top *= 2; right *= 2; bottom *= 2; left *= 2

            results.append({
                'student_id': student_id,
                'confidence': confidence,
                'location': (top, right, bottom, left),
                'is_unknown': is_unknown,
            })

    except Exception as exc:
        logger.exception("Error during face recognition: %s", exc)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Drawing helpers
# ─────────────────────────────────────────────────────────────────────────────

def draw_recognition_results(bgr_frame, results: list, student_name_map: dict):
    """
    Draw bounding boxes and labels on the frame.

    Args:
        bgr_frame:        OpenCV frame.
        results:          Output from recognize_faces_in_frame().
        student_name_map: Dict mapping student PK → display name.

    Returns:
        Annotated BGR frame, or the original frame if cv2 unavailable.
    """
    if not CV2_AVAILABLE:
        return bgr_frame

    frame = bgr_frame.copy()

    for res in results:
        top, right, bottom, left = res['location']

        if res['is_unknown']:
            color = (0, 0, 220)
            label = "Unknown"
        else:
            color = (0, 200, 80)
            name = student_name_map.get(res['student_id'], 'Student')
            pct = round(res['confidence'] * 100, 1)
            label = f"{name} ({pct}%)"

        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.rectangle(frame, (left, bottom - 30), (right, bottom), color, cv2.FILLED)
        cv2.putText(
            frame, label,
            (left + 6, bottom - 8),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55,
            (255, 255, 255), 1,
        )

    return frame


# ─────────────────────────────────────────────────────────────────────────────
# Bulk encoding helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_all_encodings_from_db():
    """
    Load all student face encodings from the database.

    Returns:
        Tuple (known_encodings, known_student_ids) — both lists, same length.
    """
    from .models import Student  # local import to avoid circular deps

    known_encodings = []
    known_student_ids = []

    students = Student.objects.filter(is_active=True).exclude(face_encoding=None)
    for student in students:
        enc = student.get_face_encoding()
        if enc is not None:
            known_encodings.append(enc)
            known_student_ids.append(student.pk)

    logger.info("Loaded %d face encodings from database.", len(known_encodings))
    return known_encodings, known_student_ids


def generate_thumbnail(image_path: str, size: tuple = (150, 150)) -> Optional[str]:
    """
    Create a small square thumbnail of a student photo.

    Returns the path to the thumbnail, or None on failure.
    """
    if not CV2_AVAILABLE:
        return None
    try:
        img = cv2.imread(image_path)
        if img is None:
            return None
        thumb = cv2.resize(img, size)
        base, ext = os.path.splitext(image_path)
        thumb_path = f"{base}_thumb{ext}"
        cv2.imwrite(thumb_path, thumb)
        return thumb_path
    except Exception as exc:
        logger.exception("Thumbnail generation failed: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Liveness Detection (Blink / Motion-based Anti-Spoofing)
# ─────────────────────────────────────────────────────────────────────────────

def compute_ear(eye_points) -> float:
    """
    Eye Aspect Ratio (EAR) formula.
    eye_points: list of 6 (x, y) tuples representing eye landmarks.
    EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
    """
    if not NUMPY_AVAILABLE:
        return 0.3
    p = np.array(eye_points)
    A = np.linalg.norm(p[1] - p[5])
    B = np.linalg.norm(p[2] - p[4])
    C = np.linalg.norm(p[0] - p[3])
    return (A + B) / (2.0 * C) if C > 0 else 0.3


EAR_THRESHOLD = 0.25   # below this → eye is closed (blink)
EAR_CONSEC_FRAMES = 2  # must be below threshold for N consecutive frames


class LivenessSession:
    """
    Stateless blink counter — store one instance per recognition session.
    Call update() with each new frame; check is_live when blink_count >= required.
    """
    def __init__(self, required_blinks: int = 2):
        self.required_blinks = required_blinks
        self.blink_count = 0
        self._consec_below = 0
        self._eye_open = True

    def update(self, ear: float) -> bool:
        """
        Feed the current EAR value; returns True if a new blink was detected.
        """
        new_blink = False
        if ear < EAR_THRESHOLD:
            self._consec_below += 1
        else:
            if self._consec_below >= EAR_CONSEC_FRAMES:
                self.blink_count += 1
                new_blink = True
            self._consec_below = 0
        return new_blink

    @property
    def is_live(self) -> bool:
        return self.blink_count >= self.required_blinks

    def to_dict(self) -> dict:
        return {
            'blink_count': self.blink_count,
            'required_blinks': self.required_blinks,
            'is_live': self.is_live,
        }


def extract_ear_from_frame(bgr_frame, face_location: tuple) -> float:
    """
    Given a BGR frame and a face bounding box (top, right, bottom, left),
    use dlib's 68-point predictor to compute the average EAR of both eyes.
    Returns 0.3 (open-eye default) if dlib predictor not available.
    """
    if not ai_available():
        return 0.3

    try:
        import dlib
        predictor_path = os.path.join(
            os.path.dirname(__file__),
            'shape_predictor_68_face_landmarks.dat'
        )
        if not os.path.exists(predictor_path):
            # Predictor model not downloaded — use motion fallback
            return 0.3

        predictor = dlib.shape_predictor(predictor_path)
        detector = dlib.get_frontal_face_detector()

        gray = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2GRAY)
        top, right, bottom, left = face_location
        rect = dlib.rectangle(left, top, right, bottom)
        shape = predictor(gray, rect)

        # Left eye: points 36–41, Right eye: 42–47
        left_eye = [(shape.part(i).x, shape.part(i).y) for i in range(36, 42)]
        right_eye = [(shape.part(i).x, shape.part(i).y) for i in range(42, 48)]

        left_ear = compute_ear(left_eye)
        right_ear = compute_ear(right_eye)
        return (left_ear + right_ear) / 2.0

    except Exception as exc:
        logger.warning("EAR extraction failed: %s", exc)
        return 0.3


# ─────────────────────────────────────────────────────────────────────────────
# Batch Recognition (Multiple Faces in One Image)
# ─────────────────────────────────────────────────────────────────────────────

def batch_recognize_from_image(
    image_path: str,
    known_encodings: list,
    known_student_ids: list,
    tolerance: float = 0.5,
) -> list:
    """
    Detect and recognize ALL faces in a single image file.
    Ideal for classroom group photos.

    Returns:
        List of dicts with keys:
          - student_id  : DB PK or None
          - confidence  : float 0–1
          - location    : (top, right, bottom, left)
          - is_unknown  : bool
          - face_image  : base64-encoded JPEG crop of the face
    """
    if not ai_available():
        return []

    if not os.path.exists(image_path):
        logger.error("Batch scan: image not found: %s", image_path)
        return []

    try:
        image = face_recognition.load_image_file(image_path)
        face_locations = face_recognition.face_locations(image, model='hog')
        face_encodings_list = face_recognition.face_encodings(image, face_locations)

        results = []
        bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        for face_enc, face_loc in zip(face_encodings_list, face_locations):
            student_id = None
            confidence = 0.0
            is_unknown = True

            if known_encodings:
                distances = face_recognition.face_distance(known_encodings, face_enc)
                best_idx = int(np.argmin(distances))
                best_dist = float(distances[best_idx])
                if best_dist <= tolerance:
                    student_id = known_student_ids[best_idx]
                    confidence = max(0.0, min(1.0, 1.0 - best_dist))
                    is_unknown = False

            # Crop face for preview
            top, right, bottom, left = face_loc
            pad = 20
            crop = bgr[
                max(0, top - pad):min(bgr.shape[0], bottom + pad),
                max(0, left - pad):min(bgr.shape[1], right + pad)
            ]
            _, buf = cv2.imencode('.jpg', crop, [cv2.IMWRITE_JPEG_QUALITY, 80])
            face_b64 = base64.b64encode(buf.tobytes()).decode('utf-8')

            results.append({
                'student_id': student_id,
                'confidence': round(confidence, 3),
                'location': (top, right, bottom, left),
                'is_unknown': is_unknown,
                'face_image': face_b64,
            })

        logger.info("Batch scan: found %d faces in %s", len(results), image_path)
        return results

    except Exception as exc:
        logger.exception("Batch recognition error: %s", exc)
        return []
