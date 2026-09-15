/**
 * Kalich Reborn — Telegram Mini App (TMA) Client
 */

// --- Constants & Config ---
const LESSON_CALLS = [
  { slot: 0, num: 1, start: "08:20", end: "09:05", startMin: 8 * 60 + 20, endMin: 9 * 60 + 5 },
  { slot: 1, num: 2, start: "09:05", end: "09:50", startMin: 9 * 60 + 5, endMin: 9 * 60 + 50 },
  { slot: 2, num: 3, start: "10:00", end: "10:45", startMin: 10 * 60, endMin: 10 * 60 + 45 },
  { slot: 3, num: 4, start: "10:45", end: "11:30", startMin: 10 * 60 + 45, endMin: 11 * 60 + 30 },
  { slot: 4, num: 5, start: "11:35", end: "12:20", startMin: 11 * 60 + 35, endMin: 12 * 60 + 20 },
  { slot: 5, num: 6, start: "12:25", end: "13:10", startMin: 12 * 60 + 25, endMin: 13 * 60 + 10 },
  { slot: 6, num: 7, start: "13:15", end: "14:00", startMin: 13 * 60 + 15, endMin: 14 * 60 },
  { slot: 7, num: 8, start: "14:00", end: "14:45", startMin: 14 * 60, endMin: 14 * 60 + 45 },
  { slot: 8, num: 9, start: "14:50", end: "15:35", startMin: 14 * 60 + 50, endMin: 15 * 60 + 35 },
  { slot: 9, num: 10, start: "15:40", end: "16:25", startMin: 15 * 60 + 40, endMin: 16 * 60 + 25 }
];

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
  liveStatusTitle: document.getElementById("live-status-title"),
  liveRoomBadge: document.getElementById("live-room-badge"),
  liveLessonName: document.getElementById("live-lesson-name"),
  liveSubgroupInfo: document.getElementById("live-subgroup-info"),
  liveTimeRange: document.getElementById("live-time-range"),
  liveTimeLeft: document.getElementById("live-time-left"),
  liveProgressBar: document.getElementById("live-progress-bar"),
  liveNextRow: document.getElementById("live-next-row"),
  liveNextContent: document.getElementById("live-next-content"),
  todayDateBadge: document.getElementById("today-date-badge"),
  todaySourceBadge: document.getElementById("today-source-badge"),
  todayScheduleList: document.getElementById("today-schedule-list"),
  
  tomorrowTitle: document.getElementById("tomorrow-title"),
  tomorrowDateBadge: document.getElementById("tomorrow-date-badge"),
  tomorrowSourceBadge: document.getElementById("tomorrow-source-badge"),
  tomorrowScheduleList: document.getElementById("tomorrow-schedule-list"),
  
  daysPills: document.getElementById("days-pills"),
  customDayScheduleList: document.getElementById("custom-day-schedule-list"),
  
  // Find Tab (/f & /w)
  findModeRoomBtn: document.getElementById("btn-mode-room"),
  findModeGroupBtn: document.getElementById("btn-mode-group"),
  findSearchInput: document.getElementById("find-search-input"),
  findDeptWrapper: document.getElementById("find-dept-wrapper"),
  findSelectDept: document.getElementById("find-select-dept"),
  findSelectDay: document.getElementById("find-select-day"),
  findQuickChips: document.getElementById("find-quick-chips"),
  findResultsList: document.getElementById("find-results-list"),
  findEmptyHint: document.getElementById("find-empty-hint"),
  
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
  // Only attach Authorization header if not a GET or explicitly requested
  if (options.method && options.method !== 'GET' && tg && tg.initData) {
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
    const data = await res.json();
    const rawGroups = data.groups || data;
    const list = [];
    for (const [name, info] of Object.entries(rawGroups)) {
      if (Array.isArray(info)) {
        list.push({ department: Number(info[0]), group_id: Number(info[1]), group_name: name });
      } else if (info && typeof info === 'object') {
        list.push({ department: Number(info.department), group_id: Number(info.group_id), group_name: info.group_name || name });
      }
    }
    list.sort((a, b) => a.group_name.localeCompare(b.group_name, 'ru'));
    state.groups = list;
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
    const rawLessons = Array.isArray(data) ? data : (data.lessons || []);

    localStorage.setItem(cacheKey, JSON.stringify(rawLessons));
    state.scheduleCache[cacheKey] = rawLessons;

    renderScheduleCards(rawLessons, targetListEl, sourceBadgeEl, "server", isToday);
  } catch (err) {
    const cached = localStorage.getItem(cacheKey);
    if (cached) {
      const data = JSON.parse(cached);
      const rawLessons = Array.isArray(data) ? data : (data.lessons || []);
      renderScheduleCards(rawLessons, targetListEl, sourceBadgeEl, "offline-cache", isToday);
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

function parseLessonSlot(rawItem, slotIdx) {
  if (!rawItem) return null;
  if (typeof rawItem === "object") {
    if (!rawItem.subject || !rawItem.subject.trim()) return null;
    return {
      slot_idx: slotIdx,
      subject: rawItem.subject.trim(),
      room: rawItem.room || "",
      teacher: rawItem.teacher || "",
      is_override: Boolean(rawItem.is_override),
      override_note: rawItem.override_note || ""
    };
  }
  if (typeof rawItem === "string") {
    const trimmed = rawItem.trim();
    if (!trimmed || trimmed.toUpperCase() === "ОБЕД" || trimmed === "-") return null;
    const match = trimmed.match(/^(.*?)(?:\s*\((.*?)\))?$/);
    const room = match ? (match[2] || "").trim() : "";
    const subject = match ? (match[1] || "").trim() : trimmed;
    return {
      slot_idx: slotIdx,
      subject,
      room,
      teacher: "",
      is_override: false,
      override_note: ""
    };
  }
  return null;
}

function cleanSubjectForGrouping(t) {
  return String(t || "").replace(/\(.*?\)/g, "").trim().toLowerCase();
}

function buildLessonBlocks(lessons) {
  if (!lessons || lessons.length === 0) return [];
  const total = Math.min(lessons.length, LESSON_CALLS.length);
  const blocks = [];
  let i = 0;

  while (i < total) {
    const rawFirst = lessons[i];
    const parsedFirst = parseLessonSlot(rawFirst, i);

    if (!parsedFirst) {
      i++;
      continue;
    }

    const firstIdx = i;
    const target = cleanSubjectForGrouping(parsedFirst.subject);
    let lastIdx = i;

    while (lastIdx + 1 < total) {
      const nextParsed = parseLessonSlot(lessons[lastIdx + 1], lastIdx + 1);
      if (!nextParsed) break;
      if (cleanSubjectForGrouping(nextParsed.subject) !== target) break;
      if (parsedFirst.room && nextParsed.room && parsedFirst.room !== nextParsed.room) break;
      lastIdx++;
    }

    const startCall = LESSON_CALLS[firstIdx];
    const endCall = LESSON_CALLS[lastIdx];
    const durationMin = endCall.endMin - startCall.startMin;
    const count = lastIdx - firstIdx + 1;
    const lessonNumsStr = firstIdx === lastIdx
      ? `${firstIdx + 1} УРОК`
      : `${firstIdx + 1}–${lastIdx + 1} УРОКИ`;

    blocks.push({
      firstIdx,
      lastIdx,
      firstNum: firstIdx + 1,
      lastNum: lastIdx + 1,
      lessonNumsStr,
      startTime: startCall.start,
      endTime: endCall.end,
      startMin: startCall.startMin,
      endMin: endCall.endMin,
      durationMin,
      count,
      subject: parsedFirst.subject,
      room: parsedFirst.room,
      teacher: parsedFirst.teacher,
      is_override: parsedFirst.is_override,
      override_note: parsedFirst.override_note
    });

    i = lastIdx + 1;
  }

  return blocks;
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

  const blocks = buildLessonBlocks(lessons);

  if (blocks.length === 0) {
    targetListEl.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🎉</div>
        <p>Пар и уроков не запланировано.</p>
      </div>
    `;
    return;
  }

  const now = new Date();
  const currentMinutes = now.getHours() * 60 + now.getMinutes();

  let html = "";
  blocks.forEach(b => {
    const isCurrent = isToday && currentMinutes >= b.startMin && currentMinutes <= b.endMin;
    const isOverride = Boolean(b.is_override);
    const roomStr = b.room ? `каб. ${escapeHtml(b.room)}` : "Каб. не указан";
    const teacherStr = b.teacher ? escapeHtml(b.teacher) : "Преподаватель не указан";

    html += `
      <div class="lesson-card ${isCurrent ? "is-current" : ""} ${isOverride ? "is-override" : ""}">
        <div class="lesson-header">
          <div class="lesson-meta-left">
            <span class="lesson-pair-num">${escapeHtml(b.lessonNumsStr)}</span>
            <span class="lesson-duration-badge">${b.durationMin} мин</span>
            ${isCurrent ? '<span class="lesson-current-tag"><span class="live-dot pulse"></span> Идёт сейчас</span>' : ''}
          </div>
          <span class="lesson-time">${b.startTime} — ${b.endTime}</span>
        </div>
        <div class="lesson-title">
          ${escapeHtml(b.subject)}
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
            ⚠️ Замена: ${escapeHtml(b.override_note || "Изменение в расписании")}
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

// --- Live Bells Timer & Now Widget ---
function updateLiveBellsTimer() {
  const now = new Date();
  const currentMinutes = now.getHours() * 60 + now.getMinutes();
  const dayOfWeek = now.getDay();
  const dates = getTodayAndTomorrowDays();
  const dept = dom.selectDept ? dom.selectDept.value : 3;
  const gid = state.groupId;
  const cacheKey = `sch_${dept}_${gid}_${dates.todayDayNum}`;
  const todayLessons = state.scheduleCache[cacheKey] || [];
  const blocks = buildLessonBlocks(todayLessons);

  const banner = dom.bellsLiveIndicator;
  if (!banner) return;

  if (dayOfWeek === 0) {
    banner.classList.remove("has-active");
    if (dom.liveStatusTitle) dom.liveStatusTitle.textContent = "Выходной";
    if (dom.liveRoomBadge) dom.liveRoomBadge.style.display = "none";
    if (dom.liveLessonName) dom.liveLessonName.textContent = "Сегодня выходной! Отдыхай и набирайся сил~ [^ v ^]";
    if (dom.liveSubgroupInfo) dom.liveSubgroupInfo.style.display = "none";
    if (dom.liveTimeRange) dom.liveTimeRange.textContent = "Занятий нет";
    if (dom.liveTimeLeft) dom.liveTimeLeft.textContent = "Отдых";
    if (dom.liveProgressBar) dom.liveProgressBar.style.width = "0%";
    if (dom.liveNextRow) dom.liveNextRow.style.display = "none";
  } else if (blocks.length > 0) {
    const firstBlock = blocks[0];
    const lastBlock = blocks[blocks.length - 1];

    let activeBlock = null;
    let nextBlock = null;

    for (let i = 0; i < blocks.length; i++) {
      const b = blocks[i];
      if (currentMinutes >= b.startMin && currentMinutes <= b.endMin) {
        activeBlock = b;
        nextBlock = blocks[i + 1] || null;
        break;
      } else if (currentMinutes < b.startMin) {
        nextBlock = b;
        break;
      }
    }

    if (currentMinutes < firstBlock.startMin) {
      // Before classes start
      banner.classList.remove("has-active");
      const untilStart = firstBlock.startMin - currentMinutes;
      const untilStr = untilStart >= 60
        ? `${Math.floor(untilStart / 60)}ч ${untilStart % 60}м`
        : `${untilStart} мин`;

      if (dom.liveStatusTitle) dom.liveStatusTitle.textContent = `До начала пар: ${untilStr}`;
      if (dom.liveRoomBadge) {
        dom.liveRoomBadge.style.display = firstBlock.room ? "inline-block" : "none";
        dom.liveRoomBadge.textContent = firstBlock.room ? `каб. ${firstBlock.room}` : "";
      }
      if (dom.liveLessonName) dom.liveLessonName.textContent = `1 урок: ${firstBlock.subject}`;
      if (dom.liveSubgroupInfo) dom.liveSubgroupInfo.style.display = "none";
      if (dom.liveTimeRange) dom.liveTimeRange.textContent = `Начало в ${firstBlock.startTime}`;
      if (dom.liveTimeLeft) dom.liveTimeLeft.textContent = `через ${untilStr}`;
      if (dom.liveProgressBar) dom.liveProgressBar.style.width = "0%";
      if (dom.liveNextRow) dom.liveNextRow.style.display = "none";

    } else if (activeBlock) {
      // Currently during a class block
      banner.classList.add("has-active");
      if (dom.liveStatusTitle) dom.liveStatusTitle.textContent = `Сейчас идёт: ${activeBlock.lessonNumsStr}`;
      if (dom.liveRoomBadge) {
        dom.liveRoomBadge.style.display = activeBlock.room ? "inline-block" : "none";
        dom.liveRoomBadge.textContent = activeBlock.room ? `каб. ${activeBlock.room}` : "";
      }
      if (dom.liveLessonName) dom.liveLessonName.textContent = activeBlock.subject;

      if (dom.liveSubgroupInfo) {
        const extra = activeBlock.teacher ? `Преподаватель: ${activeBlock.teacher}` : "";
        if (extra) {
          dom.liveSubgroupInfo.style.display = "block";
          dom.liveSubgroupInfo.textContent = extra;
        } else {
          dom.liveSubgroupInfo.style.display = "none";
        }
      }

      if (dom.liveTimeRange) dom.liveTimeRange.textContent = `Время: ${activeBlock.startTime} — ${activeBlock.endTime}`;

      const elapsed = currentMinutes - activeBlock.startMin;
      const duration = activeBlock.endMin - activeBlock.startMin;
      const pct = Math.min(100, Math.max(0, Math.round((elapsed / Math.max(1, duration)) * 100)));
      const remaining = activeBlock.endMin - currentMinutes;
      const remHours = Math.floor(remaining / 60);
      const remMins = remaining % 60;
      const remStr = remHours > 0 ? `${remHours}ч ${remMins}м` : `${remMins} мин`;

      if (dom.liveTimeLeft) dom.liveTimeLeft.textContent = `Осталось: ${remStr} (${pct}%)`;
      if (dom.liveProgressBar) dom.liveProgressBar.style.width = `${pct}%`;

      if (dom.liveNextRow) {
        if (nextBlock) {
          dom.liveNextRow.style.display = "flex";
          if (dom.liveNextContent) {
            dom.liveNextContent.textContent = `${nextBlock.firstNum}. ${nextBlock.subject} (${nextBlock.startTime} — ${nextBlock.endTime})`;
          }
        } else {
          dom.liveNextRow.style.display = "flex";
          if (dom.liveNextContent) {
            dom.liveNextContent.textContent = "Это последняя пара на сегодня [^ v ^]";
          }
        }
      }

    } else if (nextBlock) {
      // Break (перемена) between blocks
      banner.classList.remove("has-active");
      const untilNext = nextBlock.startMin - currentMinutes;
      if (dom.liveStatusTitle) dom.liveStatusTitle.textContent = `Перемена (до звонка: ${untilNext} мин)`;
      if (dom.liveRoomBadge) {
        dom.liveRoomBadge.style.display = nextBlock.room ? "inline-block" : "none";
        dom.liveRoomBadge.textContent = nextBlock.room ? `каб. ${nextBlock.room}` : "";
      }
      if (dom.liveLessonName) dom.liveLessonName.textContent = `Следующий: ${nextBlock.subject}`;
      if (dom.liveSubgroupInfo) dom.liveSubgroupInfo.style.display = "none";
      if (dom.liveTimeRange) dom.liveTimeRange.textContent = `Звонок в ${nextBlock.startTime}`;
      if (dom.liveTimeLeft) dom.liveTimeLeft.textContent = `${untilNext} мин перерыва`;
      if (dom.liveProgressBar) dom.liveProgressBar.style.width = "0%";
      if (dom.liveNextRow) dom.liveNextRow.style.display = "none";

    } else {
      // All blocks ended for today
      banner.classList.remove("has-active");
      if (dom.liveStatusTitle) dom.liveStatusTitle.textContent = "Все пары завершены";
      if (dom.liveRoomBadge) dom.liveRoomBadge.style.display = "none";
      if (dom.liveLessonName) dom.liveLessonName.textContent = "Все занятия на сегодня закончились! Можно отдыхать [^ v ^]";
      if (dom.liveSubgroupInfo) dom.liveSubgroupInfo.style.display = "none";
      if (dom.liveTimeRange) dom.liveTimeRange.textContent = "Учебный день завершён";
      if (dom.liveTimeLeft) dom.liveTimeLeft.textContent = "Свободное время 🎉";
      if (dom.liveProgressBar) dom.liveProgressBar.style.width = "100%";
      if (dom.liveNextRow) dom.liveNextRow.style.display = "none";
    }

  } else {
    // Fallback based on generic bells
    banner.classList.remove("has-active");
    let activePair = null;
    let nextPair = null;
    PAIR_TIMES.forEach(p => {
      if (currentMinutes >= p.startMin && currentMinutes <= p.endMin) {
        activePair = p;
      } else if (currentMinutes < p.startMin && !nextPair) {
        nextPair = p;
      }
    });

    if (activePair) {
      const remaining = activePair.endMin - currentMinutes;
      if (dom.liveStatusTitle) dom.liveStatusTitle.textContent = `Сейчас идёт ${activePair.pair} пара`;
      if (dom.liveLessonName) dom.liveLessonName.textContent = `Звонок через ${remaining} мин`;
      if (dom.liveTimeRange) dom.liveTimeRange.textContent = `${activePair.start} — ${activePair.end}`;
      if (dom.liveTimeLeft) dom.liveTimeLeft.textContent = `${remaining} мин`;
    } else if (nextPair) {
      const until = nextPair.startMin - currentMinutes;
      if (dom.liveStatusTitle) dom.liveStatusTitle.textContent = `Перемена`;
      if (dom.liveLessonName) dom.liveLessonName.textContent = `До ${nextPair.pair} пары: ${until} мин`;
      if (dom.liveTimeRange) dom.liveTimeRange.textContent = `Начало в ${nextPair.start}`;
      if (dom.liveTimeLeft) dom.liveTimeLeft.textContent = `${until} мин`;
    } else {
      if (dom.liveStatusTitle) dom.liveStatusTitle.textContent = `Занятий нет`;
      if (dom.liveLessonName) dom.liveLessonName.textContent = `Все пары на сегодня завершены 👋`;
      if (dom.liveTimeRange) dom.liveTimeRange.textContent = `-`;
      if (dom.liveTimeLeft) dom.liveTimeLeft.textContent = `Отдых`;
    }
  }

  // Bells Tab Render
  let listHtml = "";
  LESSON_CALLS.forEach(c => {
    const isActive = currentMinutes >= c.startMin && currentMinutes <= c.endMin;
    listHtml += `
      <div class="bell-row ${isActive ? "is-active" : ""}">
        <span class="bell-number">${c.num} урок</span>
        <span class="bell-time">${c.start} — ${c.end}</span>
      </div>
    `;
  });
  if (dom.bellsList) dom.bellsList.innerHTML = listHtml;
}

// --- Find Tab (/f & /w) Logic ---
let findSearchDebounce = null;
let currentFindMode = "f"; // "f" (кабинет) or "w" (группа)

const POPULAR_ROOMS = ["42", "25", "13", "32", "5", "26", "35", "43", "21", "1"];
const POPULAR_GROUPS = ["ИС 21-25", "ИС 31-24", "ИС 41-23", "Э 11-26", "Э 21-25", "ПК 31-24", "РПО 11-26", "СЛ 11-26"];

function updateFindQuickChips() {
  if (!dom.findQuickChips) return;
  dom.findQuickChips.innerHTML = "";

  if (currentFindMode === "f") {
    POPULAR_ROOMS.forEach(room => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = `Каб. ${room}`;
      chip.addEventListener("click", () => {
        haptic("selection");
        dom.findSearchInput.value = room;
        dom.findQuickChips.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
        executeFind();
      });
      dom.findQuickChips.appendChild(chip);
    });
  } else {
    POPULAR_GROUPS.forEach(grp => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.textContent = grp;
      chip.addEventListener("click", () => {
        haptic("selection");
        dom.findSearchInput.value = grp;
        dom.findQuickChips.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
        executeFind();
      });
      dom.findQuickChips.appendChild(chip);
    });
  }
}

function setFindMode(mode) {
  currentFindMode = mode;
  haptic("selection");

  if (dom.findModeRoomBtn) dom.findModeRoomBtn.classList.toggle("active", mode === "f");
  if (dom.findModeGroupBtn) dom.findModeGroupBtn.classList.toggle("active", mode === "w");

  if (mode === "f") {
    if (dom.findSearchInput) dom.findSearchInput.placeholder = "Номер кабинета (напр. 42, 25)...";
    if (dom.findDeptWrapper) dom.findDeptWrapper.style.display = "flex";
    if (dom.findEmptyHint) dom.findEmptyHint.textContent = "Введите номер кабинета для просмотра занятости пар (/f)";
  } else {
    if (dom.findSearchInput) dom.findSearchInput.placeholder = "Название группы (напр. ИС 21-25, 41-23)...";
    if (dom.findDeptWrapper) dom.findDeptWrapper.style.display = "none";
    if (dom.findEmptyHint) dom.findEmptyHint.textContent = "Введите название группы для просмотра её расписания (/w)";
  }

  updateFindQuickChips();
  if (dom.findSearchInput && dom.findSearchInput.value.trim()) {
    executeFind();
  } else {
    if (dom.findResultsList) {
      dom.findResultsList.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🔍</div>
          <p>${dom.findEmptyHint ? dom.findEmptyHint.textContent : ""}</p>
        </div>
      `;
    }
  }
}

async function executeFind() {
  const q = dom.findSearchInput ? dom.findSearchInput.value.trim() : "";
  const dept = dom.findSelectDept ? dom.findSelectDept.value : 3;
  const day = dom.findSelectDay ? dom.findSelectDay.value : 1;

  if (!q) {
    if (dom.findResultsList) {
      dom.findResultsList.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🔍</div>
          <p>${currentFindMode === "f" ? "Введите номер кабинета (/f)" : "Введите название группы (/w)"}</p>
        </div>
      `;
    }
    return;
  }

  dom.findResultsList.innerHTML = `
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Поиск...</p>
    </div>
  `;

  try {
    const url = `/api/find?mode=${currentFindMode}&q=${encodeURIComponent(q)}&department=${dept}&day=${day}`;
    const res = await apiFetch(url);
    const data = await res.json();

    if (!res.ok || data.error) {
      dom.findResultsList.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">⚠️</div>
          <p>${escapeHtml(data.error || "Ничего не найдено")}</p>
        </div>
      `;
      return;
    }

    if (currentFindMode === "f") {
      renderRoomFindResults(data, q);
    } else {
      renderGroupFindResults(data, q);
    }
  } catch (err) {
    console.error("Find error:", err);
    dom.findResultsList.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚠️</div>
        <p>Ошибка при выполнении поиска.</p>
      </div>
    `;
  }
}

function renderRoomFindResults(data, query) {
  const pairs = data.pairs || [];
  if (pairs.length === 0) {
    dom.findResultsList.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📖</div>
        <p>Для кабинета ${escapeHtml(query)} данных нет.</p>
      </div>
    `;
    return;
  }

  let html = `
    <div class="schedule-status-bar">
      <span>Кабинет <strong>${escapeHtml(query)}</strong> (отделение ${data.department})</span>
      <span class="badge badge-success">/f</span>
    </div>
  `;

  pairs.forEach(p => {
    if (p.occupied && p.lessons && p.lessons.length > 0) {
      p.lessons.forEach(item => {
        const grpsStr = item.groups && item.groups.length > 0 ? item.groups.join(", ") : "";
        html += `
          <div class="lesson-card pair-occupied-card">
            <div class="lesson-header">
              <span class="lesson-pair-num">${p.pair} ПАРА</span>
              <span class="badge pair-badge-occupied">Занят</span>
              <span class="lesson-time">${p.time}</span>
            </div>
            <div class="lesson-title">
              ${escapeHtml(item.subject)}
            </div>
            ${grpsStr ? `
              <div class="groups-pill-list">
                ${item.groups.map(g => `<span class="group-tag-pill">${escapeHtml(g)}</span>`).join("")}
              </div>
            ` : ""}
          </div>
        `;
      });
    } else {
      html += `
        <div class="lesson-card pair-free-card">
          <div class="lesson-header">
            <span class="lesson-pair-num">${p.pair} ПАРА</span>
            <span class="badge pair-badge-free">Свободен</span>
            <span class="lesson-time">${p.time}</span>
          </div>
          <div class="lesson-title" style="font-size: 13px; font-weight: 500; color: var(--hint-color);">
            Окно (пар нет)
          </div>
        </div>
      `;
    }
  });

  dom.findResultsList.innerHTML = html;
}

function renderGroupFindResults(data, query) {
  const rawLessons = data.lessons || [];
  const blocks = buildLessonBlocks(rawLessons);

  if (blocks.length === 0) {
    dom.findResultsList.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🎉</div>
        <p>У группы <strong>${escapeHtml(data.group_name || query)}</strong> занятий нет!</p>
      </div>
    `;
    return;
  }

  let html = `
    <div class="schedule-status-bar">
      <span>Группа <strong>${escapeHtml(data.group_name)}</strong> (отд. ${data.department})</span>
      <span class="badge badge-success">/w</span>
    </div>
  `;

  blocks.forEach(b => {
    html += `
      <div class="lesson-card ${b.is_override ? "is-override" : ""}">
        <div class="lesson-header">
          <span class="lesson-pair-num">${escapeHtml(b.lessonNumsStr)}</span>
          ${b.room ? `<span class="lesson-room">каб. ${escapeHtml(b.room)}</span>` : ""}
          <span class="lesson-time">${b.startTime} — ${b.endTime}</span>
        </div>
        <div class="lesson-title">
          ${escapeHtml(b.subject)}
        </div>
        ${b.is_override ? `
          <div class="lesson-override-note">
            ⚠️ Замена: ${escapeHtml(b.override_note || "Изменение в расписании")}
          </div>
        ` : ""}
      </div>
    `;
  });

  dom.findResultsList.innerHTML = html;
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

  // Find tab (/f & /w) event listeners
  if (dom.findModeRoomBtn) {
    dom.findModeRoomBtn.addEventListener("click", () => setFindMode("f"));
  }
  if (dom.findModeGroupBtn) {
    dom.findModeGroupBtn.addEventListener("click", () => setFindMode("w"));
  }

  if (dom.findSearchInput) {
    dom.findSearchInput.addEventListener("input", () => {
      clearTimeout(findSearchDebounce);
      findSearchDebounce = setTimeout(executeFind, 300);
    });
  }

  if (dom.findSelectDept) {
    dom.findSelectDept.addEventListener("change", executeFind);
  }
  if (dom.findSelectDay) {
    dom.findSelectDay.addEventListener("change", executeFind);
  }

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
  updateFindQuickChips();
  updateLiveBellsTimer();
  checkServerHealth();

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(err => {
      console.warn('ServiceWorker registration error:', err);
    });
  }

  setInterval(updateLiveBellsTimer, 15000);
});
