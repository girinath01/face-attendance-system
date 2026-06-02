/**
 * dashboard.js — Chart.js analytics charts for the admin dashboard.
 */

document.addEventListener('DOMContentLoaded', () => {

  // ── Common chart defaults ────────────────────────────────────────────
  Chart.defaults.color = '#94a3b8';
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.font.size = 12;

  // ── Weekly Attendance Bar Chart ──────────────────────────────────────
  const weeklyCtx = document.getElementById('weeklyChart');
  if (weeklyCtx && typeof weeklyLabels !== 'undefined') {
    new Chart(weeklyCtx, {
      type: 'bar',
      data: {
        labels: weeklyLabels,
        datasets: [{
          label: 'Students Present',
          data: weeklyData,
          backgroundColor: weeklyData.map((_, i) =>
            i === weeklyData.length - 1
              ? 'rgba(99,102,241,0.9)'
              : 'rgba(99,102,241,0.45)'
          ),
          borderColor: 'rgba(99,102,241,1)',
          borderWidth: 1,
          borderRadius: 8,
          borderSkipped: false,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(15,22,41,0.95)',
            borderColor: 'rgba(99,102,241,0.4)',
            borderWidth: 1,
            titleColor: '#f1f5f9',
            bodyColor: '#94a3b8',
            padding: 12,
            cornerRadius: 10,
            callbacks: {
              title: (items) => items[0].label,
              label: (item) => ` ${item.raw} students present`,
            },
          },
        },
        scales: {
          x: {
            grid: { color: 'rgba(255,255,255,0.05)', drawBorder: false },
            ticks: { color: '#64748b' },
          },
          y: {
            grid: { color: 'rgba(255,255,255,0.05)', drawBorder: false },
            ticks: { color: '#64748b', precision: 0 },
            beginAtZero: true,
          },
        },
        animation: {
          duration: 800,
          easing: 'easeOutQuart',
        },
      },
    });
  }

  // ── Department Distribution Doughnut Chart ───────────────────────────
  const deptCtx = document.getElementById('deptChart');
  if (deptCtx && typeof deptLabels !== 'undefined') {
    const deptColors = [
      'rgba(99,102,241,0.85)',
      'rgba(139,92,246,0.85)',
      'rgba(6,182,212,0.85)',
      'rgba(34,197,94,0.85)',
      'rgba(245,158,11,0.85)',
      'rgba(239,68,68,0.85)',
      'rgba(236,72,153,0.85)',
      'rgba(168,85,247,0.85)',
    ];

    new Chart(deptCtx, {
      type: 'doughnut',
      data: {
        labels: deptLabels,
        datasets: [{
          data: deptCounts,
          backgroundColor: deptColors.slice(0, deptLabels.length),
          borderColor: 'rgba(15,22,41,0.8)',
          borderWidth: 3,
          hoverOffset: 8,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '68%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              color: '#94a3b8',
              padding: 16,
              usePointStyle: true,
              pointStyleWidth: 10,
              font: { size: 12 },
            },
          },
          tooltip: {
            backgroundColor: 'rgba(15,22,41,0.95)',
            borderColor: 'rgba(99,102,241,0.4)',
            borderWidth: 1,
            titleColor: '#f1f5f9',
            bodyColor: '#94a3b8',
            padding: 12,
            cornerRadius: 10,
            callbacks: {
              label: (item) => ` ${item.label}: ${item.raw} students`,
            },
          },
        },
        animation: {
          animateRotate: true,
          duration: 1000,
          easing: 'easeOutQuart',
        },
      },
    });
  }

  // ── Animate stat counters ────────────────────────────────────────────
  document.querySelectorAll('.stat-value[data-target]').forEach(el => {
    const target = parseInt(el.getAttribute('data-target'));
    if (isNaN(target)) return;
    let start = 0;
    const duration = 1200;
    const step = target / (duration / 16);
    const timer = setInterval(() => {
      start = Math.min(start + step, target);
      el.textContent = Math.round(start);
      if (start >= target) clearInterval(timer);
    }, 16);
  });

  // ── Progress bar animations ──────────────────────────────────────────
  document.querySelectorAll('.progress-fill[data-width]').forEach(el => {
    const width = el.getAttribute('data-width');
    setTimeout(() => { el.style.width = width + '%'; }, 200);
  });

  // ── Dashboard auto-refresh stats every 30 seconds ───────────────────
  const autoRefresh = document.getElementById('auto-refresh-stats');
  if (autoRefresh) {
    setInterval(async () => {
      try {
        const resp = await fetch('/api/stats/');
        const data = await resp.json();

        const update = (id, val) => {
          const el = document.getElementById(id);
          if (el) el.textContent = val;
        };

        update('stat-total',   data.total);
        update('stat-present', data.present);
        update('stat-absent',  data.absent);
        update('stat-pct',     data.percentage + '%');
      } catch (e) {}
    }, 30000);
  }

});
