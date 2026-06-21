// ID Generator for local profile (compat with Telegram chat_id)
function generateUUID() {
  return Math.floor(Math.random() * 2147483647);
}

// PWA Install State
let deferredPrompt = null;

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  if (el.installBanner) el.installBanner.classList.remove('hidden');
});

// State management
let state = {
  user: {
    id: 0,
    name: 'Гость',
    role: 'student',
    department: 3,
    group_id: null,
    rooms: []
  },
  groups: {}, // { "gname": [dep, gid] }
  currentTab: 'tab-schedule',
  selectedDept: 3,
  selectedGroup: null,
  selectedDay: new Date().getDay() || 1, // 1-6
  teacherSelectedDay: new Date().getDay() || 1,
  selectedDate: '',
  scheduleCache: {}, // { 'dep-group': { day: lessons } }
  offlineQueue: [],
  online: navigator.onLine
};

// CONSTANTS
const CALL_TIMES = [
  ["08:20", "09:50"], // 1
  ["10:00", "11:30"], // 2
  ["11:35", "13:10"], // 3
  ["13:15", "14:45"], // 4
  ["14:50", "16:25"]  // 5 (10 slots total are grouped as double lessons)
];

const SLOT_TIMES = [
  ["08:20", "09:05"], ["09:05", "09:50"], // Para 1
  ["10:00", "10:45"], ["10:45", "11:30"], // Para 2
  ["11:35", "12:20"], ["12:25", "13:10"], // Para 3
  ["13:15", "14:00"], ["14:00", "14:45"], // Para 4
  ["14:50", "15:35"], ["15:40", "16:25"]  // Para 5
];

// Document Elements
const el = {
  loader: document.getElementById('loader'),
  userName: document.getElementById('user-name'),
  userRole: document.getElementById('user-role'),
  connStatus: document.getElementById('connection-status'),
  syncBanner: document.getElementById('sync-banner'),
  syncMessage: document.getElementById('sync-message'),
  btnSyncRetry: document.getElementById('btn-sync-retry'),
  
  // Setup View Elements
  viewSetup: document.getElementById('view-setup'),
  viewMain: document.getElementById('view-main'),
  setupForm: document.getElementById('setup-form'),
  setupRole: document.getElementById('setup-role'),
  setupName: document.getElementById('setup-name'),
  setupStudentFields: document.getElementById('setup-student-fields'),
  setupTeacherFields: document.getElementById('setup-teacher-fields'),
  setupDept: document.getElementById('setup-dept'),
  setupGroup: document.getElementById('setup-group'),
  setupTeacherDept: document.getElementById('setup-teacher-dept'),
  setupRooms: document.getElementById('setup-rooms'),
  setupPassword: document.getElementById('setup-password'),
  installBanner: document.getElementById('install-banner'),
  btnInstallPwa: document.getElementById('btn-install-pwa'),
  
  selectDept: document.getElementById('select-dept'),
  selectGroup: document.getElementById('select-group'),
  inputScheduleDate: document.getElementById('input-schedule-date'),
  scheduleTitle: document.getElementById('schedule-title'),
  btnSaveDefault: document.getElementById('btn-save-default'),
  scheduleList: document.getElementById('schedule-list'),
  
  navTeacherTab: document.getElementById('nav-teacher-tab'),
  teacherRoomsInfo: document.getElementById('teacher-rooms-info'),
  teacherScheduleList: document.getElementById('teacher-schedule-list'),
  
  // Override Modal
  overrideModal: document.getElementById('override-modal'),
  btnCloseModal: document.getElementById('btn-close-modal'),
  overrideForm: document.getElementById('override-form'),
  overrideLabelDetail: document.getElementById('override-label-detail'),
  overrideSlot: document.getElementById('override-slot'),
  overrideDay: document.getElementById('override-day'),
  overrideGroup: document.getElementById('override-group'),
  overrideSubject: document.getElementById('override-subject'),
  overrideRoom: document.getElementById('override-room'),
  btnDeleteOverride: document.getElementById('btn-delete-override'),
  btnCancelLesson: document.getElementById('btn-cancel-lesson'),
  btnUndoCancel: document.getElementById('btn-undo-cancel'),
  
  // Teacher UI additions
  inputTeacherDate: document.getElementById('input-teacher-date'),
  
  // Settings
  settingNotifications: document.getElementById('setting-notifications'),
  settingVoice: document.getElementById('setting-voice'),
  settingVoiceEffect: document.getElementById('setting-voice-effect'),
  settingFluffy: document.getElementById('setting-fluffy'),
  
  // Analytics
  statsType: document.getElementById('stats-type'),
  statsDept: document.getElementById('stats-dept'),
  statsGroupSelectors: document.getElementById('stats-group-selectors'),
  statsTeacherSelector: document.getElementById('stats-teacher-selector'),
  statsTarget: document.getElementById('stats-target'),
  statsTargetInput: document.getElementById('stats-target-input'),
  svgSubjects: document.getElementById('svg-subjects'),
  svgDaily: document.getElementById('svg-daily'),
  svgGroups: document.getElementById('svg-groups'),
  chartGroupsCard: document.getElementById('chart-groups-card'),
  
  // Moderator Control
  navModeratorTab: document.getElementById('nav-moderator-tab'),
  btnAdminFill: document.getElementById('btn-admin-fill'),
  btnAdminFlush: document.getElementById('btn-admin-flush'),
  adminOverridesList: document.getElementById('admin-overrides-list'),
  adminDateStart: document.getElementById('admin-date-start'),
  adminDateEnd: document.getElementById('admin-date-end'),
  btnAdminWeekCurrent: document.getElementById('btn-admin-week-current'),
  btnAdminWeekNext: document.getElementById('btn-admin-week-next'),
  adminDept: document.getElementById('admin-dept'),
  
  // Settings profile fields
  settingsUserName: document.getElementById('settings-user-name'),
  settingsUserRole: document.getElementById('settings-user-role'),
  settingsDeptRow: document.getElementById('settings-dept-row'),
  settingsUserDept: document.getElementById('settings-user-dept'),
  settingsGroupRow: document.getElementById('settings-group-row'),
  settingsDefaultGroup: document.getElementById('settings-default-group'),
  
  // Navigation
  navButtons: document.querySelectorAll('.nav-item'),
  views: document.querySelectorAll('.tab-view')
};

// =================== INIT & AUTHENTICATION ===================
async function initApp() {
  // PWA Standalone Enforcement
  const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;
  const urlParams = new URLSearchParams(window.location.search);
  const isBypass = urlParams.get('dev') === '1';

  if (!isStandalone && !isBypass) {
    document.getElementById('loader').classList.add('hidden');
    document.getElementById('pwa-blocker').classList.remove('hidden');
    
    // Listen for beforeinstallprompt
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      deferredPrompt = e;
      const btn = document.getElementById('btn-pwa-blocker-install');
      btn.classList.remove('hidden');
      document.getElementById('pwa-blocker-hint').classList.add('hidden');
      
      btn.addEventListener('click', async () => {
        if (deferredPrompt) {
          deferredPrompt.prompt();
          const { outcome } = await deferredPrompt.userChoice;
          if (outcome === 'accepted') {
            console.log('User accepted the install prompt');
          }
          deferredPrompt = null;
          btn.classList.add('hidden');
        }
      });
    });
    
    return; // STOP EXECUTION!
  }

  setupEventListeners();
  loadLocalCache();
  
  // Start background auth polling
  if (state.user && state.user.id) {
    checkAuthStatus();
    setInterval(checkAuthStatus, 10000);
  }

  // Check Profile
  const cachedProfile = localStorage.getItem('kalich_profile');
  if (cachedProfile) {
    state.user = JSON.parse(cachedProfile);
    
    // Legacy profile cleanup (if they have old dev ID or missing ID)
    if (state.user.id === 1234567 || state.user.id === 0 || !state.user.id || typeof state.user.id === 'string') {
      console.log("Found legacy profile, resetting...");
      localStorage.removeItem('kalich_profile');
      state.user = { id: 0, name: 'Гость', role: 'student', department: 3, group_id: null, rooms: [] };
      
      el.viewMain.classList.add('hidden');
      el.viewSetup.classList.remove('hidden');
      await loadGroups();
      populateSetupGroups();
      document.body.classList.remove('loading');
      document.body.classList.add('ready');
      return;
    }

    el.viewSetup.classList.add('hidden');
    el.viewMain.classList.remove('hidden');
    
    // Auto-select tab based on role
    if (state.user.role === 'teacher') {
      state.currentTab = 'tab-teacher';
    } else if (state.user.role === 'moderator') {
      state.currentTab = 'tab-moderator';
    }
    
    // Fetch groups
    await loadGroups();
    
    startMainApp();
  } else {
    // Show Setup Flow
    el.viewMain.classList.add('hidden');
    el.viewSetup.classList.remove('hidden');
    
    // Fetch groups for setup dropdown
    await loadGroups();
    populateSetupGroups();
    
    // Hide loader
    document.body.classList.remove('loading');
    document.body.classList.add('ready');
  }
}

