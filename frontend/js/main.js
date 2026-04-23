const API_BASE = (() => {
  const configured = (window.APP_CONFIG && window.APP_CONFIG.API_BASE) || '';
  if (configured) return configured.replace(/\/$/, '');

  const hostname = window.location.hostname;
  const isLocal = hostname === 'localhost' || hostname === '127.0.0.1';
  return isLocal ? 'http://localhost:5000/api' : '/api';
})();
const TRANSLATION_STORAGE_KEY = 'siteLanguage';
const TRANSLATION_LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'hi', label: 'Hindi' },
  { value: 'mr', label: 'Marathi' },
  { value: 'gu', label: 'Gujarati' },
  { value: 'pa', label: 'Punjabi' },
  { value: 'ta', label: 'Tamil' },
  { value: 'te', label: 'Telugu' }
];

let translateApplyTimer = null;

// ===== AUTH HELPERS =====
function getToken() { return localStorage.getItem('token'); }
function getUser() {
  const u = localStorage.getItem('user');
  return u ? JSON.parse(u) : null;
}
function isLoggedIn() { return !!getToken(); }
function isFarmerLoggedIn() {
  if (!isLoggedIn()) return false;
  const user = getUser();
  if (!user || !user.role) return false;
  const role = String(user.role).toLowerCase();
  return role === 'farmer' || role === 'renter';
}
function logout() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  window.location.href = '/index.html';
}

// ===== API HELPER =====
async function apiCall(method, endpoint, data = null, auth = false) {
  const headers = { 'Content-Type': 'application/json' };
  if (auth && getToken()) headers['Authorization'] = `Bearer ${getToken()}`;
  const opts = { method, headers };
  if (data) opts.body = JSON.stringify(data);
  const res = await fetch(`${API_BASE}${endpoint}`, opts);
  let payload = null;
  try {
    payload = await res.json();
  } catch (_) {
    payload = null;
  }

  if (!res.ok) {
    const message = (payload && payload.error) ? payload.error : `Request failed (${res.status})`;
    throw new Error(message);
  }

  return payload || {};
}

// ===== NAVBAR: Hamburger =====
const hamburger = document.getElementById('hamburger');
const navLinks = document.getElementById('navLinks');
if (hamburger) {
  hamburger.addEventListener('click', () => {
    navLinks.classList.toggle('open');
  });
}

// ===== NAVBAR: Auth state =====
function updateNavAuth() {
  const navAuth = document.getElementById('navAuth');
  if (!navAuth) return;
  const user = getUser();
  if (user) {
    const role = String(user.role || '').toLowerCase();
    const isOwner = role === 'owner';
    const isAdmin = role === 'admin';
    const kycStatus = String(user.kyc_status || '').toLowerCase();
    const firstName = (user.name || 'User').split(' ')[0];
    const roleLabel = isAdmin ? 'Admin' : (isOwner ? 'Owner' : 'Farmer');
    const ownerPortalHref = (kycStatus === 'approved') ? '/pages/owner-dashboard.html' : '/pages/owner-kyc.html';
    const ownerPortalLabel = (kycStatus === 'approved') ? 'Owner Dashboard' : 'Complete KYC';
    const ownerEquipmentLink = (isOwner && kycStatus === 'approved')
      ? '<a href="/pages/owner-dashboard.html#equipmentList" class="btn-outline" style="margin-left:8px">Equipment</a>'
      : '';
    const ownerLink = isOwner
      ? `<a href="${ownerPortalHref}" class="btn-outline" style="margin-left:8px">${ownerPortalLabel}</a>`
      : '';
    const adminLink = isAdmin
      ? '<a href="/pages/admin-panel.html" class="btn-outline" style="margin-left:8px">Admin Panel</a>'
      : '';

    let statusTag = '';
    if (isOwner) {
      if (kycStatus === 'pending') statusTag = ' | KYC: Pending';
      else if (kycStatus === 'approved') statusTag = ' | KYC: Approved';
      else if (kycStatus === 'rejected') statusTag = ' | KYC: Rejected';
    }

    navAuth.innerHTML = `
      <span style="color:rgba(255,255,255,0.8);font-size:0.88rem;">${roleLabel}: <strong>${firstName}</strong>${statusTag}</span>
      ${ownerLink}
      ${ownerEquipmentLink}
      ${adminLink}
      <button class="btn-outline" onclick="logout()">Logout</button>
    `;
  }
}
updateNavAuth();

function injectLanguageSwitcher() {
  const nav = document.querySelector('.navbar');
  const navAuth = document.getElementById('navAuth');
  if (!nav || !navAuth || document.getElementById('languageSwitcher')) return;

  const wrapper = document.createElement('div');
  wrapper.className = 'language-switcher';
  wrapper.id = 'languageSwitcher';

  const options = TRANSLATION_LANGUAGES.map(language => {
    return `<option value="${language.value}">${language.label}</option>`;
  }).join('');

  wrapper.innerHTML = `
    <select id="languageSelect" class="language-select" aria-label="Translate site">
      ${options}
    </select>
  `;

  nav.insertBefore(wrapper, navAuth);

  const select = document.getElementById('languageSelect');
  const savedLanguage = localStorage.getItem(TRANSLATION_STORAGE_KEY) || 'en';
  select.value = savedLanguage;
  select.addEventListener('change', event => {
    const language = event.target.value || 'en';
    localStorage.setItem(TRANSLATION_STORAGE_KEY, language);
    applyTranslation(language);
  });
}

