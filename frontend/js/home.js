// ===== HOME PAGE JS =====

let equipmentRefreshTimer = null;
const EQUIPMENT_REFRESH_INTERVAL = 8000; // 8 seconds

function startEquipmentRefresh() {
  if (equipmentRefreshTimer) clearInterval(equipmentRefreshTimer);
  equipmentRefreshTimer = setInterval(() => {
    if (document.hidden) return; // Pause if tab is not visible
    loadFeaturedEquipment();
  }, EQUIPMENT_REFRESH_INTERVAL);
}

function stopEquipmentRefresh() {
  if (equipmentRefreshTimer) {
    clearInterval(equipmentRefreshTimer);
    equipmentRefreshTimer = null;
  }
}

// Listen for visibility changes
document.addEventListener('visibilitychange', () => {
  if (document.hidden) stopEquipmentRefresh();
  else startEquipmentRefresh();
});

// Animate stats on page load
window.addEventListener('load', async () => {
  animateCounter(document.getElementById('statEquip'), 120, '+');
  animateCounter(document.getElementById('statOwners'), 85, '+');
  animateCounter(document.getElementById('statRentals'), 430, '+');
  loadFeaturedEquipment();
  startEquipmentRefresh();
});

async function loadFeaturedEquipment() {
  const grid = document.getElementById('featuredGrid');
  try {
    const res = await apiCall('GET', '/equipment/?limit=8');
    if (res.equipment && res.equipment.length > 0) {
      grid.innerHTML = res.equipment.map(renderEquipmentCard).join('');
    } else {
      grid.innerHTML = '<div class="no-results"><i class="fa-solid fa-box-open"></i>No equipment available right now.</div>';
    }
  } catch (e) {
    grid.innerHTML = `<div class="no-results"><i class="fa-solid fa-plug-circle-xmark"></i>${e.message || 'Unable to connect to backend.'}</div>`;
  }
}