async function checkAuthStatus() {
  if (!state.user || !state.user.id) return;
  try {
    const authResponse = await fetchAPI('/api/auth', {
      method: 'POST',
      body: JSON.stringify({ device_id: state.user.id })
    });
    
    if (authResponse && !authResponse.error && authResponse.user) {
      let changed = false;
      if (authResponse.user.role === 'teacher' && state.user.role !== 'teacher') {
        state.user.role = 'teacher';
        state.user.department = authResponse.user.department;
        state.user.rooms = authResponse.user.rooms;
        changed = true;
        alert("Ваша заявка на преподавателя была одобрена!");
      } else if (authResponse.user.role === 'moderator' && state.user.role !== 'moderator') {
        state.user.role = 'moderator';
        changed = true;
        alert("Вам выданы права модератора!");
      }

      if (changed) {
        localStorage.setItem('kalich_profile', JSON.stringify(state.user));
        // Force UI update
        startMainApp();
      }
    }
  } catch (e) {
    console.warn("Auth check failed", e);
  }
}

function populateSetupGroups() {
  const dep = parseInt(el.setupDept.value);
  el.setupGroup.innerHTML = '<option value="">Выберите группу...</option>';
  
  const filtered = [];
  for (const [name, info] of Object.entries(state.groups)) {
    if (info[0] === dep) filtered.push({ name, gid: info[1] });
  }
  filtered.sort((a, b) => a.name.localeCompare(b.name));
  
  filtered.forEach(g => {
    const opt = document.createElement('option');
    opt.value = g.gid;
    opt.textContent = g.name;
    el.setupGroup.appendChild(opt);
  });
}

// =================== MAIN APP START ===================

// Settings UI and Application logic
function applySettings() {
  const s = state.user.settings || {};
  
  // 1. Populate UI if elements exist
  if (el.settingNotifications) el.settingNotifications.checked = !!s.notifications;
  if (el.settingVoice) el.settingVoice.checked = !!s.voice_alerts;
  if (el.settingVoiceEffect) el.settingVoiceEffect.value = s.voice_effect || 'normal';
  if (el.settingFluffy) el.settingFluffy.checked = !!s.fluffy_mode;

  // 2. Apply theme (Fluffy Mode)
  if (s.fluffy_mode) {
    document.body.classList.add('fluffy-mode');
  } else {
    document.body.classList.remove('fluffy-mode');
  }

  // 3. Toggle voice button visibility
  const voiceBtn = document.getElementById('btn-read-schedule');
  if (voiceBtn) {
    if (s.voice_alerts) voiceBtn.classList.remove('hidden');
    else voiceBtn.classList.add('hidden');
  }

  // 4. Request Notification permissions if turned on
  if (s.notifications && 'Notification' in window) {
    if (Notification.permission !== 'granted' && Notification.permission !== 'denied') {
      Notification.requestPermission();
    }
  }
}

async function startMainApp() {
  // Update profile views
  updateProfileUI();
  applySettings();

  // Load default group if saved
  const savedGroup = localStorage.getItem('kalich_default_group');
  if (savedGroup) {
    const [dep, gid] = JSON.parse(savedGroup);
    state.selectedDept = dep;
    state.selectedGroup = gid;
    el.selectDept.value = dep;
  }

  // Initial populate groups
  populateGroupsDropdown();
  if (state.selectedGroup) {
    el.selectGroup.value = state.selectedGroup;
    loadSchedule();
  }

  // Set active day in schedule controls
  document.querySelector(`.day-btn[data-day="${state.selectedDay}"]`)?.classList.add('active');
  document.querySelector(`.t-day-btn[data-day="${state.teacherSelectedDay}"]`)?.classList.add('active');

  // Hide loader
  document.body.classList.remove('loading');
  document.body.classList.add('ready');

  // Trigger initial PWA sync if anything queued
  processOfflineQueue();
  
  // Initialize analytics tab objects
  setupAnalyticsDropdown();

  // Switch to initial tab visually
  const activeBtn = document.querySelector(`.nav-item[data-tab="${state.currentTab}"]`);
  if (activeBtn) {
    activeBtn.click();
  }
}

function loadLocalCache() {
  const cachedProfile = localStorage.getItem('kalich_profile');
  if (cachedProfile) {
    state.user = JSON.parse(cachedProfile);
  }
  
  const cachedGroups = localStorage.getItem('kalich_groups');
  if (cachedGroups) {
    state.groups = JSON.parse(cachedGroups);
  }

  const queue = localStorage.getItem('kalich_offline_queue');
  if (queue) {
    state.offlineQueue = JSON.parse(queue);
    updateSyncBanner();
  }
}

function updateProfileUI() {
  const name = state.user.name || 'Студент';
  el.userName.textContent = name;
  
  // Fill settings profile fields
  if (el.settingsUserName) {
    el.settingsUserName.textContent = name;
  }
  
  let roleText = 'Студент';
  if (state.user.role === 'teacher') {
    roleText = 'Преподаватель';
    el.userRole.textContent = 'Преподаватель';
    el.userRole.className = 'role-badge success';
    el.navTeacherTab.classList.remove('hidden');
    el.teacherRoomsInfo.textContent = `Кабинеты: ${state.user.rooms.join(', ')} (Отд. ${state.user.department})`;
    populateTeacherGroupsDropdown();
    loadTeacherSchedule();
    
    if (el.settingsDeptRow) {
      el.settingsDeptRow.classList.remove('hidden');
      el.settingsUserDept.textContent = `Отделение ${state.user.department}`;
    }
    if (el.settingsGroupRow) {
      el.settingsGroupRow.classList.add('hidden');
    }
  } else if (state.user.role === 'moderator') {
    roleText = 'Модератор';
    el.userRole.textContent = 'Модератор';
    el.userRole.className = 'role-badge danger';
    el.navTeacherTab.classList.remove('hidden');
    el.navModeratorTab.classList.remove('hidden');
    el.teacherRoomsInfo.textContent = `Доступ ко всем группам и кабинетам`;
    populateTeacherGroupsDropdown();
    loadTeacherSchedule();
    loadAdminOverrides();
    
    if (el.settingsDeptRow) {
      el.settingsDeptRow.classList.add('hidden');
    }
    if (el.settingsGroupRow) {
      el.settingsGroupRow.classList.add('hidden');
    }
  } else {
    roleText = 'Студент';
    el.userRole.textContent = 'Студент';
    el.userRole.className = 'role-badge';
    el.navTeacherTab.classList.add('hidden');
    el.navModeratorTab.classList.add('hidden');
    
    if (el.settingsDeptRow) {
      el.settingsDeptRow.classList.add('hidden');
    }
    
    // Default group for student
    const savedGroup = localStorage.getItem('kalich_default_group');
    if (savedGroup && el.settingsGroupRow) {
      el.settingsGroupRow.classList.remove('hidden');
      try {
        const [dep, gid] = JSON.parse(savedGroup);
        // Find group name
        let grpName = 'Неизвестная';
        for (const [name, info] of Object.entries(state.groups)) {
          if (info[0] === dep && info[1] === gid) {
            grpName = name;
            break;
          }
        }
        el.settingsDefaultGroup.textContent = `${grpName} (Отд. ${dep})`;
      } catch(e) {
        el.settingsDefaultGroup.textContent = 'Ошибка чтения';
      }
    } else if (el.settingsGroupRow) {
      el.settingsGroupRow.classList.remove('hidden');
      el.settingsDefaultGroup.textContent = 'Не выбрана';
    }
  }
  
  if (el.settingsUserRole) {
    el.settingsUserRole.textContent = roleText;
  }

  // Load Settings
  if (state.user.settings) {
    el.settingNotifications.checked = !!state.user.settings.notifications;
    el.settingVoice.checked = !!state.user.settings.voice_alerts;
    el.settingVoiceEffect.value = state.user.settings.voice_effect || 'echo';
    el.settingFluffy.checked = !!state.user.settings.fluffy_mode;
  }
}

// =================== GROUPS & SCHEDULE ===================
async function loadGroups() {
  try {
    const data = await fetchAPI('/api/groups');
    if (data && data.groups) {
      state.groups = data.groups;
      localStorage.setItem('kalich_groups', JSON.stringify(data.groups));
    }
  } catch (e) {
    console.error("Failed to load groups list", e);
  }
}

