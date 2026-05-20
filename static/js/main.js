// Jogajog – Shared JS utilities

function showToast(msg, duration = 2500) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
}

// Auto-hide flash messages after 4s
document.addEventListener('DOMContentLoaded', () => {
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(f => {
    setTimeout(() => {
      f.style.transition = 'opacity 0.4s';
      f.style.opacity = '0';
      setTimeout(() => f.remove(), 400);
    }, 4000);
  });

  // Bottom nav active state
  const currentPath = window.location.pathname;
  document.querySelectorAll('.bni').forEach(item => {
    const href = item.getAttribute('href');
    if (href && href !== '/' && currentPath.startsWith(href)) {
      item.classList.add('on');
    }
  });
});

// Confirm before submit for destructive actions
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', e => {
    if (!confirm(el.getAttribute('data-confirm'))) e.preventDefault();
  });
});

// Lazy load images
if ('IntersectionObserver' in window) {
  const lazyImages = document.querySelectorAll('img[data-src]');
  const io = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target;
        img.src = img.dataset.src;
        img.removeAttribute('data-src');
        io.unobserve(img);
      }
    });
  });
  lazyImages.forEach(img => io.observe(img));
}

// Fetch unread notification count periodically
function refreshNotifBadge() {
  fetch('/notifications/count')
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data) return;
      const badge = document.querySelector('.notif-badge');
      if (data.count > 0) {
        if (badge) badge.textContent = data.count;
      } else if (badge) {
        badge.remove();
      }
    }).catch(() => {});
}

// Poll every 30 seconds if user is logged in
if (document.querySelector('.notif-badge') !== undefined) {
  setInterval(refreshNotifBadge, 30000);
}
