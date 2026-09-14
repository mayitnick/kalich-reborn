/**
 * Kalich Reborn — Telegram Mini App (TMA) Client
 */

// --- Constants & Config ---
const PAIR_TIMES = [
  { pair: 1, slots: [0, 1], start: "08:20", end: "09:50", startMin: 8 * 60 + 20, endMin: 9 * 60 + 50 },
  { pair: 2, slots: [2, 3], start: "10:00", end: "11:30", startMin: 10 * 60, endMin: 11 * 60 + 30 },
  { pair: 3, slots: [4, 5], start: "11:35", end: "13:10", startMin: 11 * 60 + 35, endMin: 13 * 60 + 10 },
  { pair: 4, slots: [6, 7], start: "13:15", end: "14:45", startMin: 13 * 60 + 15, endMin: 14 * 60 + 45 },
  { pair: 5, slots: [8, 9], start: "14:50", end: "16:25", startMin: 14 * 60 + 50, endMin: 16 * 60 + 25 }
];

const DAY_NAMES = ["Воскресенье", "Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"];
const MONTH_NAMES = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];

// Telegram WebApp SDK
const tg = window.Telegram?.WebApp || null;

function initTelegram() {
  if (tg) {
    try {
      tg.ready();
      tg.expand();
      if (tg.enableClosingConfirmation) {
        tg.enableClosingConfirmation();
      }
    } catch (e) {
      console.warn("Telegram WebApp init warning:", e);
    }
  }
}

function haptic(type = "light") {
  if (!tg?.HapticFeedback) return;
  try {
    if (type === "selection") tg.HapticFeedback.selectionChanged();
    else if (["light", "medium", "heavy", "rigid", "soft"].includes(type)) tg.HapticFeedback.impactOccurred(type);
    else if (["error", "success", "warning"].includes(type)) tg.HapticFeedback.notificationOccurred(type);
  } catch (e) {}
}

// State management
const state = {
  user: {
    id: 1234567,
    name: "Студент",
    username: "",
    photoUrl: ""
  },
  department: 3,
  groupId: null,
  groupName: "",
  groups: [],
  defaultGroup: null,
  theme: localStorage.getItem("kalich_theme") || "tg",
  scheduleCache: {},
  customSelectedDay: null
};

// DOM references
const dom = {
  userAvatar: document.getElementById("user-avatar"),
  userName: document.getElementById("user-name"),
  userGroupBadge: document.getElementById("user-group-badge"),
  btnRefresh: document.getElementById("btn-refresh"),
  btnGroupSelectorToggle: document.getElementById("btn-group-selector-toggle"),
  groupSelectorCard: document.getElementById("group-selector-card"),
  
  // Group selection
  selectDept: document.getElementById("select-dept"),
  selectGroup: document.getElementById("select-group"),
  btnSaveDefault: document.getElementById("btn-save-default"),
  
  // Main Schedule (Сегодня / Завтра)
  bellsLiveIndicator: document.getElementById("bells-live-indicator"),
  liveBellsText: document.getElementById("live-bells-text"),
  todayDateBadge: document.getElementById("today-date-badge"),
  todaySourceBadge: document.getElementById("today-source-badge"),
  todayScheduleList: document.getElementById("today-schedule-list"),
  
  tomorrowTitle: document.getElementById("tomorrow-title"),
  tomorrowDateBadge: document.getElementById("tomorrow-date-badge"),
  tomorrowSourceBadge: document.getElementById("tomorrow-source-badge"),
  tomorrowScheduleList: document.getElementById("tomorrow-schedule-list"),
  
  daysPills: document.getElementById("days-pills"),
  customDayScheduleList: document.getElementById("custom-day-schedule-list"),
  
  // Teachers Tab
  teacherSearchInput: document.getElementById("teacher-search-input"),
  teacherSelectDept: document.getElementById("teacher-select-dept"),
  teacherSelectDay: document.getElementById("teacher-select-day"),
  roomChips: document.getElementById("room-chips"),
  teacherScheduleList: document.getElementById("teacher-schedule-list"),
  
  // Bells Tab
  bellsList: document.getElementById("bells-list"),
  btnCopyIcs: document.getElementById("btn-copy-ics"),
  btnDownloadIcs: document.getElementById("btn-download-ics"),
  
  // Settings Tab
  settingsUserName: document.getElementById("settings-user-name"),
  settingsUserId: document.getElementById("settings-user-id"),
  settingsSavedGroup: document.getElementById("settings-saved-group"),
  serverHealthBadge: document.getElementById("server-health-badge"),
  themeButtons: document.querySelectorAll(".theme-btn"),
  
  // Navigation
  navItems: document.querySelectorAll(".nav-item"),
  tabViews: document.querySelectorAll(".tab-view"),
  toastContainer: document.getElementById("toast-container")
};