function populateGroupsDropdown() {
  const dep = parseInt(el.selectDept.value);
  state.selectedDept = dep;
  
  el.selectGroup.innerHTML = '<option value="">Выберите группу...</option>';
  
  // Sort and filter groups by department
  const filtered = [];
  for (const [name, info] of Object.entries(state.groups)) {
    if (info[0] === dep) {
      filtered.push({ name, gid: info[1] });
    }
  }
  filtered.sort((a, b) => a.name.localeCompare(b.name));
  
  filtered.forEach(g => {
    const opt = document.createElement('option');
    opt.value = g.gid;
    opt.textContent = g.name;
    el.selectGroup.appendChild(opt);
  });
}

async function loadSchedule() {
  const dep = state.selectedDept;
  const gid = state.selectedGroup;
  const day = state.selectedDay;
  const date = state.selectedDate;
  
  if (!gid) {
    el.scheduleList.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">📅</span>
        <p>Выберите группу в меню сверху, чтобы посмотреть её расписание</p>
      </div>`;
    return;
  }

  // Update schedule title text
  if (date) {
    const [y, m, d] = date.split('-');
    el.scheduleTitle.textContent = `Расписание на ${d}.${m}.${y}`;
  } else {
    const dayLabels = { 1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб", "all": "Вся неделя" };
    const groupName = gid === 'all' ? "Все группы" : `Группа ${gid}`;
    el.scheduleTitle.textContent = `Расписание: ${groupName} (${dayLabels[day] || ""})`;
  }

  // Hide save default button for non-students
  if (state.user && (state.user.role === 'teacher' || state.user.role === 'moderator')) {
    el.btnSaveDefault.classList.add('hidden');
  } else {
    el.btnSaveDefault.classList.remove('hidden');
    // Update save default UI
    const savedGroup = localStorage.getItem('kalich_default_group');
    if (savedGroup) {
      const [savedDep, savedGid] = JSON.parse(savedGroup);
      if (savedDep === dep && savedGid === parseInt(gid)) {
        el.btnSaveDefault.textContent = '★';
        el.btnSaveDefault.classList.add('active');
      } else {
        el.btnSaveDefault.textContent = '☆';
        el.btnSaveDefault.classList.remove('active');
      }
    } else {
      el.btnSaveDefault.textContent = '☆';
      el.btnSaveDefault.classList.remove('active');
    }
  }

  // Render skeleton loading
  el.scheduleList.innerHTML = `
    <div class="empty-state">
      <div class="loader-spinner" style="width:30px;height:30px;border-width:3px;"></div>
      <p>Загрузка пар...</p>
    </div>`;

  try {
    const url = date
      ? `/api/schedule?department=${dep}&group_id=${gid}&date=${date}`
      : `/api/schedule?department=${dep}&group_id=${gid}&day=${day}`;
    const data = await fetchAPI(url);
    if (data.department_schedules) {
      renderDepartmentSchedule(data.department_schedules);
    } else if (data.week_schedules) {
      renderWeekSchedule(data.week_schedules);
    } else {
      renderSchedule(data || []);
    }
  } catch (e) {
    el.scheduleList.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">⚠️</span>
        <p>Не удалось загрузить расписание</p>
      </div>`;
  }
}

function renderSchedule(lessons) {
  if (!lessons || lessons.length === 0) {
    el.scheduleList.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">🏖️</span>
        <p>Занятий нет. Выходной!</p>
      </div>`;
    return;
  }

  el.scheduleList.innerHTML = '';
  
  // Format pairs (usually list of 8 or 10 slots)
  // We group them into pairs (two slots per double-lesson)
  const totalDoubleLessons = Math.ceil(lessons.length / 2);
  
  for (let i = 0; i < totalDoubleLessons; i++) {
    const s1 = lessons[i * 2] || "—";
    const s2 = lessons[i * 2 + 1] || "—";
    
    // Skip empty pairs entirely if both slots are empty
    const isEmpty = (s1 === "—" || s1 === "." || s1 === "x") && (s2 === "—" || s2 === "." || s2 === "x");
    if (isEmpty) continue;
    
    // Check timing
    const time = CALL_TIMES[i] || ["??:??", "??:??"];
    const subject = s1 === s2 ? s1 : `${s1} / ${s2}`;
    
    // Clean up room if present in parens
    let room = "";
    const roomMatch = subject.match(/\(([^)]+)\)/);
    if (roomMatch) {
      room = roomMatch[1];
    }
    const cleanSubject = subject.replace(/\s*\([^)]+\)/g, '').trim();
    
    const card = document.createElement('div');
    card.className = 'lesson-card';
    
    // Detect overrides
    let overrideBadge = '';
    // If it contains brackets and represents an edited class
    if (subject.toLowerCase().includes('замена') || subject.includes('(изм)')) {
      overrideBadge = `<span class="badge-override">Замена</span>`;
    }

    card.innerHTML = `
      <div class="lesson-time">
        <span class="lesson-num">Пара ${i + 1}</span>
        <span class="time-start">${time[0]}</span>
        <span class="time-end">${time[1]}</span>
      </div>
      <div class="lesson-details">
        <div class="lesson-subject">${cleanSubject}</div>
        <div class="lesson-room-group">
          ${room ? `<span>🚪 Кабинет: <strong>${room}</strong></span>` : ''}
        </div>
        ${overrideBadge}
      </div>
    `;
    
    el.scheduleList.appendChild(card);
  }

  if (el.scheduleList.children.length === 0) {
    el.scheduleList.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">🏖️</span>
        <p>Занятий нет. Выходной!</p>
      </div>`;
  }
}

// =================== TEACHER SPECIFIC LOGIC ===================
async function loadTeacherSchedule() {
  const dateStr = state.teacherSelectedDate || state.currentDate;
  
  el.teacherScheduleList.innerHTML = `
    <div class="empty-state">
      <div class="loader-spinner" style="width:30px;height:30px;border-width:3px;"></div>
      <p>Загрузка...</p>
    </div>`;

  try {
    const data = await fetchAPI(`/api/teacher/schedule?chat_id=${state.user.id}&date=${dateStr}`);
    if (data.error) throw new Error(data.error);
    renderTeacherSchedule(data);
  } catch (e) {
    el.teacherScheduleList.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">⚠️</span>
        <p>Не удалось загрузить расписание</p>
      </div>`;
  }
}

function renderTeacherSchedule(schedule) {
  if (!schedule || schedule.length === 0) {
    el.teacherScheduleList.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">🎉</span>
        <p>У вас нет пар в ваших кабинетах на этот день</p>
      </div>`;
    return;
  }

  el.teacherScheduleList.innerHTML = '';
  
  schedule.forEach((slots, idx) => {
    const time = SLOT_TIMES[idx] || ["??:??", "??:??"];
    const card = document.createElement('div');
    card.className = 'lesson-card';
    card.style.cursor = 'pointer';
    card.style.position = 'relative'; // Added for absolute positioning of pencil
    
    // Check if it is an empty slot
    const isEmpty = slots.length === 0;

    // On click, open substitution form
    card.addEventListener('click', () => {
      openOverrideModal(idx, time, slots);
    });

    if (isEmpty) {
      card.innerHTML = `
        <div class="lesson-time">
          <span class="lesson-num">Урок ${idx + 1}</span>
          <span class="time-start">${time[0]}</span>
          <span class="time-end">${time[1]}</span>
        </div>
        <div class="lesson-details">
          <div class="lesson-subject" style="color:var(--text-secondary);font-style:italic;">Свободный слот</div>
          <div class="lesson-room-group">Нажмите для назначения замены</div>
        </div>
        <div style="position: absolute; right: 10px; top: 10px; opacity: 0.3;">✏️</div>
      `;
    } else {
      // Check if it is a lunch slot (single slot with ОБЕД)
      const isLunch = slots.length === 1 && slots[0][1] === "ОБЕД";
      
      if (isLunch) {
        card.innerHTML = `
          <div class="lesson-time">
            <span class="lesson-num">Урок ${idx + 1}</span>
            <span class="time-start">${time[0]}</span>
            <span class="time-end">${time[1]}</span>
          </div>
          <div class="lesson-details">
            <div class="lesson-subject" style="color:var(--text-secondary);">Обед 🍕</div>
            <div class="lesson-room-group" style="font-size:11px;color:var(--text-secondary);">Перерыв между занятиями</div>
          </div>
        `;
      } else {
        // Group info
        const details = slots.map(s => {
          if (s[0]) {
            const grpInfo = state.groups[s[0]];
            const deptText = grpInfo ? `, Отд. ${grpInfo[0]}` : '';
            return `${s[1]} (${s[0]}${deptText})`;
          }
          return s[1];
        }).join(', ');
        const rooms = [...new Set(slots.map(s => s[2]).filter(r => r))].join(', ');
        
        card.innerHTML = `
          <div class="lesson-time">
            <span class="lesson-num">Урок ${idx + 1}</span>
            <span class="time-start">${time[0]}</span>
            <span class="time-end">${time[1]}</span>
          </div>
          <div class="lesson-details">
            <div class="lesson-subject">${details}</div>
            ${rooms ? `<div class="lesson-room-group">🚪 Кабинет: ${rooms}</div>` : ''}
          </div>
          <div style="position: absolute; right: 10px; top: 10px; opacity: 0.3;">✏️</div>
        `;
      }
    }

    el.teacherScheduleList.appendChild(card);
  });
}

