// Kalich Telegram Mini App 2.0 (Phase 7.1)

const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const CALL_TIMES = [
  ["08:20", "09:00"],
  ["09:05", "09:50"],
  ["10:00", "10:45"],
  ["10:55", "11:40"],
  ["12:00", "12:45"],
  ["12:55", "13:40"],
  ["13:50", "14:35"],
  ["14:45", "15:30"],
  ["15:40", "16:25"],
  ["16:35", "17:20"]
];

let currentDay = new Date().getDay();
if (currentDay === 0 || currentDay > 6) currentDay = 1;

let allGroups = {};
let selectedGroup = localStorage.getItem('kalich_selected_group') || "ИС 21-25";
let selectedDept = 3;
let selectedGid = 46;

function triggerHaptic(type = 'light') {
  try {
    if (tg?.HapticFeedback) {
      tg.HapticFeedback.impactOccurred(type);
    }
  } catch (e) {}
}

async function loadGroups() {
  try {
    const res = await fetch('/api/groups');
    if (res.ok) {
      const data = await res.json();
      allGroups = data.groups || {};
      updateGroupSelection();
      renderGroupsList();
    }
  } catch (e) {
    console.error("Error loading groups:", e);
  }
}

function updateGroupSelection() {
  if (allGroups[selectedGroup]) {
    const info = allGroups[selectedGroup];
    selectedDept = Array.isArray(info) ? info[0] : 3;
    selectedGid = Array.isArray(info) ? info[1] : info;
  }
  document.getElementById('groupSelectorBtn').textContent = selectedGroup || "Выбрать группу";
}

async function loadSchedule() {
  const container = document.getElementById('scheduleList');
  container.innerHTML = `
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Загрузка расписания...</p>
    </div>
  `;

  try {
    const res = await fetch(`/api/schedule?department=${selectedDept}&group_id=${selectedGid}&day=${currentDay}`);
    if (res.ok) {
      const lessons = await res.json();
      renderSchedule(lessons);
    } else {
      container.innerHTML = `<div class="empty-day">Не удалось загрузить расписание</div>`;
    }
  } catch (e) {
    container.innerHTML = `<div class="empty-day">Ошибка соединения с сервером</div>`;
  }
}

function renderSchedule(lessons) {
  const container = document.getElementById('scheduleList');
  if (!Array.isArray(lessons) || lessons.length === 0) {
    container.innerHTML = `<div class="empty-day">🎉 На этот день занятий нет! Отдыхай!</div>`;
    return;
  }

  let html = '';
  lessons.forEach((rawLesson, idx) => {
    const text = String(rawLesson).trim();
    if (!text || text === "—" || text === ".") return;

    const call = CALL_TIMES[idx] || ["--:--", "--:--"];
    const roomMatch = text.match(/\(([^)]+)\)$/);
    const room = roomMatch ? roomMatch[1] : "";
    const subject = text.replace(/\s*\([^)]*\)$/, '').trim();

    html += `
      <div class="lesson-card">
        <div class="lesson-time-box">
          <span class="lesson-num">${idx + 1}</span>
          <span class="lesson-time">${call[0]}</span>
        </div>
        <div class="lesson-info">
          <div class="lesson-subject">${subject}</div>
          <div class="lesson-meta">
            ${room ? `<span class="room-badge">Каб. ${room}</span>` : ''}
            <span>${call[0]} - ${call[1]}</span>
          </div>
        </div>
      </div>
    `;
  });

  container.innerHTML = html || `<div class="empty-day">🎉 Пар нет! Можно спать!</div>`;
}

function selectDay(day) {
  triggerHaptic('light');
  currentDay = day;
  document.querySelectorAll('.day-tab').forEach(tab => {
    tab.classList.toggle('active', parseInt(tab.dataset.day) === day);
  });
  loadSchedule();
}

function renderGroupsList(filter = "") {
  const listEl = document.getElementById('groupsList');
  const q = filter.toLowerCase().trim();
  const keys = Object.keys(allGroups).filter(k => k.toLowerCase().includes(q));

  listEl.innerHTML = keys.slice(0, 50).map(k => `
    <div class="group-item" data-group="${k}">${k}</div>
  `).join('');

  listEl.querySelectorAll('.group-item').forEach(item => {
    item.addEventListener('click', () => {
      triggerHaptic('medium');
      selectedGroup = item.dataset.group;
      localStorage.setItem('kalich_selected_group', selectedGroup);
      updateGroupSelection();
      closeModal();
      loadSchedule();
    });
  });
}

function openModal() {
  triggerHaptic('light');
  document.getElementById('groupModal').classList.add('open');
  document.getElementById('groupSearchInput').focus();
}

function closeModal() {
  document.getElementById('groupModal').classList.remove('open');
}

// Swiping gestures for switching days
let touchStartX = 0;
let touchEndX = 0;

document.addEventListener('touchstart', e => {
  touchStartX = e.changedTouches[0].screenX;
}, false);

document.addEventListener('touchend', e => {
  touchEndX = e.changedTouches[0].screenX;
  handleSwipe();
}, false);

function handleSwipe() {
  const diff = touchEndX - touchStartX;
  if (Math.abs(diff) > 60) {
    if (diff < 0 && currentDay < 6) {
      selectDay(currentDay + 1);
    } else if (diff > 0 && currentDay > 1) {
      selectDay(currentDay - 1);
    }
  }
}

// Initial binding
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.day-tab').forEach(tab => {
    tab.addEventListener('click', () => selectDay(parseInt(tab.dataset.day)));
  });

  document.getElementById('groupSelectorBtn').addEventListener('click', openModal);
  document.getElementById('closeModalBtn').addEventListener('click', closeModal);
  document.getElementById('modalBackdrop').addEventListener('click', closeModal);

  document.getElementById('groupSearchInput').addEventListener('input', e => {
    renderGroupsList(e.target.value);
  });

  selectDay(currentDay);
  loadGroups();
});