function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = "toast";
  if (type === "success") {
    toast.innerHTML = `<span style="color:var(--success-color);">✓</span> <span>${escapeHtml(message)}</span>`;
  } else if (type === "error") {
    toast.innerHTML = `<span style="color:var(--danger-color);">✕</span> <span>${escapeHtml(message)}</span>`;
  } else {
    toast.innerHTML = `<span>ℹ️</span> <span>${escapeHtml(message)}</span>`;
  }

  dom.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(-10px) scale(0.95)";
    setTimeout(() => toast.remove(), 200);
  }, 2600);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

async function apiFetch(url, options = {}) {
  const headers = options.headers || {};
  if (tg && tg.initData) {
    headers["Authorization"] = `Bearer ${tg.initData}`;
  }
  return fetch(url, { ...options, headers });
}

function formatDate(date) {
  const day = date.getDate();
  const month = MONTH_NAMES[date.getMonth()];
  return `${day} ${month}`;
}

function getTodayAndTomorrowDays() {
  const now = new Date();
  const dayOfWeek = now.getDay(); // 0 is Sunday, 1 is Monday ... 6 is Saturday
  
  let todayDayNum = dayOfWeek === 0 ? 7 : dayOfWeek; // 1-7
  
  const tomorrowDate = new Date(now);
  tomorrowDate.setDate(now.getDate() + 1);
  const tomorrowDayOfWeek = tomorrowDate.getDay();
  let tomorrowDayNum = tomorrowDayOfWeek === 0 ? 1 : tomorrowDayOfWeek; // If Sunday, point to Monday

  return {
    todayDayNum,
    todayDateStr: `${DAY_NAMES[dayOfWeek]}, ${formatDate(now)}`,
    tomorrowDayNum,
    tomorrowDateStr: tomorrowDayOfWeek === 0 ? `Пн, ${formatDate(new Date(now.getTime() + 2 * 86400000))} (следующий учебный день)` : `${DAY_NAMES[tomorrowDayOfWeek]}, ${formatDate(tomorrowDate)}`,
    isTodaySunday: dayOfWeek === 0
  };
}

function setupUserInfo() {
  if (tg?.initDataUnsafe?.user) {
    const u = tg.initDataUnsafe.user;
    state.user.id = u.id;
    state.user.name = [u.first_name, u.last_name].filter(Boolean).join(" ") || "Студент";
    state.user.username = u.username || "";
    state.user.photoUrl = u.photo_url || "";
  }

  dom.userName.textContent = state.user.name;
  dom.settingsUserName.textContent = state.user.name;
  dom.settingsUserId.textContent = String(state.user.id);

  if (state.user.photoUrl) {
    dom.userAvatar.innerHTML = `<img src="${state.user.photoUrl}" alt="Avatar">`;
  } else {
    const initials = state.user.name.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase();
    dom.userAvatar.textContent = initials || "КП";
  }

  const savedDefault = localStorage.getItem("kalich_default_group");
  if (savedDefault) {
    try {
      const parsed = JSON.parse(savedDefault);
      state.defaultGroup = parsed;
      state.department = parsed.department || 3;
      state.groupId = parsed.group_id;
      state.groupName = parsed.group_name || "";
      dom.selectDept.value = String(state.department);
      dom.userGroupBadge.textContent = state.groupName || `Группа ${state.groupId}`;
      dom.settingsSavedGroup.textContent = state.groupName || `Группа ${state.groupId}`;
    } catch (e) {
      console.warn("Failed to parse default group:", e);
    }
  }
}