function populateTeacherGroupsDropdown() {
  el.overrideGroup.innerHTML = '<option value="-1">Для всех групп (Общее)</option>';
  
  // Group options by department: 1, 2, 3
  const groupsByDept = { 1: [], 2: [], 3: [] };
  for (const [name, info] of Object.entries(state.groups)) {
    const dep = info[0];
    const gid = info[1];
    if (state.user.role === 'moderator' || dep === state.user.department) {
      if (groupsByDept[dep]) {
        groupsByDept[dep].push({ name, gid, value: `${dep}-${gid}` });
      }
    }
  }
  
  for (const dep of [1, 2, 3]) {
    if (groupsByDept[dep].length === 0) continue;
    groupsByDept[dep].sort((a, b) => a.name.localeCompare(b.name));
    
    const optgroup = document.createElement('optgroup');
    optgroup.label = `Отделение ${dep}`;
    
    groupsByDept[dep].forEach(g => {
      const opt = document.createElement('option');
      opt.value = g.value;
      opt.textContent = g.name;
      optgroup.appendChild(opt);
    });
    el.overrideGroup.appendChild(optgroup);
  }
}

function openOverrideModal(slotIdx, slots) {
  el.overrideSlot.value = slotIdx;
  el.overrideDay.value = state.teacherSelectedDay;
  el.overrideLabelDetail.textContent = `Урок ${slotIdx + 1} (${SLOT_TIMES[slotIdx]?.[0] || ""} - ${SLOT_TIMES[slotIdx]?.[1] || ""})`;
  
  // Reset values
  el.overrideSubject.value = '';
  el.overrideRoom.value = '';
  el.overrideGroup.value = '-1';
  
  // If there's an existing class, fill defaults
  if (slots && slots.length > 0 && slots[0][1] !== "ОБЕД") {
    el.overrideSubject.value = slots[0][1];
    el.overrideRoom.value = slots[0][2];
    
    // Find matching group ID
    const grpName = slots[0][0];
    if (state.groups[grpName]) {
      const [dep, gid] = state.groups[grpName];
      el.overrideGroup.value = `${dep}-${gid}`;
    }
  }

  // Toggle Cancel/Undo Cancel buttons based on current state
  if (el.btnCancelLesson && el.btnUndoCancel) {
    if (el.overrideSubject.value.trim().toLowerCase() === 'отменено') {
      el.btnCancelLesson.classList.add('hidden');
      el.btnUndoCancel.classList.remove('hidden');
    } else {
      el.btnCancelLesson.classList.remove('hidden');
      el.btnUndoCancel.classList.add('hidden');
    }
  }

  el.overrideModal.classList.remove('hidden');
}

// =================== OFFLINE SYNC ENGINE ===================
function updateOnlineStatus() {
  state.online = navigator.onLine;
  if (state.online) {
    el.connStatus.textContent = 'Онлайн';
    el.connStatus.className = 'status-indicator online';
    processOfflineQueue();
  } else {
    el.connStatus.textContent = 'Оффлайн';
    el.connStatus.className = 'status-indicator offline';
  }
}

function updateSyncBanner() {
  if (state.offlineQueue.length > 0) {
    el.syncMessage.textContent = `Неотправленных замен: ${state.offlineQueue.length}. Сохранено оффлайн.`;
    el.syncBanner.classList.remove('hidden');
  } else {
    el.syncBanner.classList.add('hidden');
  }
}

function queueOverride(override) {
  state.offlineQueue.push(override);
  localStorage.setItem('kalich_offline_queue', JSON.stringify(state.offlineQueue));
  updateSyncBanner();
  
  // Inform user
  alert('Оффлайн-режим: Замена сохранена на устройстве. Мы синхронизируем ее сразу после восстановления сети.');
}

async function processOfflineQueue() {
  if (!navigator.onLine || state.offlineQueue.length === 0) return;

  el.btnSyncRetry.textContent = 'Синхронизация...';
  el.btnSyncRetry.disabled = true;

  try {
    const result = await fetchAPI('/api/sync', {
      method: 'POST',
      body: JSON.stringify({
        device_id: state.user.id,
        overrides: state.offlineQueue
      })
    });

    if (result && !result.error) {
      state.offlineQueue = [];
      localStorage.removeItem('kalich_offline_queue');
      updateSyncBanner();
      
      // Reload teacher schedule
      loadTeacherSchedule();
      
      alert('Все оффлайн-изменения успешно синхронизированы!');
    }
  } catch (e) {
    console.error("Sync failed", e);
  } finally {
    el.btnSyncRetry.textContent = 'Синхронизировать';
    el.btnSyncRetry.disabled = false;
  }
}

// =================== ANALYTICS INTERACTIVE CHARTS ===================
function setupAnalyticsDropdown() {
  // Populate initially
  updateAnalyticsTargetDropdown();
  
  el.statsType.addEventListener('change', () => {
    updateAnalyticsTargetDropdown();
    renderAnalyticsCharts();
  });
  
  el.statsDept.addEventListener('change', () => {
    updateAnalyticsTargetDropdown();
    renderAnalyticsCharts();
  });
  
  el.statsTarget.addEventListener('change', renderAnalyticsCharts);
  el.statsTargetInput.addEventListener('input', renderAnalyticsCharts);
}

function updateAnalyticsTargetDropdown() {
  const type = el.statsType.value;
  el.statsTarget.innerHTML = '';
  
  if (type === 'group') {
    el.statsGroupSelectors.classList.remove('hidden');
    el.statsTeacherSelector.classList.add('hidden');
    
    const targetDept = parseInt(el.statsDept.value) || 3;
    
    // Filter groups by department
    const groups = [];
    for (const [name, info] of Object.entries(state.groups)) {
      if (info[0] === targetDept) {
        groups.push({ name, gid: info[1], value: `${targetDept}-${info[1]}` });
      }
    }
    
    groups.sort((a, b) => a.name.localeCompare(b.name));
    
    groups.forEach(g => {
      const opt = document.createElement('option');
      opt.value = g.value;
      opt.textContent = g.name;
      el.statsTarget.appendChild(opt);
    });
    
    if (state.selectedGroup && targetDept === state.selectedDept) {
      el.statsTarget.value = `${state.selectedDept}-${state.selectedGroup}`;
    }
  } else {
    el.statsGroupSelectors.classList.add('hidden');
    el.statsTeacherSelector.classList.remove('hidden');
  }
}

async function renderAnalyticsCharts() {
  const type = el.statsType.value;
  const target = type === 'group' ? el.statsTarget.value : el.statsTargetInput.value.trim();
  if (!target) return;

  let url = `/api/analytics?type=${type}&target=${encodeURIComponent(target)}`;
  try {
    const data = await fetchAPI(url);
    if (data && !data.error) {
      drawSubjectsChart(data.subjects || {});
      drawDailyLoadChart(data.daily || {});
      
      // Manage 3rd chart (groups)
      if (type !== 'group' && data.groups) {
        el.chartGroupsCard.classList.remove('hidden');
        drawGroupsChart(data.groups);
      } else {
        el.chartGroupsCard.classList.add('hidden');
      }
    }
  } catch (e) {
    console.error("Failed to load analytics", e);
  }
}