function applyTranslation(language) {
  const targetLanguage = language || 'en';

  if (translateApplyTimer) {
    clearInterval(translateApplyTimer);
    translateApplyTimer = null;
  }

  const tryApply = () => {
    const combo = document.querySelector('.goog-te-combo');
    if (!combo) return false;
    combo.value = targetLanguage;
    combo.dispatchEvent(new Event('change'));
    return true;
  };

  if (tryApply()) return;

  let attempts = 0;
  translateApplyTimer = setInterval(() => {
    attempts += 1;
    if (tryApply() || attempts >= 20) {
      clearInterval(translateApplyTimer);
      translateApplyTimer = null;
    }
  }, 250);
}

function loadTranslateWidget() {
  if (document.getElementById('googleTranslateScript')) return;

  window.googleTranslateElementInit = function () {
    if (!window.google || !window.google.translate) return;

    new google.translate.TranslateElement({
      pageLanguage: 'en',
      includedLanguages: TRANSLATION_LANGUAGES.map(language => language.value).join(','),
      autoDisplay: false
    }, 'google_translate_element');

    applyTranslation(localStorage.getItem(TRANSLATION_STORAGE_KEY) || 'en');
  };

  const widgetContainer = document.createElement('div');
  widgetContainer.id = 'google_translate_element';
  widgetContainer.className = 'translate-widget';
  document.body.appendChild(widgetContainer);

  const script = document.createElement('script');
  script.id = 'googleTranslateScript';
  script.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
  script.async = true;
  document.body.appendChild(script);
}

injectLanguageSwitcher();
loadTranslateWidget();

// ===== SHOW ALERT =====
function showAlert(containerId, message, type = 'info') {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
  setTimeout(() => { el.innerHTML = ''; }, 4000);
}

// ===== EQUIPMENT CARD RENDERER =====
function renderEquipmentCard(eq) {
  const icons = {
    tractor: '🚜', harvester: '🌾', rotavator: '⚙️',
    sprayer: '💧', thresher: '🌿', plough: '🔧', seeder: '🌱', pump: '🪣'
  };
  const isAvailable = eq.available !== false;
  const icon = icons[eq.category] || '🚜';
  const imageHtml = eq.image_url
    ? `<img src="${eq.image_url}" alt="${eq.name}" loading="lazy" onerror="this.outerHTML='${icon}'"/>`
    : icon;
  const distanceHtml = typeof eq.distance_km === 'number'
    ? `<span><i class="fa-solid fa-route"></i> ${eq.distance_km.toFixed(1)} km</span>`
    : '';
  const canViewAvailabilityStatus = isFarmerLoggedIn();
  const availabilityHtml = isAvailable
    ? '<span class="badge badge-green">Available</span>'
    : '<span class="badge badge-red">Unavailable</span>';
  const ctaLabel = canViewAvailabilityStatus
    ? (isAvailable ? 'View & Book' : 'View Details')
    : 'View Details';
  return `
    <div class="equipment-card" onclick="window.location.href='/pages/equipment-detail.html?id=${eq._id}'">
      <div class="card-img">${imageHtml}</div>
      <div class="card-body">
        <div class="card-title">${eq.name}</div>
        <div class="card-meta">
          <span><i class="fa-solid fa-location-dot"></i> ${eq.location}</span>
          ${distanceHtml}
          <span class="badge badge-green">${eq.category}</span>
          ${canViewAvailabilityStatus ? availabilityHtml : ''}
        </div>
        ${canViewAvailabilityStatus && !isAvailable ? '<div class="card-unavailable-note">Already booked. You can view details for alternatives.</div>' : ''}
        <div class="card-price">₹${eq.price_per_day}<span>/day</span></div>
        <button class="btn-green" style="width:100%" onclick="event.stopPropagation();window.location.href='/pages/equipment-detail.html?id=${eq._id}'">
          <i class="fa-solid fa-calendar-check"></i> ${ctaLabel}
        </button>
      </div>
    </div>
  `;
}

// ===== SEARCH REDIRECT =====
function searchEquipment() {
  const eq = document.getElementById('searchInput')?.value || '';
  const loc = document.getElementById('locationInput')?.value || '';
  window.location.href = `/pages/equipment.html?search=${encodeURIComponent(eq)}&location=${encodeURIComponent(loc)}`;
}

// ===== COUNTER ANIMATION =====
function animateCounter(el, target, suffix = '') {
  let count = 0;
  const step = Math.ceil(target / 60);
  const timer = setInterval(() => {
    count += step;
    if (count >= target) { count = target; clearInterval(timer); }
    el.textContent = count + suffix;
  }, 30);
}