async function loadGroups() {
  try {
    const res = await apiFetch("/api/groups");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    state.groups = await res.json();
    populateGroupSelect();
  } catch (err) {
    console.error("Failed to load groups:", err);
    showToast("Ошибка загрузки списка групп", "error");
    dom.selectGroup.innerHTML = `<option value="">Ошибка загрузки</option>`;
  }
}

function populateGroupSelect() {
  const currentDept = parseInt(dom.selectDept.value, 10);
  const filtered = state.groups.filter(g => g.department === currentDept);

  dom.selectGroup.innerHTML = "";
  if (filtered.length === 0) {
    dom.selectGroup.innerHTML = `<option value="">Группы не найдены</option>`;
    return;
  }

  filtered.forEach(g => {
    const opt = document.createElement("option");
    opt.value = g.group_id;
    opt.textContent = g.group_name;
    if (state.groupId && g.group_id === state.groupId) {
      opt.selected = true;
    }
    dom.selectGroup.appendChild(opt);
  });

  if (!state.groupId || !filtered.some(g => g.group_id === state.groupId)) {
    state.groupId = filtered[0].group_id;
    state.groupName = filtered[0].group_name;
    dom.selectGroup.value = state.groupId;
  } else {
    const selected = filtered.find(g => g.group_id === state.groupId);
    if (selected) state.groupName = selected.group_name;
  }

  updateGroupBadge();
  loadMainDashboardSchedule();
}

function updateGroupBadge() {
  if (state.groupName) {
    dom.userGroupBadge.textContent = `${state.groupName} ▾`;
  } else {
    dom.userGroupBadge.textContent = "Выбрать группу ▾";
  }
}