function drawSubjectsChart(subjects) {
  const svg = el.svgSubjects;
  svg.innerHTML = ''; // clear

  const entries = Object.entries(subjects).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) {
    const txt = document.createElementNS("http://www.w3.org/2000/svg", "text");
    txt.setAttribute("x", "200");
    txt.setAttribute("y", "150");
    txt.setAttribute("text-anchor", "middle");
    txt.setAttribute("fill", "#a6adc8");
    txt.textContent = "Нет данных для отображения";
    svg.appendChild(txt);
    return;
  }

  const colors = ['#89b4fa', '#b4befe', '#cba6f7', '#f5c2e7', '#a6e3a1', '#f9e2af', '#fab387', '#f38ba8'];
  const maxVal = Math.max(...entries.map(e => e[1])) || 1;
  const chartHeight = entries.length * 40 + 40;
  
  svg.setAttribute("viewBox", `0 0 400 ${chartHeight}`);
  
  entries.forEach(([subj, hours], idx) => {
    const y = idx * 40 + 20;
    const barWidth = (hours / maxVal) * 200;
    const color = colors[idx % colors.length];

    // Subject Label
    const textLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
    textLabel.setAttribute("x", "10");
    textLabel.setAttribute("y", y + 15);
    textLabel.setAttribute("fill", "#cdd6f4");
    textLabel.setAttribute("font-size", "11px");
    textLabel.setAttribute("font-weight", "bold");
    // Truncate if long
    textLabel.textContent = subj.length > 18 ? subj.slice(0, 16) + '..' : subj;
    
    // Bar
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", "140");
    rect.setAttribute("y", y);
    rect.setAttribute("width", barWidth);
    rect.setAttribute("height", "20");
    rect.setAttribute("rx", "6");
    rect.setAttribute("fill", color);
    // Animation
    const anim = document.createElementNS("http://www.w3.org/2000/svg", "animate");
    anim.setAttribute("attributeName", "width");
    anim.setAttribute("from", "0");
    anim.setAttribute("to", barWidth);
    anim.setAttribute("dur", "0.6s");
    anim.setAttribute("fill", "freeze");
    rect.appendChild(anim);

    // Value Text
    const textVal = document.createElementNS("http://www.w3.org/2000/svg", "text");
    textVal.setAttribute("x", 145 + barWidth);
    textVal.setAttribute("y", y + 15);
    textVal.setAttribute("fill", "#a6adc8");
    textVal.setAttribute("font-size", "11px");
    textVal.textContent = `${hours}ч`;

    svg.appendChild(textLabel);
    svg.appendChild(rect);
    svg.appendChild(textVal);
  });
}

function drawGroupsChart(groups) {
  const svg = el.svgGroups;
  svg.innerHTML = ''; // clear

  const entries = Object.entries(groups).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) {
    const txt = document.createElementNS("http://www.w3.org/2000/svg", "text");
    txt.setAttribute("x", "200");
    txt.setAttribute("y", "150");
    txt.setAttribute("text-anchor", "middle");
    txt.setAttribute("fill", "#a6adc8");
    txt.textContent = "Нет данных для отображения";
    svg.appendChild(txt);
    return;
  }

  const colors = ['#a6e3a1', '#94e2d5', '#89b4fa', '#b4befe', '#cba6f7', '#f5c2e7', '#f9e2af', '#fab387'];
  const maxVal = Math.max(...entries.map(e => e[1])) || 1;
  const chartHeight = entries.length * 40 + 40;
  
  svg.setAttribute("viewBox", `0 0 400 ${chartHeight}`);
  
  entries.forEach(([gname, hours], idx) => {
    const y = idx * 40 + 20;
    const barWidth = (hours / maxVal) * 180;
    const color = colors[idx % colors.length];

    // Group Label
    const textLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
    textLabel.setAttribute("x", "10");
    textLabel.setAttribute("y", y + 15);
    textLabel.setAttribute("fill", "#cdd6f4");
    textLabel.setAttribute("font-size", "10px");
    textLabel.setAttribute("font-weight", "bold");
    textLabel.textContent = gname.length > 22 ? gname.slice(0, 20) + '..' : gname;
    
    // Bar
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", "160");
    rect.setAttribute("y", y);
    rect.setAttribute("width", barWidth);
    rect.setAttribute("height", "20");
    rect.setAttribute("rx", "6");
    rect.setAttribute("fill", color);
    // Animation
    const anim = document.createElementNS("http://www.w3.org/2000/svg", "animate");
    anim.setAttribute("attributeName", "width");
    anim.setAttribute("from", "0");
    anim.setAttribute("to", barWidth);
    anim.setAttribute("dur", "0.6s");
    anim.setAttribute("fill", "freeze");
    rect.appendChild(anim);

    // Value Text
    const textVal = document.createElementNS("http://www.w3.org/2000/svg", "text");
    textVal.setAttribute("x", 165 + barWidth);
    textVal.setAttribute("y", y + 15);
    textVal.setAttribute("fill", "#a6adc8");
    textVal.setAttribute("font-size", "11px");
    textVal.textContent = `${hours}ч`;

    svg.appendChild(textLabel);
    svg.appendChild(rect);
    svg.appendChild(textVal);
  });
}

function drawDailyLoadChart(daily) {
  const svg = el.svgDaily;
  svg.innerHTML = '';

  const days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];
  const values = days.map((d, i) => daily[i + 1] || 0); // day keys 1-6
  const maxVal = Math.max(...values) || 1;

  const width = 400;
  const height = 250;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  // Draw Grid lines
  for (let i = 0; i <= 4; i++) {
    const y = 30 + i * 40;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", "30");
    line.setAttribute("y1", y);
    line.setAttribute("x2", "370");
    line.setAttribute("y2", y);
    line.setAttribute("stroke", "#313244");
    line.setAttribute("stroke-dasharray", "4");
    svg.appendChild(line);
  }

  const colWidth = 40;
  const spacing = 15;
  const startX = 55;

  days.forEach((day, idx) => {
    const val = values[idx];
    const barHeight = (val / maxVal) * 140;
    const x = startX + idx * (colWidth + spacing);
    const y = 190 - barHeight;

    // Bar
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", x);
    rect.setAttribute("y", y);
    rect.setAttribute("width", colWidth);
    rect.setAttribute("height", barHeight);
    rect.setAttribute("rx", "6");
    rect.setAttribute("fill", "#94e2d5");
    
    // Animation
    const anim = document.createElementNS("http://www.w3.org/2000/svg", "animate");
    anim.setAttribute("attributeName", "height");
    anim.setAttribute("from", "0");
    anim.setAttribute("to", barHeight);
    anim.setAttribute("dur", "0.6s");
    anim.setAttribute("fill", "freeze");
    rect.appendChild(anim);
    
    const animY = document.createElementNS("http://www.w3.org/2000/svg", "animate");
    animY.setAttribute("attributeName", "y");
    animY.setAttribute("from", "190");
    animY.setAttribute("to", y);
    animY.setAttribute("dur", "0.6s");
    animY.setAttribute("fill", "freeze");
    rect.appendChild(animY);
    
    rect.appendChild(anim);
    rect.appendChild(animY);

    // Value Label
    const textVal = document.createElementNS("http://www.w3.org/2000/svg", "text");
    textVal.setAttribute("x", x + colWidth / 2);
    textVal.setAttribute("y", y - 8);
    textVal.setAttribute("text-anchor", "middle");
    textVal.setAttribute("fill", "#cdd6f4");
    textVal.setAttribute("font-size", "11px");
    textVal.setAttribute("font-weight", "bold");
    textVal.textContent = val > 0 ? `${val}ч` : '0';

    // Day Label
    const textDay = document.createElementNS("http://www.w3.org/2000/svg", "text");
    textDay.setAttribute("x", x + colWidth / 2);
    textDay.setAttribute("y", "215");
    textDay.setAttribute("text-anchor", "middle");
    textDay.setAttribute("fill", "#bac2de");
    textDay.setAttribute("font-size", "12px");
    textDay.setAttribute("font-weight", "500");
    textDay.textContent = day;

    svg.appendChild(rect);
    svg.appendChild(textVal);
    svg.appendChild(textDay);
  });
}

