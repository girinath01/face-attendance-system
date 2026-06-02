/**
 * main.js — Webcam control, face recognition AJAX calls, and UI helpers.
 */

// ── Global state ──────────────────────────────────────────────────────────
const App = {
  videoStream: null,
  recognitionActive: false,
  recognitionInterval: null,
  captureInterval: 1500,       // ms between recognition attempts
  lastRecognized: null,
  lastMarked: new Set(),        // Student PKs already marked this session
  requestInFlight: false,       // Prevent overlapping API calls
  cooldownUntil: 0,             // Timestamp when cooldown ends

  // DOM elements
  video: null,
  canvas: null,
  ctx: null,

  init() {
    this.video  = document.getElementById('webcam-video');
    this.canvas = document.getElementById('capture-canvas');
    if (this.canvas) this.ctx = this.canvas.getContext('2d');

    // Clock
    this.startClock();

    // Auto-dismiss alerts after 5 s
    this.autoHideAlerts();

    // Webcam buttons
    const startBtn = document.getElementById('btn-start-webcam');
    const stopBtn  = document.getElementById('btn-stop-webcam');
    if (startBtn) startBtn.addEventListener('click', () => this.startWebcam());
    if (stopBtn)  stopBtn.addEventListener('click',  () => this.stopWebcam());

    // Capture photo (registration page)
    const captureBtn = document.getElementById('btn-capture-photo');
    if (captureBtn) captureBtn.addEventListener('click', () => this.capturePhoto());

    // Use uploaded photo preview
    const photoInput = document.getElementById('photo');
    if (photoInput) photoInput.addEventListener('change', (e) => this.previewPhoto(e));

    console.log('AI Face Attendance System ready ✓');
  },

  // ── Clock ──────────────────────────────────────────────────────────────
  startClock() {
    const el = document.getElementById('live-clock');
    if (!el) return;
    const update = () => {
      const now = new Date();
      el.textContent = now.toLocaleTimeString('en-IN', { hour12: true });
    };
    update();
    setInterval(update, 1000);
  },

  // ── Alert auto-hide ────────────────────────────────────────────────────
  autoHideAlerts() {
    document.querySelectorAll('.alert-auto-hide').forEach(alert => {
      setTimeout(() => {
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-10px)';
        alert.style.transition = 'all 0.4s ease';
        setTimeout(() => alert.remove(), 400);
      }, 5000);
    });
  },

  // ── Toast Notifications ────────────────────────────────────────────────
  showToast(message, type = 'info', duration = 4000) {
    const icons = {
      success: 'fa-check-circle',
      error:   'fa-times-circle',
      warning: 'fa-exclamation-triangle',
      info:    'fa-info-circle',
    };

    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast-item ${type}`;
    toast.innerHTML = `
      <i class="fa-solid ${icons[type] || 'fa-info-circle'}"></i>
      <span style="flex:1">${message}</span>
      <i class="fa-solid fa-xmark" style="cursor:pointer;opacity:0.7" onclick="this.parentElement.remove()"></i>
    `;

    container.appendChild(toast);

    if (duration > 0) {
      setTimeout(() => {
        toast.style.animation = 'toastOut 0.4s ease forwards';
        setTimeout(() => toast.remove(), 400);
      }, duration);
    }
  },

  // ── Webcam ─────────────────────────────────────────────────────────────
  async startWebcam(forRecognition = true) {
    const statusEl = document.getElementById('webcam-status');

    try {
      this.videoStream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
        audio: false,
      });

      if (this.video) {
        this.video.srcObject = this.videoStream;
        await this.video.play();
      }

      this.updateWebcamUI(true);

      if (statusEl) {
        statusEl.textContent = 'Camera active — scanning for faces…';
        statusEl.style.color = '#4ade80';
      }

      if (forRecognition) {
        setTimeout(() => this.startRecognition(), 1000);
      }

      this.showToast('Camera started successfully', 'success');

    } catch (err) {
      console.error('Webcam error:', err);
      const msg = err.name === 'NotAllowedError'
        ? 'Camera permission denied. Please allow camera access.'
        : `Camera error: ${err.message}`;
      this.showToast(msg, 'error', 6000);
      if (statusEl) { statusEl.textContent = msg; statusEl.style.color = '#f87171'; }
    }
  },

  stopWebcam() {
    this.stopRecognition();

    if (this.videoStream) {
      this.videoStream.getTracks().forEach(t => t.stop());
      this.videoStream = null;
    }

    if (this.video) {
      this.video.srcObject = null;
    }

    this.updateWebcamUI(false);
    this.showToast('Camera stopped', 'info');

    const statusEl = document.getElementById('webcam-status');
    if (statusEl) { statusEl.textContent = 'Camera stopped.'; statusEl.style.color = '#94a3b8'; }
  },

  updateWebcamUI(active) {
    const startBtn = document.getElementById('btn-start-webcam');
    const stopBtn  = document.getElementById('btn-stop-webcam');
    if (startBtn) startBtn.style.display = active ? 'none' : 'inline-flex';
    if (stopBtn)  stopBtn.style.display  = active ? 'inline-flex' : 'none';

    // Toggle scan animation
    const scanLine = document.querySelector('.scan-line');
    if (scanLine) scanLine.style.display = active ? 'block' : 'none';
  },

  // ── Face Recognition Loop ──────────────────────────────────────────────
  startRecognition() {
    if (this.recognitionActive) return;
    this.recognitionActive = true;

    this.recognitionInterval = setInterval(() => {
      if (!this.videoStream) { this.stopRecognition(); return; }
      this.captureAndRecognize();
    }, this.captureInterval);
  },

  stopRecognition() {
    this.recognitionActive = false;
    if (this.recognitionInterval) {
      clearInterval(this.recognitionInterval);
      this.recognitionInterval = null;
    }
  },

  captureFrame() {
    if (!this.video || !this.canvas) return null;
    const { videoWidth: w, videoHeight: h } = this.video;
    if (!w || !h) return null;
    this.canvas.width  = w;
    this.canvas.height = h;
    this.ctx.drawImage(this.video, 0, 0, w, h);
    return this.canvas.toDataURL('image/jpeg', 0.7);
  },

  async captureAndRecognize() {
    const frame = this.captureFrame();
    if (!frame) return;

    // Rate limiting: skip if in cooldown or request already in flight
    if (this.requestInFlight) return;
    if (Date.now() < this.cooldownUntil) return;

    this.requestInFlight = true;

    try {
      const resp = await fetch('/api/recognize/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCsrf() },
        body: JSON.stringify({ image: frame }),
      });

      const data = await resp.json();

      // Handle AI not installed
      if (data.ai_not_ready) {
        this.stopRecognition();
        const resultPanel = document.getElementById('recognition-result');
        if (resultPanel) {
          resultPanel.innerHTML = `
            <div class="recognition-result error">
              <div class="result-avatar-placeholder" style="background:linear-gradient(135deg,#ef4444,#f59e0b);">⚠</div>
              <div style="flex:1">
                <div style="font-size:14px;font-weight:600;color:#f87171;">AI Libraries Not Installed</div>
                <div style="font-size:12px;color:#94a3b8;margin-top:4px;">${data.error}</div>
              </div>
            </div>`;
        }
        this.showToast(data.error, 'error', 8000);
        return;
      }

      this.handleRecognitionResult(data);

    } catch (err) {
      console.warn('Recognition request failed:', err);
    } finally {
      this.requestInFlight = false;
    }
  },

  async handleRecognitionResult(data) {
    const resultPanel = document.getElementById('recognition-result');

    if (!data.success) {
      // No face or not recognized — clear panel quietly
      if (data.message && resultPanel) {
        resultPanel.innerHTML = `
          <div class="recognition-result warning">
            <div class="result-avatar-placeholder">?</div>
            <div style="flex:1">
              <div style="font-size:13px;color:#94a3b8;">${data.message}</div>
            </div>
          </div>`;
      }
      return;
    }

    const { student_id, name, department, year, photo_url, confidence, confidence_pct, already_marked, student_code } = data;

    // Prevent re-marking already-done students
    if (already_marked && this.lastMarked.has(student_id)) return;

    // Display recognized student
    if (resultPanel) {
      const avatarHtml = photo_url
        ? `<img src="${photo_url}" class="result-avatar" alt="${name}">`
        : `<div class="result-avatar-placeholder">${name.charAt(0)}</div>`;

      const statusColor = already_marked ? '#fbbf24' : '#4ade80';
      const statusText  = already_marked ? '⚠️ Already marked today' : '✅ Recognized!';

      resultPanel.innerHTML = `
        <div class="recognition-result ${already_marked ? 'warning' : 'success'}">
          ${avatarHtml}
          <div style="flex:1">
            <div style="font-size:16px;font-weight:700;color:#f1f5f9;">${name}</div>
            <div style="font-size:12px;color:#94a3b8;">${student_code} · ${department} · Year ${year}</div>
            <div style="margin-top:8px;">
              <div class="confidence-bar-wrap">
                <div class="confidence-bar-fill" style="width:${confidence_pct}%"></div>
              </div>
              <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Confidence: ${confidence_pct}%</div>
            </div>
            <div style="margin-top:6px;font-size:13px;color:${statusColor};">${statusText}</div>
          </div>
        </div>`;
    }

    // Auto-mark attendance if not already marked
    if (!already_marked && !this.lastMarked.has(student_id)) {
      this.lastMarked.add(student_id);
      // 3-second cooldown after a successful recognition
      this.cooldownUntil = Date.now() + 3000;
      await this.markAttendance(student_id, confidence);
    }
  },

  async markAttendance(studentId, confidence) {
    try {
      const resp = await fetch('/api/mark-attendance/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': this.getCsrf() },
        body: JSON.stringify({ student_id: studentId, confidence }),
      });

      const data = await resp.json();

      if (data.success) {
        this.showToast(data.message, 'success');
        this.refreshAttendanceTable();
      } else if (data.already_marked) {
        this.showToast(data.message, 'warning');
      } else {
        this.showToast(data.error || 'Attendance marking failed', 'error');
      }

    } catch (err) {
      this.showToast('Network error while marking attendance', 'error');
    }
  },

  // ── Registration Page Webcam ───────────────────────────────────────────
  async startRegistrationWebcam() {
    try {
      this.videoStream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' }, audio: false,
      });
      if (this.video) {
        this.video.srcObject = this.videoStream;
        await this.video.play();
      }
      document.getElementById('btn-capture-photo').disabled = false;
      this.showToast('Camera ready — position your face in frame', 'info');
    } catch (err) {
      this.showToast('Could not access camera: ' + err.message, 'error');
    }
  },

  capturePhoto() {
    const frame = this.captureFrame();
    if (!frame) {
      this.showToast('Camera not active. Start camera first.', 'warning');
      return;
    }

    // Store in hidden input
    const hiddenInput = document.getElementById('captured_photo');
    if (hiddenInput) hiddenInput.value = frame;

    // Show preview
    const preview = document.getElementById('photo-preview');
    if (preview) {
      preview.src = frame;
      preview.style.display = 'block';
    }

    this.showToast('📸 Photo captured! You can now register the student.', 'success');
  },

  previewPhoto(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const preview = document.getElementById('photo-preview');
      if (preview) {
        preview.src = ev.target.result;
        preview.style.display = 'block';
      }
    };
    reader.readAsDataURL(file);
  },

  // ── Live attendance table refresh ──────────────────────────────────────
  refreshAttendanceTable() {
    const tableWrap = document.getElementById('attendance-table-wrap');
    if (!tableWrap) return;

    // Use HTMX-style partial refresh or just reload the table rows
    setTimeout(() => {
      fetch(window.location.href + '?refresh=1', { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(r => r.text())
        .then(html => {
          const parser = new DOMParser();
          const doc = parser.parseFromString(html, 'text/html');
          const newTable = doc.getElementById('attendance-table-wrap');
          if (newTable && tableWrap) {
            tableWrap.innerHTML = newTable.innerHTML;
          }
        })
        .catch(() => {});
    }, 500);
  },

  // ── CSRF helper ────────────────────────────────────────────────────────
  getCsrf() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.content;
    const cookie = document.cookie.split('; ').find(r => r.startsWith('csrftoken='));
    return cookie ? cookie.split('=')[1] : '';
  },
};

// ── Kick off on DOMContentLoaded ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => App.init());