// --- Main Dashboard: Загрузка СЕГОДНЯ + ЗАВТРА ---
async function loadMainDashboardSchedule() {
  if (!state.groupId) return;

  const dates = getTodayAndTomorrowDays();
  dom.todayDateBadge.textContent = dates.todayDateStr;
  dom.tomorrowDateBadge.textContent = dates.tomorrowDateStr;

  // 1. Загрузка СЕГОДНЯ
  if (dates.isTodaySunday) {
    dom.todayScheduleList.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🎉</div>
        <p>Сегодня воскресенье — выходной день! Ниже расписание на понедельник.</p>
      </div>
    `;
    dom.todaySourceBadge.textContent = "Выходной";
  } else {
    loadSingleSchedule(dates.todayDayNum, dom.todayScheduleList, dom.todaySourceBadge, true);
  }

  // 2. Загрузка ЗАВТРА
  loadSingleSchedule(dates.tomorrowDayNum, dom.tomorrowScheduleList, dom.tomorrowSourceBadge, false);
}

async function loadSingleSchedule(day, targetListEl, sourceBadgeEl, isToday = false) {
  const dept = dom.selectDept.value;
  const gid = state.groupId;
  const cacheKey = `sch_${dept}_${gid}_${day}`;

  targetListEl.innerHTML = `
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Загрузка расписания...</p>
    </div>
  `;

  try {
    const res = await apiFetch(`/api/schedule?department=${dept}&group_id=${gid}&day=${day}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    localStorage.setItem(cacheKey, JSON.stringify(data));
    state.scheduleCache[cacheKey] = data;

    renderScheduleCards(data.lessons || [], targetListEl, sourceBadgeEl, data.source || "server", isToday);
  } catch (err) {
    const cached = localStorage.getItem(cacheKey);
    if (cached) {
      const data = JSON.parse(cached);
      renderScheduleCards(data.lessons || [], targetListEl, sourceBadgeEl, "offline-cache", isToday);
    } else {
      targetListEl.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">⚠️</div>
          <p>Не удалось получить данные с сервера.</p>
        </div>
      `;
    }
  }
}

function renderScheduleCards(lessons, targetListEl, sourceBadgeEl, source, isToday) {
  if (sourceBadgeEl) {
    sourceBadgeEl.textContent = source === "offline-cache" ? "Офлайн" : "Актуально";
    sourceBadgeEl.className = `badge ${source === "offline-cache" ? "badge-warning" : "badge-success"}`;
  }

  if (!lessons || lessons.length === 0) {
    targetListEl.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🎉</div>
        <p>В этот день занятий нет.</p>
      </div>
    `;
    return;
  }

  const pairsData = PAIR_TIMES.map(pInfo => {
    const lesson = lessons.find(l => pInfo.slots.includes(l.slot_idx) && l.subject && l.subject.trim());
    return {
      ...pInfo,
      lesson: lesson || null
    };
  });

  const hasAny = pairsData.some(p => p.lesson !== null);
  if (!hasAny) {
    targetListEl.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🎉</div>
        <p>Пар не запланировано.</p>
      </div>
    `;
    return;
  }

  const now = new Date();
  const currentMinutes = now.getHours() * 60 + now.getMinutes();

  let html = "";
  pairsData.forEach(p => {
    const isCurrent = isToday && currentMinutes >= p.startMin && currentMinutes <= p.endMin;

    if (!p.lesson) {
      html += `
        <div class="lesson-card ${isCurrent ? "is-current" : ""}" style="opacity: 0.55;">
          <div class="lesson-header">
            <span class="lesson-pair-num">${p.pair} ПАРА</span>
            <span class="lesson-time">${p.start} — ${p.end}</span>
          </div>
          <div class="lesson-title" style="font-size: 13px; font-weight: 500; color: var(--hint-color);">
            Окно (пар нет)
          </div>
        </div>
      `;
      return;
    }

    const l = p.lesson;
    const isOverride = Boolean(l.is_override);
    const roomStr = l.room ? `каб. ${escapeHtml(l.room)}` : "Каб. не указан";
    const teacherStr = l.teacher ? escapeHtml(l.teacher) : "Преподаватель не указан";

    html += `
      <div class="lesson-card ${isCurrent ? "is-current" : ""} ${isOverride ? "is-override" : ""}">
        <div class="lesson-header">
          <span class="lesson-pair-num">${p.pair} ПАРА</span>
          ${isCurrent ? '<span class="lesson-current-tag"><span class="live-dot pulse"></span> Идёт сейчас</span>' : ''}
          <span class="lesson-time">${p.start} — ${p.end}</span>
        </div>
        <div class="lesson-title">
          ${escapeHtml(l.subject)}
        </div>
        <div class="lesson-footer">
          <span class="lesson-teacher">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
            ${teacherStr}
          </span>
          <span class="lesson-room">${roomStr}</span>
        </div>
        ${isOverride ? `
          <div class="lesson-override-note">
            ⚠️ Замена: ${escapeHtml(l.override_note || "Изменение в расписании")}
          </div>
        ` : ''}
      </div>
    `;
  });

  targetListEl.innerHTML = html;
}

// --- Custom Day View (Вся неделя) ---
async function loadCustomDay(day) {
  state.customSelectedDay = day;
  dom.customDayScheduleList.classList.remove("hidden");
  loadSingleSchedule(day, dom.customDayScheduleList, null, false);
}

// --- Live Bells Timer ---
function updateLiveBellsTimer() {
  const now = new Date();
  const currentMinutes = now.getHours() * 60 + now.getMinutes();
  const dayOfWeek = now.getDay();

  let activePair = null;
  let nextPair = null;

  PAIR_TIMES.forEach(p => {
    if (currentMinutes >= p.startMin && currentMinutes <= p.endMin) {
      activePair = p;
    } else if (currentMinutes < p.startMin && !nextPair) {
      nextPair = p;
    }
  });

  if (dayOfWeek === 0) {
    dom.liveBellsText.textContent = "Сегодня выходной день 🎉";
  } else if (activePair) {
    const remaining = activePair.endMin - currentMinutes;
    dom.liveBellsText.textContent = `Сейчас идёт ${activePair.pair} пара (до звонка: ${remaining} мин)`;
  } else if (nextPair) {
    const until = nextPair.startMin - currentMinutes;
    dom.liveBellsText.textContent = `Перемена. До ${nextPair.pair} пары: ${until} мин`;
  } else {
    dom.liveBellsText.textContent = "Все пары на сегодня завершены 👋";
  }

  // Bells Tab Render
  let listHtml = "";
  PAIR_TIMES.forEach(p => {
    const isActive = activePair && activePair.pair === p.pair;
    listHtml += `
      <div class="bell-row ${isActive ? "is-active" : ""}">
        <span class="bell-number">${p.pair} пара</span>
        <span class="bell-time">${p.start} — ${p.end}</span>
      </div>
    `;
  });
  dom.bellsList.innerHTML = listHtml;
}

// --- Teachers & Rooms Tab Logic ---
let searchDebounce = null;

async function searchTeacherSchedule() {
  const query = dom.teacherSearchInput.value.trim();
  const dept = dom.teacherSelectDept.value;
  const day = dom.teacherSelectDay.value;

  if (!query) {
    dom.teacherScheduleList.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🔍</div>
        <p>Введите номер кабинета или ФИО преподавателя</p>
      </div>
    `;
    return;
  }

  dom.teacherScheduleList.innerHTML = `
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Поиск занятий...</p>
    </div>
  `;

  try {
    const isNumericRoom = /^\d+$/.test(query);
    let url = `/api/teacher/schedule?department=${dept}&day=${day}`;
    if (isNumericRoom) {
      url += `&rooms=${encodeURIComponent(query)}`;
    } else {
      url += `&teacher_name=${encodeURIComponent(query)}`;
    }

    const res = await apiFetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    renderTeacherSchedule(data.schedule || [], query);
  } catch (err) {
    dom.teacherScheduleList.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚠️</div>
        <p>Ошибка при поиске занятий.</p>
      </div>
    `;
  }
}

function renderTeacherSchedule(schedule = [], query = "") {
  if (!schedule || schedule.length === 0) {
    dom.teacherScheduleList.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📖</div>
        <p>Занятий по запросу «${escapeHtml(query)}» не найдено.</p>
      </div>
    `;
    return;
  }

  let html = "";
  schedule.forEach(item => {
    const pairNum = Math.floor(item.slot_idx / 2) + 1;
    const pInfo = PAIR_TIMES.find(p => p.pair === pairNum) || { start: "", end: "" };

    html += `
      <div class="lesson-card ${item.is_override ? "is-override" : ""}">
        <div class="lesson-header">
          <span class="lesson-pair-num">${pairNum} ПАРА</span>
          <span class="lesson-time">${pInfo.start} — ${pInfo.end}</span>
        </div>
        <div class="lesson-title">
          ${escapeHtml(item.subject)}
        </div>
        <div class="lesson-footer">
          <span class="lesson-teacher">
            <strong>Группа:</strong> ${escapeHtml(item.group_name || "-")}
            ${item.teacher ? ` • ${escapeHtml(item.teacher)}` : ""}
          </span>
          <span class="lesson-room">Каб. ${escapeHtml(item.room || "-")}</span>
        </div>
      </div>
    `;
  });

  dom.teacherScheduleList.innerHTML = html;
}

// --- Calendar Actions (.ics) ---
function setupCalendarActions() {
  dom.btnCopyIcs.addEventListener("click", () => {
    haptic("light");
    if (!state.groupId) {
      showToast("Сначала выберите группу", "error");
      return;
    }
    const dept = dom.selectDept.value;
    const icsUrl = `${window.location.origin}/api/calendar/${dept}/${state.groupId}.ics`;

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(icsUrl).then(() => {
        showToast("Ссылка на календарь скопирована!", "success");
      }).catch(() => fallbackCopy(icsUrl));
    } else {
      fallbackCopy(icsUrl);
    }
  });

  dom.btnDownloadIcs.addEventListener("click", () => {
    haptic("medium");
    if (!state.groupId) {
      showToast("Сначала выберите группу", "error");
      return;
    }
    const dept = dom.selectDept.value;
    window.location.href = `/api/calendar/${dept}/${state.groupId}.ics`;
  });
}