// =================== EVENT LISTENERS ===================
function setupEventListeners() {
  // Toggles for schedule view filters
  const btnToggleDate = document.getElementById('btn-toggle-date');
  const btnToggleGroup = document.getElementById('btn-toggle-group');
  const filterDateSec = document.getElementById('filter-date-section');
  const filterGroupSec = document.getElementById('filter-group-section');

  if (btnToggleDate) {
    btnToggleDate.addEventListener('click', () => {
      filterDateSec.classList.toggle('hidden');
      if (!filterDateSec.classList.contains('hidden')) {
        filterGroupSec.classList.add('hidden');
      }
    });
  }

  if (btnToggleGroup) {
    btnToggleGroup.addEventListener('click', () => {
      filterGroupSec.classList.toggle('hidden');
      if (!filterGroupSec.classList.contains('hidden')) {
        filterDateSec.classList.add('hidden');
      }
    });
  }

  // PWA Install Button
  if (el.btnInstallPwa) {
    el.btnInstallPwa.addEventListener('click', async () => {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        if (outcome === 'accepted') {
          el.installBanner.classList.add('hidden');
        }
        deferredPrompt = null;
      }
    });
  }

  // Setup Form Listeners
  if (el.setupRole) {
    el.setupRole.addEventListener('change', (e) => {
      const role = e.target.value;
      if (role === 'student') {
        el.setupStudentFields.classList.remove('hidden');
        el.setupTeacherFields.classList.add('hidden');
      } else {
        el.setupStudentFields.classList.add('hidden');
        el.setupTeacherFields.classList.remove('hidden');
      }
    });
  }

  if (el.setupDept) {
    el.setupDept.addEventListener('change', populateSetupGroups);
  }

  if (el.setupForm) {
    el.setupForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const role = el.setupRole.value;
      const name = el.setupName.value.trim();
      let dept = 3;
      let groupId = null;
      let rooms = [];
      
      if (role === 'student') {
        dept = parseInt(el.setupDept.value);
        groupId = parseInt(el.setupGroup.value);
        if (!groupId) {
          alert('Пожалуйста, выберите группу');
          return;
        }
        localStorage.setItem('kalich_default_group', JSON.stringify([dept, groupId]));
      } else {
        dept = parseInt(el.setupTeacherDept.value);
        const roomsInput = el.setupRooms.value.trim();
        if (roomsInput) {
          rooms = roomsInput.split(',').map(r => r.trim()).filter(r => r);
        }
      }
      
      const userId = generateUUID();
      let finalRole = role;

      if (role === 'teacher') {
        finalRole = 'student'; // Initially set to student to allow viewing schedule
        try {
          await fetchAPI('/api/auth/request_teacher', {
            method: 'POST',
            body: JSON.stringify({
              device_id: userId,
              name: name,
              department: dept,
              rooms: rooms
            })
          });
          alert('Ваша заявка отправлена модераторам. Пока ожидаете, можете пользоваться расписанием как студент.');
        } catch(err) {
          console.error("Failed to send teacher request", err);
          alert("Не удалось отправить заявку, попробуйте позже.");
          return;
        }
      }
      
      state.user = {
        id: userId,
        name: name,
        role: finalRole,
        department: dept,
        group_id: groupId,
        rooms: rooms,
        settings: {
          notifications: 1,
          voice_alerts: 0,
          voice_effect: 'echo',
          fluffy_mode: 0
        }
      };
      
      localStorage.setItem('kalich_profile', JSON.stringify(state.user));
      
      el.viewSetup.classList.add('hidden');
      el.viewMain.classList.remove('hidden');
      startMainApp();
    });
  }

  // Navigation Tabs switching
  el.navButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabId = btn.getAttribute('data-tab');
      if (!tabId) return;
      
      // Update nav UI
      el.navButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      
      // Update views UI
      el.views.forEach(v => v.classList.remove('active'));
      document.getElementById(tabId)?.classList.add('active');
      
      state.currentTab = tabId;
      
      // Load relevant tab data
      if (tabId === 'tab-teacher') {
        loadTeacherSchedule();
      } else if (tabId === 'tab-analytics') {
        renderAnalyticsCharts();
      } else if (tabId === 'tab-moderator') {
        loadAdminOverrides();
      }
    });
  });

  // Schedule Filter change listeners
  el.selectDept.addEventListener('change', () => {
    populateGroupsDropdown();
    state.selectedGroup = null;
    state.selectedDate = '';
    el.inputScheduleDate.value = '';
    loadSchedule();
  });
  
  el.selectGroup.addEventListener('change', (e) => {
    state.selectedGroup = e.target.value;
    state.selectedDate = '';
    el.inputScheduleDate.value = '';
    loadSchedule();
  });

  // Date picker listener
  el.inputScheduleDate.addEventListener('change', (e) => {
    state.selectedDate = e.target.value;
    if (state.selectedDate) {
      // Clear active weekdays button selection
      document.querySelectorAll('.day-btn').forEach(b => b.classList.remove('active'));
    }
    loadSchedule();
  });

  // Day filter selector
  document.querySelectorAll('.day-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.day-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.selectedDate = '';
      el.inputScheduleDate.value = '';
      const val = btn.getAttribute('data-day');
      state.selectedDay = val === 'all' ? 'all' : parseInt(val);
      loadSchedule();
    });
  });

  // Teacher day selector
  document.querySelectorAll('.t-day-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.t-day-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.teacherSelectedDay = parseInt(btn.getAttribute('data-day'));
      loadTeacherSchedule();
    });
  });

  // ⭐ Favorite/Default Group button
  el.btnSaveDefault.addEventListener('click', () => {
    if (!state.selectedGroup) return;
    const value = [state.selectedDept, state.selectedGroup];
    
    // Toggle
    const saved = localStorage.getItem('kalich_default_group');
    if (saved && JSON.stringify(value) === saved) {
      localStorage.removeItem('kalich_default_group');
      el.btnSaveDefault.textContent = '☆';
      el.btnSaveDefault.classList.remove('active');
    } else {
      localStorage.setItem('kalich_default_group', JSON.stringify(value));
      el.btnSaveDefault.textContent = '★';
      el.btnSaveDefault.classList.add('active');
    }
    updateProfileUI();
  });

  // Sync Banner Button
  el.btnSyncRetry.addEventListener('click', processOfflineQueue);

  if (el.btnCloseModal) {
    el.btnCloseModal.addEventListener('click', () => el.overrideModal.classList.add('hidden'));
  }
  
  if (el.btnCancelLesson) {
    el.btnCancelLesson.addEventListener('click', () => {
      el.overrideSubject.value = 'Отменено';
      el.overrideRoom.value = '';
      el.overrideForm.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
      // Show undo button after cancelling a lesson
      if (el.btnUndoCancel) {
        el.btnUndoCancel.classList.remove('hidden');
      }
    });
  }
  
  if (el.btnUndoCancel) {
    el.btnUndoCancel.addEventListener('click', () => {
      // "Отменить отмену" effectively means resetting the override
      if (el.btnDeleteOverride) {
        el.btnDeleteOverride.click();
      }
      // Hide undo button after undo action
      el.btnUndoCancel.classList.add('hidden');
    });
  }

  // Teacher Schedule Date Picker
  if (el.inputTeacherDate) {
    el.inputTeacherDate.addEventListener('change', (e) => {
      state.teacherSelectedDate = e.target.value;
      const d = new Date(e.target.value).getDay();
      state.teacherSelectedDay = d === 0 ? 1 : d;
      loadTeacherSchedule();
    });
  }

  // Override Form submission
  el.overrideForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Determine the date to send with override
    let overrideDate = state.teacherSelectedDate || state.selectedDate || state.currentDate;
    
    const groupVal = el.overrideGroup.value;
    let overrideDept = state.user.department;
    let overrideGroupId = -1;
    if (groupVal !== "-1") {
      const parts = groupVal.split('-');
      overrideDept = parseInt(parts[0]);
      overrideGroupId = parseInt(parts[1]);
    }
    
    const override = {
      teacher_chat_id: state.user.id,
      department: overrideDept,
      day: parseInt(el.overrideDay.value),
      slot_idx: parseInt(el.overrideSlot.value),
      group_id: overrideGroupId,
      new_room: el.overrideRoom.value.trim(),
      new_subject: el.overrideSubject.value.trim(),
      date: overrideDate
    };

    el.overrideModal.classList.add('hidden');

    if (!navigator.onLine) {
      queueOverride(override);
    } else {
      try {
        const result = await fetchAPI('/api/override', {
          method: 'POST',
          body: JSON.stringify({
            device_id: state.user.id,
            ...override
          })
        });

        if (result && !result.error) {
          loadTeacherSchedule();
          loadSchedule();
          alert('Замена успешно сохранена!');
        } else {
          alert('Ошибка сохранения: ' + (result?.error || 'Неизвестная ошибка'));
        }
      } catch (err) {
        console.error(err);
        queueOverride(override); // Queue if network error
      }
    }
  });

  // Delete/Clear Override
  el.btnDeleteOverride.addEventListener('click', async () => {
    const day = parseInt(el.overrideDay.value);
    const slot_idx = parseInt(el.overrideSlot.value);
    
    const groupVal = el.overrideGroup.value;
    let overrideDept = state.user.department;
    let overrideGroupId = -1;
    if (groupVal !== "-1") {
      const parts = groupVal.split('-');
      overrideDept = parseInt(parts[0]);
      overrideGroupId = parseInt(parts[1]);
    }

    // Determine the date to send with override
    let overrideDate = state.selectedDate;
    if (state.currentTab === 'tab-teacher') {
      const d = state.teacherSelectedDay;
      const today = new Date();
      const dayOfWeek = today.getDay();
      const diff = today.getDate() - (dayOfWeek === 0 ? 7 : dayOfWeek) + d;
      const targetDt = new Date(today.setDate(diff));
      overrideDate = formatDate(targetDt);
    } else if (!overrideDate && state.selectedDay && state.selectedDay !== 'all') {
      const d = state.selectedDay;
      const today = new Date();
      const dayOfWeek = today.getDay();
      const diff = today.getDate() - (dayOfWeek === 0 ? 7 : dayOfWeek) + d;
      const targetDt = new Date(today.setDate(diff));
      overrideDate = formatDate(targetDt);
    }

    el.overrideModal.classList.add('hidden');

    const clearAction = {
      teacher_chat_id: state.user.id,
      department: overrideDept,
      day: day,
      slot_idx: slot_idx,
      group_id: overrideGroupId,
      new_room: "",
      new_subject: "", // Empty fields clear overrides
      date: overrideDate
    };

    if (!navigator.onLine) {
      queueOverride(clearAction);
    } else {
      try {
        const result = await fetchAPI('/api/override', {
          method: 'POST',
          body: JSON.stringify({
            device_id: state.user.id,
            ...clearAction
          })
        });
        if (result && !result.error) {
          loadTeacherSchedule();
          loadSchedule();
        }
      } catch (err) {
        queueOverride(clearAction);
      }
    }
  });

  // Online / Offline window events
  window.addEventListener('online', updateOnlineStatus);
  window.addEventListener('offline', updateOnlineStatus);

  const saveSettings = async () => {
    const settings = {
      notifications: el.settingNotifications.checked ? 1 : 0,
      voice_alerts: el.settingVoice.checked ? 1 : 0,
      voice_effect: el.settingVoiceEffect.value,
      fluffy_mode: el.settingFluffy.checked ? 1 : 0
    };

    state.user.settings = settings;
    localStorage.setItem('kalich_profile', JSON.stringify(state.user));

    applySettings();

    // Send settings update to server if online
    if (navigator.onLine) {
      try {
        await fetchAPI('/api/settings', {
          method: 'POST',
          body: JSON.stringify({
            device_id: state.user.id,
            settings
          })
        });
      } catch (e) {
        console.warn("Failed to sync settings with server", e);
      }
    }
  };

  el.settingNotifications.addEventListener('change', saveSettings);
  el.settingVoice.addEventListener('change', saveSettings);
  el.settingVoiceEffect.addEventListener('change', saveSettings);
  el.settingFluffy.addEventListener('change', saveSettings);

  // Voice Synthesis Logic
  const voiceBtn = document.getElementById('btn-read-schedule');
  if (voiceBtn) {
    voiceBtn.addEventListener('click', () => {
      if (!window.speechSynthesis) return;
      
      window.speechSynthesis.cancel(); // stop previous
      
      const title = el.scheduleTitle.textContent;
      const cards = el.scheduleList.querySelectorAll('.lesson-card');
      
      let textToRead = title + ". ";
      
      if (cards.length === 0) {
        textToRead += "Занятий нет, выходной!";
      } else {
        cards.forEach(card => {
          const num = card.querySelector('.lesson-num')?.textContent || "";
          const subj = card.querySelector('.lesson-subject')?.textContent || "";
          const roomEl = card.querySelector('.lesson-room-group strong');
          const room = roomEl ? "Кабинет " + roomEl.textContent : "";
          const isOverride = card.querySelector('.badge-override') ? "Внимание, замена! " : "";
          
          textToRead += `${num}. ${isOverride}${subj}. ${room}. `;
        });
      }
      
      const utterance = new SpeechSynthesisUtterance(textToRead);
      utterance.lang = 'ru-RU';
      
      const effect = state.user.settings?.voice_effect || 'normal';
      if (effect === 'high') {
        utterance.pitch = 1.8;
      } else if (effect === 'low') {
        utterance.pitch = 0.5;
      } else {
        utterance.pitch = 1.0;
      }
      
      window.speechSynthesis.speak(utterance);
    });
  }

  // Reset Profile Listener
  if (document.getElementById('btn-reset-profile')) {
    document.getElementById('btn-reset-profile').addEventListener('click', () => {
      if (confirm('Вы уверены, что хотите выйти из профиля и сбросить настройки?')) {
        localStorage.removeItem('kalich_profile');
        localStorage.removeItem('kalich_default_group');
        location.reload();
      }
    });
  }

  // Moderator buttons listeners
  const formatDate = (date) => {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  };

  el.btnAdminWeekCurrent.addEventListener('click', () => {
    const today = new Date();
    const day = today.getDay();
    const diff = today.getDate() - day + (day === 0 ? -6 : 1);
    const monday = new Date(today.setDate(diff));
    const saturday = new Date(monday);
    saturday.setDate(monday.getDate() + 5);
    el.adminDateStart.value = formatDate(monday);
    el.adminDateEnd.value = formatDate(saturday);
  });

  el.btnAdminWeekNext.addEventListener('click', () => {
    const today = new Date();
    const day = today.getDay();
    const diff = today.getDate() - day + (day === 0 ? -6 : 1) + 7;
    const monday = new Date(today.setDate(diff));
    const saturday = new Date(monday);
    saturday.setDate(monday.getDate() + 5);
    el.adminDateStart.value = formatDate(monday);
    el.adminDateEnd.value = formatDate(saturday);
  });

  el.btnAdminFill.addEventListener('click', async () => {
    const start = el.adminDateStart.value;
    const end = el.adminDateEnd.value;
    const dept = el.adminDept.value;
    el.btnAdminFill.disabled = true;
    el.btnAdminFill.textContent = 'Запуск...';
    try {
      const res = await fetchAPI('/api/admin/fill', {
        method: 'POST',
        body: JSON.stringify({
          device_id: state.user.id,
          start_date: start,
          end_date: end,
          department: dept
        })
      });
      if (res && res.status === 'success') {
        alert('Заполнение базы запущено! Это займет до 1-2 минут.');
      } else {
        alert('Ошибка запуска: ' + (res?.error || 'Неизвестно'));
      }
    } catch (e) {
      alert('Ошибка сети.');
    } finally {
      el.btnAdminFill.disabled = false;
      el.btnAdminFill.textContent = 'Заполнить кэш';
    }
  });

  el.btnAdminFlush.addEventListener('click', async () => {
    const start = el.adminDateStart.value;
    const end = el.adminDateEnd.value;
    const dept = el.adminDept.value;
    const confirmMsg = start && end 
      ? `Вы действительно хотите очистить кэш расписания с ${start} по ${end} (отделение: ${dept})?`
      : `Вы действительно хотите очистить кэш (отделение: ${dept})? Все скачанные расписания будут стерты (история и замены сохранятся).`;
      
    if (!confirm(confirmMsg)) return;
    try {
      const res = await fetchAPI('/api/admin/flush', {
        method: 'POST',
        body: JSON.stringify({
          device_id: state.user.id,
          start_date: start,
          end_date: end,
          department: dept
        })
      });
      if (res && res.status === 'success') {
        alert('Кэш успешно очищен!');
        loadSchedule();
      }
    } catch (e) {
      alert('Ошибка сети.');
    }
  });
}