function fallbackCopy(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand("copy");
    showToast("Ссылка скопирована!", "success");
  } catch (e) {
    showToast("Не удалось скопировать", "error");
  }
  document.body.removeChild(ta);
}

// --- Health Check ---
async function checkServerHealth() {
  try {
    const res = await apiFetch("/api/health");
    if (res.ok) {
      dom.serverHealthBadge.textContent = "В сети";
      dom.serverHealthBadge.className = "badge badge-success";
    }
  } catch (e) {
    dom.serverHealthBadge.textContent = "Офлайн";
    dom.serverHealthBadge.className = "badge badge-warning";
  }
}

// --- Theme Management ---
function applyTheme(theme) {
  state.theme = theme;
  localStorage.setItem("kalich_theme", theme);

  dom.themeButtons.forEach(btn => {
    btn.classList.toggle("active", btn.dataset.theme === theme);
  });

  if (theme === "tg") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.setAttribute("data-theme", theme);
  }
}

// --- Save Default Group ---
async function saveDefaultGroup() {
  haptic("medium");
  if (!state.groupId) return;

  const payload = {
    department: parseInt(dom.selectDept.value, 10),
    group_id: state.groupId,
    group_name: state.groupName,
    role: "student"
  };

  localStorage.setItem("kalich_default_group", JSON.stringify(payload));
  state.defaultGroup = payload;
  dom.settingsSavedGroup.textContent = state.groupName;

  try {
    await apiFetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    showToast(`Группа ${state.groupName} сохранена по умолчанию!`, "success");
  } catch (e) {
    showToast(`Группа ${state.groupName} сохранена локально!`, "success");
  }

  dom.groupSelectorCard.classList.add("hidden");
}