function renderDepartmentSchedule(dept_schedules) {
  el.scheduleList.innerHTML = '';
  const entries = Object.entries(dept_schedules).sort((a,b) => a[0].localeCompare(b[0]));
  
  if (entries.length === 0) {
    el.scheduleList.innerHTML = `<div class="empty-state"><p>Нет групп в этом отделении</p></div>`;
    return;
  }
  
  const container = document.createElement('div');
  container.className = 'schedule-grid-container';
  
  const table = document.createElement('table');
  table.className = 'schedule-grid-table';
  
  // Table Header
  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  headerRow.innerHTML = `
    <th>Группа</th>
    <th>Пара 1<br><small>08:20-09:50</small></th>
    <th>Пара 2<br><small>10:00-11:30</small></th>
    <th>Пара 3<br><small>11:35-13:10</small></th>
    <th>Пара 4<br><small>13:15-14:45</small></th>
    <th>Пара 5<br><small>14:50-16:25</small></th>
  `;
  thead.appendChild(headerRow);
  table.appendChild(thead);
  
  // Table Body
  const tbody = document.createElement('tbody');
  
  entries.forEach(([gname, lessons]) => {
    const row = document.createElement('tr');
    
    // Group Name cell
    const groupCell = document.createElement('td');
    groupCell.className = 'grid-group-name';
    groupCell.textContent = gname;
    row.appendChild(groupCell);
    
    // 5 Double Lessons
    for (let i = 0; i < 5; i++) {
      const cell = document.createElement('td');
      cell.className = 'grid-cell';
      
      const s1 = lessons[i * 2] || "—";
      const s2 = lessons[i * 2 + 1] || "—";
      
      const isEmpty = (s1 === "—" || s1 === "." || s1 === "x") && (s2 === "—" || s2 === "." || s2 === "x");
      
      if (isEmpty) {
        cell.textContent = "—";
        cell.classList.add('empty-cell');
      } else {
        const subject = s1 === s2 ? s1 : `${s1} / ${s2}`;
        let room = "";
        const roomMatch = subject.match(/\(([^)]+)\)/);
        if (roomMatch) room = roomMatch[1];
        const cleanSubject = subject.replace(/\s*\([^)]+\)/g, '').trim();
        
        const dispSubject = cleanSubject.length > 25 ? cleanSubject.slice(0, 23) + '..' : cleanSubject;
        
        cell.innerHTML = `<strong>${dispSubject}</strong>${room ? `<br><span style="color:var(--text-secondary);font-size:10px;">🚪 Каб. ${room}</span>` : ''}`;
        
        if (subject.toLowerCase().includes('замена') || subject.includes('(изм)')) {
          cell.classList.add('override');
        }
      }
      
      // If user is moderator or teacher, make cell interactive to change it
      if (state.user.role === 'moderator' || state.user.role === 'teacher') {
        cell.addEventListener('click', () => {
          if (state.groups[gname]) {
            const gid = state.groups[gname][1];
            const slotsData = [
              [gname, s1, s1.match(/\(([^)]+)\)/)?.[1] || ""],
              [gname, s2, s2.match(/\(([^)]+)\)/)?.[1] || ""]
            ];
            // Open modal for double lesson i (starts at slot i*2)
            openOverrideModal(i * 2, slotsData);
            el.overrideGroup.value = gid;
          }
        });
      }
      
      row.appendChild(cell);
    }
    
    tbody.appendChild(row);
  });
  
  table.appendChild(tbody);
  container.appendChild(table);
  el.scheduleList.appendChild(container);
}