// --- Event Handlers ---
function setupEventListeners() {
  // Navigation tabs
  dom.navItems.forEach(btn => {
    btn.addEventListener("click", () => {
      haptic("selection");
      const targetTab = btn.dataset.tab;

      dom.navItems.forEach(b => b.classList.remove("active"));
      dom.tabViews.forEach(v => v.classList.remove("active"));

      btn.classList.add("active");
      const view = document.getElementById(targetTab);
      if (view) view.classList.add("active");

      if (targetTab === "tab-bells") {
        updateLiveBellsTimer();
      }
    });
  });

  // Toggle group selector
  dom.btnGroupSelectorToggle.addEventListener("click", () => {
    haptic("light");
    dom.groupSelectorCard.classList.toggle("hidden");
  });

  dom.userGroupBadge.addEventListener("click", () => {
    haptic("light");
    dom.groupSelectorCard.classList.toggle("hidden");
  });

  dom.selectDept.addEventListener("change", () => {
    haptic("light");
    state.department = parseInt(dom.selectDept.value, 10);
    populateGroupSelect();
  });

  dom.selectGroup.addEventListener("change", () => {
    haptic("light");
    state.groupId = parseInt(dom.selectGroup.value, 10);
    const selected = state.groups.find(g => g.group_id === state.groupId && g.department === parseInt(dom.selectDept.value, 10));
    if (selected) state.groupName = selected.group_name;
    updateGroupBadge();
    loadMainDashboardSchedule();
  });

  dom.btnSaveDefault.addEventListener("click", saveDefaultGroup);

  // Refresh
  dom.btnRefresh.addEventListener("click", () => {
    haptic("medium");
    showToast("Обновление данных...", "info");
    loadGroups().then(() => loadMainDashboardSchedule());
    updateLiveBellsTimer();
    checkServerHealth();
  });

  // Week day pills
  dom.daysPills.querySelectorAll(".day-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      haptic("selection");
      const day = parseInt(pill.dataset.day, 10);
      if (state.customSelectedDay === day && !dom.customDayScheduleList.classList.contains("hidden")) {
        // Toggle hide
        dom.customDayScheduleList.classList.add("hidden");
        pill.classList.remove("active");
        state.customSelectedDay = null;
        return;
      }

      dom.daysPills.querySelectorAll(".day-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      loadCustomDay(day);
    });
  });

  // Teachers search
  dom.teacherSearchInput.addEventListener("input", () => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(searchTeacherSchedule, 350);
  });

  dom.teacherSelectDept.addEventListener("change", searchTeacherSchedule);
  dom.teacherSelectDay.addEventListener("change", searchTeacherSchedule);

  // Room chips
  dom.roomChips.querySelectorAll(".chip").forEach(chip => {
    chip.addEventListener("click", () => {
      haptic("selection");
      dom.teacherSearchInput.value = chip.dataset.room;
      dom.roomChips.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      searchTeacherSchedule();
    });
  });

  // Theme
  dom.themeButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      haptic("light");
      applyTheme(btn.dataset.theme);
    });
  });

  setupCalendarActions();
}

// Bootstrap
window.addEventListener("DOMContentLoaded", () => {
  initTelegram();
  setupUserInfo();
  applyTheme(state.theme);
  setupEventListeners();
  loadGroups();
  updateLiveBellsTimer();
  checkServerHealth();

  setInterval(updateLiveBellsTimer, 60000);
});