function renderWeekSchedule(week_schedules) {
  el.scheduleList.innerHTML = '';
  const dayNames = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота"
  };
  
  for (let d = 1; d <= 6; d++) {
    const lessons = week_schedules[d] || [];
    
    const section = document.createElement('div');
    section.className = 'card';
    section.style.marginBottom = '12px';
    section.style.padding = '12px';
    
    const title = document.createElement('h3');
    title.textContent = dayNames[d];
    title.style.fontSize = '14px';
    title.style.marginBottom = '8px';
    title.style.borderBottom = '1px solid var(--border-color)';
    title.style.paddingBottom = '4px';
    section.appendChild(title);
    
    const lessonsList = document.createElement('div');
    lessonsList.className = 'schedule-list';
    
    const totalDoubleLessons = Math.ceil(lessons.length / 2);
    let count = 0;
    for (let i = 0; i < totalDoubleLessons; i++) {
      const s1 = lessons[i * 2] || "—";
      const s2 = lessons[i * 2 + 1] || "—";
      
      const isEmpty = (s1 === "—" || s1 === "." || s1 === "x") && (s2 === "—" || s2 === "." || s2 === "x");
      if (isEmpty) continue;
      
      const time = CALL_TIMES[i] || ["??:??", "??:??"];
      const subject = s1 === s2 ? s1 : `${s1} / ${s2}`;
      
      let room = "";
      const roomMatch = subject.match(/\(([^)]+)\)/);
      if (roomMatch) room = roomMatch[1];
      const cleanSubject = subject.replace(/\s*\([^)]+\)/g, '').trim();
      
      const card = document.createElement('div');
      card.className = 'lesson-card';
      card.style.padding = '8px 12px';
      card.style.gap = '8px';
      
      card.innerHTML = `
        <div class="lesson-time" style="min-width:60px;padding-right:8px;">
          <span class="time-start" style="font-size:13px;">${time[0]}</span>
          <span class="time-end" style="font-size:10px;">${time[1]}</span>
        </div>
        <div class="lesson-details">
          <div class="lesson-subject" style="font-size:13px;">${cleanSubject}</div>
          <div class="lesson-room-group" style="font-size:11px;">
            ${room ? `<span>🚪 Каб: <strong>${room}</strong></span>` : ''}
          </div>
        </div>
      `;
      lessonsList.appendChild(card);
      count++;
    }
    
    if (count === 0) {
      lessonsList.innerHTML = `<div class="empty-state" style="padding:10px;"><p style="font-size:12px;margin:0;">Занятий нет</p></div>`;
    }
    section.appendChild(lessonsList);
    el.scheduleList.appendChild(section);
  }
}

async function loadAdminOverrides() {
  el.adminOverridesList.innerHTML = `<div class="empty-state">Загрузка замен...</div>`;
  try {
    const data = await fetchAPI('/api/admin/overrides');
    if (data && data.overrides) {
      renderAdminOverrides(data.overrides);
    }
  } catch (e) {
    el.adminOverridesList.innerHTML = `<div class="empty-state"><p>Ошибка загрузки замен.</p></div>`;
  }
}

function renderAdminOverrides(overrides) {
  if (!overrides || overrides.length === 0) {
    el.adminOverridesList.innerHTML = `<div class="empty-state">Нет активных замен в базе данных</div>`;
    return;
  }
  
  el.adminOverridesList.innerHTML = '';
  const dayNames = { 1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб" };
  
  const overridesByDept = { 1: [], 2: [], 3: [] };
  overrides.forEach(o => {
    const dep = o.department || 3;
    if (overridesByDept[dep]) {
      overridesByDept[dep].push(o);
    }
  });

  for (const dep of [1, 2, 3]) {
    const list = overridesByDept[dep];
    if (list.length === 0) continue;

    const deptHeader = document.createElement('h4');
    deptHeader.textContent = `Отделение ${dep}`;
    deptHeader.style.marginTop = '15px';
    deptHeader.style.marginBottom = '8px';
    deptHeader.style.fontSize = '13px';
    deptHeader.style.color = 'var(--text-secondary)';
    deptHeader.style.borderBottom = '1px solid var(--border-color)';
    deptHeader.style.paddingBottom = '4px';
    el.adminOverridesList.appendChild(deptHeader);

    list.forEach(o => {
      const card = document.createElement('div');
      card.className = 'lesson-card';
      card.style.justifyContent = 'space-between';
      card.style.alignItems = 'center';
      
      const details = document.createElement('div');
      details.className = 'lesson-details';
      
      const title = document.createElement('div');
      title.className = 'lesson-subject';
      title.style.fontSize = '14px';
      title.textContent = `${o.new_subject || "Без изменения предмета"}`;
      
      const desc = document.createElement('div');
      desc.className = 'lesson-room-group';
      desc.innerHTML = `
        <span>📅 ${dayNames[o.day] || "?"}, Урок ${o.slot_idx + 1}</span>
        <span>👥 ${o.group_name} (Отд. ${o.department})</span>
        ${o.new_room ? `<span>🚪 Каб: <strong>${o.new_room}</strong></span>` : ''}
      `;
      
      details.appendChild(title);
      details.appendChild(desc);
      
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'btn btn-danger';
      deleteBtn.style.padding = '6px 12px';
      deleteBtn.style.fontSize = '12px';
      deleteBtn.textContent = 'Удалить';
      deleteBtn.addEventListener('click', async () => {
        if (!confirm('Удалить эту замену?')) return;
        try {
          const res = await fetchAPI('/api/admin/delete_override', {
            method: 'POST',
            body: JSON.stringify({ initData: tg?.initData || "", id: o.id })
          });
          if (res && res.status === 'success') {
            loadAdminOverrides();
          }
        } catch (e) {
          alert('Ошибка сети.');
        }
      });
      
      card.appendChild(details);
      card.appendChild(deleteBtn);
      el.adminOverridesList.appendChild(card);
    });
  }
}

// =================== UTILS ===================
async function fetchAPI(url, options = {}) {
  const defaultHeaders = {
    'Content-Type': 'application/json'
  };

  options.headers = {
    ...defaultHeaders,
    ...options.headers
  };

  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return await response.json();
}

// Register service worker for installable PWA
let refreshing = false;

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').then(reg => {
      console.log('ServiceWorker registration successful', reg.scope);

      // Setup update flow
      reg.addEventListener('updatefound', () => {
        const newWorker = reg.installing;
        newWorker.addEventListener('statechange', () => {
          if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
            // New update available! Show banner.
            const updateBanner = document.getElementById('update-banner');
            const btnUpdateApp = document.getElementById('btn-update-app');
            if (updateBanner && btnUpdateApp) {
              updateBanner.classList.remove('hidden');
              btnUpdateApp.addEventListener('click', () => {
                updateBanner.classList.add('hidden');
                newWorker.postMessage({ type: 'SKIP_WAITING' });
              });
            }
          }
        });
      });
    }).catch(err => console.error('ServiceWorker registration failed', err));

    // Listen for the controlling service worker changing
    // and reload the page
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (!refreshing) {
        refreshing = true;
        window.location.reload();
      }
    });
  });
}

// Launch App
initApp();
