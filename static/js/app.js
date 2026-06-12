// Frontend behavior for the Calendar Matching app UI.
document.addEventListener("DOMContentLoaded", () => {
    let currentDisplayDate = null;
    let busyDataA = { busy: [] };
    let busyDataB = { busy: [] };
    let combinedBusy = [];
    let suggestedSlots = [];
    let userPrefs = [];
    let showCalendarA = true;
    let showCalendarB = true;
    let accountsLoaded = 0;
    let currentUser = null;
    let currentInviteRequestId = null;
    const requiresAuth = document.body.dataset.requiresAuth === "true";

    function $(id) {
        return document.getElementById(id);
    }

    function setText(id, text) {
        const el = $(id);
        if (el) el.textContent = text;
    }

    function setBadge(id, text, className) {
        const el = $(id);
        if (!el) return;
        el.textContent = text;
        el.className = `badge ${className}`;
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function ensureSuggestedContainer() {
        let el = $("suggestedSlots");
        if (!el) {
            el = document.createElement("div");
            el.id = "suggestedSlots";
            const grid = $("calendarGrid");
            if (grid && grid.parentNode) {
                grid.parentNode.insertBefore(el, grid);
            } else {
                document.body.appendChild(el);
            }
        }
        return el;
    }

    function updateHealth() {
        fetch("/api/health")
            .then((r) => r.json())
            .then((d) => {
                const el = $("health");
                if (el) el.style.background = d.status === "healthy" ? "#16a34a" : "#dc2626";
            })
            .catch(() => {
                const el = $("health");
                if (el) el.style.background = "#dc2626";
            });
    }
    setInterval(updateHealth, 5000);
    updateHealth();

    function userDisplayName(user) {
        return user.display_name || user.email;
    }

    function setSessionUi(user) {
        if (!user) {
            if (requiresAuth) window.location.replace("/login");
            return;
        }

        const menuName = $("userMenuName");
        if (menuName) menuName.textContent = userDisplayName(user);

        const publicNav = $("publicNav");
        if (publicNav) {
            publicNav.innerHTML = `
                <li class="nav-item"><a class="nav-link" href="/dashboard">Dashboard</a></li>
                <li class="nav-item"><a class="nav-link" href="/requests/new">New request</a></li>
                <li class="nav-item"><button class="btn btn-outline-secondary" id="homeLogoutBtn" type="button">Log out</button></li>`;
            const homeLogoutBtn = $("homeLogoutBtn");
            if (homeLogoutBtn) {
                homeLogoutBtn.onclick = async () => {
                    await fetch("/auth/logout", { method: "POST" });
                    window.location.replace("/");
                };
            }
        }
    }

    async function loadCurrentUser() {
        const res = await fetch("/auth/me");
        if (!res.ok) {
            setSessionUi(null);
            return null;
        }
        const user = await res.json();
        currentUser = user;
        setSessionUi(user);
        return user;
    }

    const logoutBtn = $("logoutBtn");
    if (logoutBtn) {
        logoutBtn.onclick = async () => {
            await fetch("/auth/logout", { method: "POST" });
            window.location.replace("/login");
        };
    }

    function showEmail(label, email) {
        const container = $("emails");
        if (!container) return;
        const p = document.createElement("p");
        p.className = "mb-1";
        p.textContent = `${email} connected`;
        container.appendChild(p);
    }

    function populateTimeSelects() {
        const table = $("prefsTable");
        if (!table) return;

        table.querySelectorAll("select").forEach((sel) => {
            if (sel.options && sel.options.length > 0) return;
            for (let h = 0; h < 24; h++) {
                const hh = String(h).padStart(2, "0");
                const opt = document.createElement("option");
                opt.value = hh;
                opt.textContent = hh;
                sel.appendChild(opt);
            }
        });
    }

    function setDefaultDates() {
        const earliest = $("earliestDate");
        const latest = $("latestDate");
        if (!earliest || !latest || earliest.value || latest.value) return;

        const now = new Date();
        const start = new Date(now);
        start.setUTCDate(start.getUTCDate() + 1);
        const end = new Date(start);
        end.setUTCDate(end.getUTCDate() + 14);
        earliest.value = start.toISOString().slice(0, 10);
        latest.value = end.toISOString().slice(0, 10);
    }

    function getDateRange() {
        const earliest = $("earliestDate")?.value;
        const latest = $("latestDate")?.value;
        if (earliest && latest) {
            return {
                timeMin: `${earliest}T00:00:00.000Z`,
                timeMax: `${latest}T23:59:59.000Z`,
            };
        }
        const now = new Date();
        const later = new Date(now.getTime() + 7 * 24 * 3600 * 1000);
        return { timeMin: now.toISOString(), timeMax: later.toISOString() };
    }

    function collectAvailabilityWindows(containerId = "timeWindowsContainer") {
        const container = $(containerId);
        if (!container) return null;
        const prefs = [];
        container.querySelectorAll(".availability-window").forEach((windowEl) => {
            const start = windowEl.querySelector(".window-start")?.value || "09:00";
            const end = windowEl.querySelector(".window-end")?.value || "17:00";
            windowEl.querySelectorAll(".weekday-input").forEach((input) => {
                if (input.checked) prefs.push({ day: input.dataset.day, start, end });
            });
        });
        return prefs;
    }

    function getPrefsFromTable() {
        const availabilityPrefs = collectAvailabilityWindows();
        if (availabilityPrefs) return availabilityPrefs;

        const weekdayInputs = document.querySelectorAll(".weekday-input");
        if (weekdayInputs.length > 0) {
            const start = $("windowStart")?.value || "09:00";
            const end = $("windowEnd")?.value || "17:00";
            return Array.from(weekdayInputs)
                .filter((input) => input.checked)
                .map((input) => ({ day: input.dataset.day, start, end }));
        }

        const table = $("prefsTable");
        if (!table) return [];

        const prefs = [];
        table.querySelectorAll("tbody tr").forEach((row) => {
            const checkbox = row.querySelector("input[type=checkbox]");
            if (!checkbox || !checkbox.checked) return;

            const day = checkbox.dataset.day;
            const startSel = row.querySelector("select.start");
            const endSel = row.querySelector("select.end");
            if (!day || !startSel || !endSel) return;

            prefs.push({ day, start: `${startSel.value}:00`, end: `${endSel.value}:00` });
        });
        return prefs;
    }

    function convertPrefsArray(arr) {
        const days = { Mon: 0, Tue: 1, Wed: 2, Thu: 3, Fri: 4, Sat: 5, Sun: 6 };
        return (arr || [])
            .map((p) => ({ day: Number.isInteger(p.day) ? p.day : days[p.day], start: p.start, end: p.end }))
            .filter((p) => Number.isInteger(p.day) && p.day >= 0 && p.day <= 6 && p.start && p.end && p.start < p.end);
    }

    function groupWindowsByTime(windows) {
        const grouped = new Map();
        (windows || []).forEach((window) => {
            const day = Number.isInteger(window.day) ? window.day : dayNames.indexOf(window.day);
            if (day < 0 || day > 6 || !window.start || !window.end) return;
            const key = `${window.start}|${window.end}`;
            if (!grouped.has(key)) grouped.set(key, { start: window.start, end: window.end, days: [] });
            grouped.get(key).days.push(day);
        });
        return Array.from(grouped.values());
    }

    function availabilityWindowTemplate(index, group = {}) {
        const prefix = group.prefix || "window";
        const checkboxClass = group.checkboxClass || "weekday-input";
        const startId = index === 0 && prefix === "window" ? "windowStart" : `${prefix}Start-${index}`;
        const endId = index === 0 && prefix === "window" ? "windowEnd" : `${prefix}End-${index}`;
        const selectedDays = new Set(group.days || (index === 0 ? [0, 1, 2, 3, 4] : []));
        const dayButtons = dayNames.map((dayName, dayIndex) => {
            const id = `${prefix}Day-${index}-${dayName}`;
            return `<input class="btn-check ${checkboxClass}" type="checkbox" id="${id}" data-day="${dayName}" ${selectedDays.has(dayIndex) ? "checked" : ""}><label class="btn btn-outline-primary" for="${id}">${dayName}</label>`;
        }).join("");
        return `
            <div class="availability-window border rounded-4 p-3" data-window-index="${index}">
                <div class="d-flex justify-content-between align-items-center gap-2 mb-2">
                    <h3 class="h6 mb-0">Time set ${index + 1}</h3>
                    ${index > 0 ? '<button class="btn btn-outline-danger btn-sm remove-time-window" type="button">Remove</button>' : '<span class="badge text-bg-light">Shared days and timing</span>'}
                </div>
                <div class="weekday-selector mb-3" role="group" aria-label="Allowed weekdays for time set ${index + 1}">${dayButtons}</div>
                <div class="row g-3">
                    <div class="col-6"><label class="form-label" for="${startId}">Between</label><input id="${startId}" type="time" class="form-control window-start" value="${escapeHtml(group.start || "09:00")}"></div>
                    <div class="col-6"><label class="form-label" for="${endId}">And</label><input id="${endId}" type="time" class="form-control window-end" value="${escapeHtml(group.end || "17:00")}"></div>
                </div>
            </div>`;
    }

    function wireAvailabilityWindowRemovers(container) {
        container.querySelectorAll(".remove-time-window").forEach((button) => {
            button.onclick = () => button.closest(".availability-window")?.remove();
        });
    }

    function addAvailabilityWindow(containerId = "timeWindowsContainer", group = {}) {
        const container = $(containerId);
        if (!container) return;
        const index = container.querySelectorAll(".availability-window").length;
        container.insertAdjacentHTML("beforeend", availabilityWindowTemplate(index, group));
        wireAvailabilityWindowRemovers(container);
    }

    function setAvailabilityWindows(windows, containerId = "timeWindowsContainer", options = {}) {
        const container = $(containerId);
        if (!container) return;
        const groups = groupWindowsByTime(windows);
        container.innerHTML = (groups.length ? groups : [{ days: [0, 1, 2, 3, 4], start: "09:00", end: "17:00" }])
            .map((group, index) => availabilityWindowTemplate(index, { ...group, ...options }))
            .join("");
        wireAvailabilityWindowRemovers(container);
    }

    function inPref(isoDateTime, prefs) {
        const d = new Date(isoDateTime);
        const weekday = (d.getUTCDay() + 6) % 7; // Convert JS Sun=0 to Python-style Mon=0.
        const time = d.toISOString().slice(11, 16);
        return prefs.some((p) => p.day === weekday && time >= p.start && time < p.end);
    }

    function isBusy(dateStr, busyData) {
        const busyArr = (busyData && busyData.busy) || [];
        return busyArr.some((b) => {
            if (!b?.start || !b?.end) return false;
            if (b.start === b.end) return dateStr === b.start;
            return dateStr >= b.start && dateStr < b.end;
        });
    }

    function isSuggested(dateStr) {
        const isBusyCombined = (combinedBusy || []).some((b) => dateStr >= b.start && dateStr < b.end);
        const inPrefTime = userPrefs.length === 0 || inPref(dateStr, userPrefs);
        return !isBusyCombined && inPrefTime;
    }

    function renderOptionCards() {
        const optionCards = $("optionCards");
        if (!optionCards) return;

        if (!suggestedSlots || suggestedSlots.length === 0) {
            optionCards.innerHTML = '<div class="col-12"><div class="empty-state rounded-4 p-4 text-center">No shared free time was found. Try extending the date range or relaxing the allowed hours.</div></div>';
            return;
        }

        optionCards.innerHTML = suggestedSlots.slice(0, 3).map((slot, index) => {
            const start = new Date(slot.start);
            const end = new Date(slot.end);
            const label = index === 0 ? "Best option" : `Option ${index + 1}`;
            const badge = index === 0 ? "text-bg-success" : "text-bg-light";
            const border = index === 0 ? "border-success" : "";
            const day = start.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
            const startTime = start.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
            const endTime = end.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
            const reason = slot.reason || "Both calendars are free and the slot fits your request constraints.";
            return `
                <div class="col-md-4">
                    <div class="option-card card h-100 ${border}">
                        <div class="card-body p-4">
                            <span class="badge ${badge}">${label}</span>
                            <h3 class="h5 mt-3">${escapeHtml(day)}</h3>
                            <p class="fs-5 fw-semibold mb-1">${escapeHtml(startTime)}–${escapeHtml(endTime)}</p>
                            <p class="small text-secondary">Shown in your browser timezone</p>
                            <p class="small">${escapeHtml(reason)}</p>
                            <button class="btn ${index === 0 ? "btn-success" : "btn-outline-primary"} w-100" type="button">Choose this option</button>
                        </div>
                    </div>
                </div>`;
        }).join("");
    }

    function renderSuggestedSlots() {
        const el = ensureSuggestedContainer();

        if (!suggestedSlots || suggestedSlots.length === 0) {
            el.innerHTML = "<div class='suggestedItem'>No suggested slots found.</div>";
            renderOptionCards();
            return;
        }

        const items = suggestedSlots.slice(0, 3).map((slot, index) => {
            const startDate = new Date(slot.start).toLocaleString("en-US", {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
            });
            const endTime = new Date(slot.end).toLocaleTimeString("en-US", {
                hour: "2-digit",
                minute: "2-digit",
            });
            return `<div class="suggestedItem"><strong>${index === 0 ? "Best option" : `Option ${index + 1}`}</strong><br>${startDate} → ${endTime}</div>`;
        }).join("");

        el.innerHTML = `<h3 class="h5">Top suggested meeting times</h3><div class="suggested-grid">${items}</div>`;
        renderOptionCards();
    }

    function renderCalendarGrid(displayDate) {
        const container = $("calendarGrid");
        if (!container) return;
        container.innerHTML = "";

        const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
        const dayName = dayNames[displayDate.getUTCDay()];
        const dateStr = displayDate.toISOString().split("T")[0];
        setText("currentDate", `${dateStr} (${dayName})`);

        let gridCols = "70px";
        if (showCalendarA) gridCols += " minmax(130px, 1fr)";
        if (showCalendarB) gridCols += " minmax(130px, 1fr)";
        gridCols += " minmax(130px, 1fr)";
        container.style.gridTemplateColumns = gridCols;

        const headers = ["Time"];
        if (showCalendarA) headers.push("Requester");
        if (showCalendarB) headers.push("Invitee");
        headers.push("Available");
        headers.forEach((header, index) => {
            const el = document.createElement("div");
            el.className = index === 0 ? "timeColumnHeader" : "dayColumnHeader";
            el.textContent = header;
            container.appendChild(el);
        });

        for (let hour = 0; hour < 24; hour++) {
            for (let min = 0; min < 60; min += 30) {
                const hh = String(hour).padStart(2, "0");
                const mm = String(min).padStart(2, "0");
                const timeStr = `${hh}:${mm}`;
                const slotDateTime = `${dateStr}T${timeStr}:00Z`;

                const timeCell = document.createElement("div");
                timeCell.className = "timeSlot timeLabel";
                timeCell.textContent = timeStr;
                container.appendChild(timeCell);

                if (showCalendarA) {
                    const slotA = document.createElement("div");
                    slotA.className = "timeSlot";
                    if (isBusy(slotDateTime, busyDataA)) {
                        slotA.classList.add("busyA");
                        slotA.textContent = "Busy";
                    }
                    container.appendChild(slotA);
                }

                if (showCalendarB) {
                    const slotB = document.createElement("div");
                    slotB.className = "timeSlot";
                    if (isBusy(slotDateTime, busyDataB)) {
                        slotB.classList.add("busyB");
                        slotB.textContent = "Busy";
                    }
                    container.appendChild(slotB);
                }

                const slotAvail = document.createElement("div");
                slotAvail.className = "timeSlot";
                if (isSuggested(slotDateTime)) {
                    slotAvail.classList.add("suggested");
                    slotAvail.textContent = "✓ Free";
                }
                container.appendChild(slotAvail);
            }
        }
    }

    async function loadAccounts() {
        const res = await fetch("/accounts");
        if (res.status === 401) {
            if (requiresAuth) window.location.replace("/login");
            return;
        }
        if (!res.ok) return;

        const list = await res.json();
        accountsLoaded = list.length;
        renderProfileLinkedCalendars(list);

        const emails = $("emails");
        if (emails) emails.innerHTML = "";
        list.forEach((acc) => showEmail(acc.account_label, acc.email));

        const calendarSelects = ["requestAccountSelect", "requestOwnerCalendar", "inviteCalendarSelect"]
            .map((id) => $(id))
            .filter(Boolean);
        if (calendarSelects.length === 0) return;

        calendarSelects.forEach((select) => {
            select.innerHTML = "";
            if (list.length === 0) {
                select.innerHTML = '<option value="">No connected calendars yet</option>';
                return;
            }
            list.forEach((acc) => {
                const opt = document.createElement("option");
                opt.value = acc.account_label;
                opt.textContent = acc.email;
                select.appendChild(opt);
            });
            if (profileLinkedCalendarLabels[0]) select.value = profileLinkedCalendarLabels[0];
        });
    }



    function presetToText(preset) {
        const names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
        return (preset.windows || []).map((w) => `${names[w.day] || w.day} ${w.start}-${w.end}`).join(", ");
    }

    let profilePresets = [];
    let profileLinkedCalendarLabels = [];

    function renderProfileLinkedCalendars(accounts) {
        const container = $('profileLinkedCalendarList');
        if (!container) return;
        if (!accounts || accounts.length === 0) {
            container.innerHTML = `<div class="border rounded-4 p-3 bg-white"><p class="mb-2 fw-semibold">No calendars connected yet.</p><p class="small text-secondary mb-0">Use the connector below to add your first Google calendar account to this profile.</p></div>`;
            return;
        }
        container.innerHTML = accounts.map((account) => {
            const label = escapeHtml(account.account_label);
            const checked = profileLinkedCalendarLabels.includes(account.account_label) ? 'checked' : '';
            return `<div class="linked-calendar-option border rounded-4 p-3 bg-white">
                <input class="form-check-input profile-calendar-input" type="checkbox" id="profileCalendar-${label}" value="${label}" ${checked}>
                <label class="form-check-label ms-2" for="profileCalendar-${label}"><strong>${escapeHtml(account.email)}</strong><span class="d-block small text-secondary">Google Calendar</span></label>
            </div>`;
        }).join('');
        container.querySelectorAll('.profile-calendar-input').forEach((input) => {
            input.addEventListener('change', () => {
                profileLinkedCalendarLabels = Array.from(container.querySelectorAll('.profile-calendar-input'))
                    .filter((checkbox) => checkbox.checked)
                    .map((checkbox) => checkbox.value);
                if ($('profileLinkedCalendar')) $('profileLinkedCalendar').value = profileLinkedCalendarLabels[0] || '';
            });
        });
    }

    async function loadProfile() {
        if (!$('profileDisplayName') && !$('presetList') && !$('timePresetSelect')) return;
        const res = await fetch('/api/profile');
        if (!res.ok) return;
        const profile = await res.json();
        profilePresets = profile.time_presets || [];
        profileLinkedCalendarLabels = profile.linked_calendar_labels || (profile.linked_calendar_label ? [profile.linked_calendar_label] : []);
        if ($('profileDisplayName')) $('profileDisplayName').value = profile.display_name || '';
        if ($('profilePhone')) $('profilePhone').value = profile.phone_number || '';
        if ($('profileTimezone')) $('profileTimezone').value = profile.timezone_preference || Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
        if ($('profileLinkedCalendar')) $('profileLinkedCalendar').value = profileLinkedCalendarLabels[0] || '';
        if ($('profileLinkedCalendarList')) loadAccounts().catch(() => { });
        renderPresetList();
        renderRequestPresetControls(profilePresets);
    }

    function presetWindowTemplate(presetIndex, windowIndex, window = {}) {
        const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        const selectedDay = Number.isInteger(Number(window.day)) ? Number(window.day) : 0;
        const dayOptions = dayNames.map((name, day) => `<option value="${day}" ${selectedDay === day ? 'selected' : ''}>${name}</option>`).join('');
        const removeButton = windowIndex > 0 ? '<button class="btn btn-outline-danger btn-sm preset-window-remove" type="button" aria-label="Remove this time block">×</button>' : '<span class="badge text-bg-light">Time block</span>';
        return `<div class="preset-window border rounded-4 p-3" data-window-index="${windowIndex}">
            <div class="d-flex justify-content-between align-items-center gap-2 mb-3"><h4 class="h6 mb-0">Time block ${windowIndex + 1}</h4>${removeButton}</div>
            <div class="row g-3">
                <div class="col-md-4"><label class="form-label small" for="presetDay-${presetIndex}-${windowIndex}">Day</label><select id="presetDay-${presetIndex}-${windowIndex}" class="form-select preset-window-day">${dayOptions}</select></div>
                <div class="col-md-4"><label class="form-label small" for="presetStart-${presetIndex}-${windowIndex}">From</label><input id="presetStart-${presetIndex}-${windowIndex}" type="time" class="form-control preset-window-start" value="${escapeHtml(window.start || '09:00')}"></div>
                <div class="col-md-4"><label class="form-label small" for="presetEnd-${presetIndex}-${windowIndex}">Until</label><input id="presetEnd-${presetIndex}-${windowIndex}" type="time" class="form-control preset-window-end" value="${escapeHtml(window.end || '17:00')}"></div>
            </div>
        </div>`;
    }

    function syncPresetFromCard(card, index) {
        profilePresets[index].name = card.querySelector('.preset-name')?.value || 'Custom preset';
        profilePresets[index].windows = Array.from(card.querySelectorAll('.preset-window')).map((windowEl) => ({
            day: Number(windowEl.querySelector('.preset-window-day')?.value || 0),
            start: windowEl.querySelector('.preset-window-start')?.value || '09:00',
            end: windowEl.querySelector('.preset-window-end')?.value || '17:00',
        })).filter((window) => window.start < window.end);
        const summary = card.querySelector('.preset-summary');
        if (summary) summary.textContent = presetToText(profilePresets[index]) || 'Add at least one time block.';
    }

    function renderPresetList() {
        const list = $('presetList');
        if (!list) return;
        list.innerHTML = profilePresets.map((preset, index) => {
            const windows = (preset.windows && preset.windows.length ? preset.windows : [{ day: 0, start: '09:00', end: '17:00' }]);
            return `<div class="preset-card border rounded-4 p-3" data-index="${index}">
                <div class="d-flex justify-content-between gap-2 align-items-start">
                    <div class="flex-grow-1">
                        <label class="form-label small" for="presetName-${index}">Preset name</label>
                        <input id="presetName-${index}" class="form-control preset-name" value="${escapeHtml(preset.name)}">
                        <div class="preset-window-list d-grid gap-2 mt-3">${windows.map((window, windowIndex) => presetWindowTemplate(index, windowIndex, window)).join('')}</div>
                        <button class="btn btn-link px-0 preset-window-add" type="button">+ Add another time block</button>
                        <p class="small text-secondary mt-2 mb-0 preset-summary">${escapeHtml(presetToText(preset) || 'Add at least one time block.')}</p>
                    </div>
                    <div class="btn-group-vertical">
                        <button class="btn btn-outline-secondary btn-sm preset-up" type="button">↑</button>
                        <button class="btn btn-outline-secondary btn-sm preset-down" type="button">↓</button>
                        <button class="btn btn-outline-danger btn-sm preset-remove" type="button">Remove</button>
                    </div>
                </div>
            </div>`;
        }).join('');
        list.querySelectorAll('.preset-card').forEach((card) => {
            const index = Number(card.dataset.index);
            card.querySelector('.preset-name').addEventListener('input', () => syncPresetFromCard(card, index));
            card.querySelectorAll('.preset-window-day, .preset-window-start, .preset-window-end').forEach((input) => input.addEventListener('change', () => syncPresetFromCard(card, index)));
            card.querySelectorAll('.preset-window-remove').forEach((button) => button.addEventListener('click', () => { button.closest('.preset-window')?.remove(); syncPresetFromCard(card, index); renderPresetList(); }));
            card.querySelector('.preset-window-add').addEventListener('click', () => { syncPresetFromCard(card, index); profilePresets[index].windows.push({ day: 5, start: '10:00', end: '18:00' }); renderPresetList(); });
            card.querySelector('.preset-up').addEventListener('click', () => { syncPresetFromCard(card, index); if (index > 0) { [profilePresets[index - 1], profilePresets[index]] = [profilePresets[index], profilePresets[index - 1]]; renderPresetList(); } });
            card.querySelector('.preset-down').addEventListener('click', () => { syncPresetFromCard(card, index); if (index < profilePresets.length - 1) { [profilePresets[index + 1], profilePresets[index]] = [profilePresets[index], profilePresets[index + 1]]; renderPresetList(); } });
            card.querySelector('.preset-remove').addEventListener('click', () => { profilePresets.splice(index, 1); renderPresetList(); });
        });
    }

    async function saveProfile() {
        const status = $('profileStatus');
        if (status) status.textContent = 'Saving profile…';
        document.querySelectorAll('.preset-card').forEach((card) => syncPresetFromCard(card, Number(card.dataset.index)));
        profileLinkedCalendarLabels = Array.from(document.querySelectorAll('.profile-calendar-input'))
            .filter((input) => input.checked)
            .map((input) => input.value);
        const payload = {
            display_name: $('profileDisplayName')?.value || '',
            phone_number: $('profilePhone')?.value || '',
            timezone_preference: $('profileTimezone')?.value || 'UTC',
            linked_calendar_label: profileLinkedCalendarLabels[0] || null,
            linked_calendar_labels: profileLinkedCalendarLabels,
            time_presets: profilePresets,
        };
        const res = await fetch('/api/profile', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        if (status) {
            status.className = res.ok ? 'small mt-3 text-success' : 'small mt-3 text-danger';
            status.textContent = res.ok ? 'Profile saved.' : 'Could not save profile.';
        }
        if (res.ok) await loadProfile();
    }

    function addPreset() {
        profilePresets.push({ id: `custom-${Date.now()}`, name: 'Custom preset', windows: [{ day: 0, start: '09:00', end: '17:00' }] });
        renderPresetList();
    }

    async function loadFriends() {
        const list = $('friendList');
        const requestFriendList = $('requestFriendList');
        if (!list && !requestFriendList) return;
        if (!currentUser) {
            await loadCurrentUser().catch(() => null);
        }
        const res = await fetch('/api/friends');
        if (!res.ok) return;
        const friends = await res.json();
        if (requestFriendList) {
            const accepted = friends.filter((friend) => friend.status === 'accepted');
            requestFriendList.innerHTML = accepted.length ? accepted.map((friend) => {
                const ownEmail = currentUser?.email || '';
                const email = friend.requester_email === ownEmail ? friend.recipient_email : friend.requester_email;
                return `<label class="form-check"><input class="form-check-input request-friend-input" type="checkbox" value="${escapeHtml(email)}"> <span class="form-check-label">${escapeHtml(email)}</span></label>`;
            }).join('') : '<p class="small text-secondary mb-0">No accepted friends yet.</p>';
        }
        if (!list && requestFriendList) return;
        if (!friends.length) {
            list.innerHTML = '<div class="empty-state"><h2 class="h4">No friends yet</h2><p class="text-secondary">Send a request by email to start building your friend list.</p></div>';
            return;
        }
        const ownEmail = currentUser?.email || '';
        list.innerHTML = friends.map((friend) => {
            const isReceiver = friend.recipient_email === ownEmail;
            const otherPerson = friend.requester_email === ownEmail ? friend.recipient_email : friend.requester_email;
            const statusText = friend.status === 'pending' ? (isReceiver ? 'Waiting for your answer' : 'Invitation sent') : 'Friends';
            return `<div class="card rounded-4 shadow-sm position-relative"><button class="btn btn-sm btn-light border delete-card-btn delete-friend" data-id="${friend.id}" type="button" aria-label="Delete friend request">×</button><div class="card-body p-4 pe-5">
                <div class="d-flex justify-content-between gap-3"><div><h2 class="h5">${escapeHtml(otherPerson)}</h2><p class="mb-0 text-secondary">${escapeHtml(statusText)}</p></div><span class="badge text-bg-secondary align-self-start">${escapeHtml(friend.status)}</span></div>
                ${friend.status === 'pending' && isReceiver ? `<button class="btn btn-outline-primary mt-3 accept-friend" data-id="${friend.id}" type="button">Accept friend request</button>` : ''}
            </div></div>`;
        }).join('');
        list.querySelectorAll('.accept-friend').forEach((button) => button.addEventListener('click', () => acceptFriend(button.dataset.id)));
        list.querySelectorAll('.delete-friend').forEach((button) => button.addEventListener('click', () => deleteFriendRequest(button.dataset.id)));
    }

    async function sendFriendRequest() {
        const status = $('friendStatus');
        if (status) status.textContent = 'Sending friend request…';
        const res = await fetch('/api/friends', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ recipient_email: $('friendEmail')?.value || '' }) });
        const data = await res.json().catch(() => ({}));
        if (status) {
            status.className = res.ok ? 'small mt-3 text-success' : 'small mt-3 text-danger';
            status.textContent = res.ok ? 'Friend request sent.' : (data.detail || 'Could not send request.');
        }
        if (res.ok) loadFriends();
    }

    async function acceptFriend(id) {
        await fetch(`/api/friends/${encodeURIComponent(id)}/accept`, { method: 'POST' });
        loadFriends();
    }

    async function deleteFriendRequest(id) {
        if (!window.confirm('Delete this friend request?')) return;
        await fetch(`/api/friends/${encodeURIComponent(id)}`, { method: 'DELETE' });
        loadFriends();
    }

    async function acceptVisibleRequest(requestId) {
        const res = await fetch(`/api/requests/${encodeURIComponent(requestId)}/accept`, { method: 'POST' });
        if (!res.ok) alert('Could not accept this request. Open the invite link from the sender if this keeps happening.');
        loadRequests();
    }

    async function deleteMeetingRequest(requestId) {
        if (!window.confirm('Delete this meeting request?')) return;
        await fetch(`/api/requests/${encodeURIComponent(requestId)}`, { method: 'DELETE' });
        loadRequests();
    }

    function renderRequestPresetControls(presets) {
        const select = $('timePresetSelect');
        if (!select) return;
        select.innerHTML = (presets || []).map((preset) => `<option value="${escapeHtml(preset.id)}">${escapeHtml(preset.name)}</option>`).join('');
        const quick = $('timePresetQuickButtons');
        if (quick) {
            quick.innerHTML = (presets || []).slice(0, 3).map((preset) => `<button class="btn btn-outline-primary preset-quick" data-id="${escapeHtml(preset.id)}" type="button">${escapeHtml(preset.name)}</button>`).join('');
            quick.querySelectorAll('.preset-quick').forEach((button) => button.addEventListener('click', () => { if (select) select.value = button.dataset.id; applyPreset(button.dataset.id); quick.querySelectorAll('.preset-quick').forEach((btn) => btn.classList.toggle('active', btn === button)); }));
        }
        select.addEventListener('change', () => applyPreset(select.value));
    }

    function applyPreset(id) {
        const preset = profilePresets.find((item) => item.id === id);
        if (!preset || !(preset.windows || []).length) return;
        setAvailabilityWindows(preset.windows);
    }

    async function setDemoConnector(label, account) {
        const status = $(`demoConnectorStatus${label}`);
        const button = $(`demoConnect${label}`);
        const connected = Boolean(account);
        if (status) {
            status.textContent = connected ? 'Google connected' : 'Not connected';
            status.className = connected ? 'badge text-bg-success align-self-start' : 'badge text-bg-secondary align-self-start';
        }
        if (button) button.textContent = connected ? `Reconnect Google calendar ${label}` : `Connect Google calendar ${label}`;
        const busyEl = $(`demoBusy${label}`);
        if (busyEl && !connected) {
            busyEl.textContent = 'Connect this Google calendar to include its availability.';
        }
        if (busyEl && connected) {
            busyEl.textContent = `${account.email} is connected. Availability will be checked when you run matching.`;
        }
    }

    async function loadDemoConnectors() {
        const results = $('demoResults');
        try {
            const user = await loadCurrentUser();
            if (!user) return { a: null, b: null };
            const res = await fetch('/accounts');
            if (!res.ok) throw new Error('Could not load connected Google calendars');
            const accounts = await res.json();
            const byLabel = Object.fromEntries((accounts || []).map((account) => [String(account.account_label || '').toLowerCase(), account]));
            await setDemoConnector('A', byLabel.a);
            await setDemoConnector('B', byLabel.b);
            return { a: byLabel.a || null, b: byLabel.b || null };
        } catch (error) {
            await setDemoConnector('A', null);
            await setDemoConnector('B', null);
            if (results) results.innerHTML = `<div class="alert alert-warning">${escapeHtml(error.message || 'Could not load demo calendar connections.')}</div>`;
            return { a: null, b: null };
        }
    }

    async function runDemoMatching() {
        const results = $('demoResults');
        if (!results) return;
        const accounts = await loadDemoConnectors();
        if (!accounts.a || !accounts.b) {
            results.innerHTML = '<div class="alert alert-info">Connect both Google calendars above to run demo matching with real free/busy data.</div>';
            return;
        }
        const date = $('demoDate')?.value || new Date().toISOString().slice(0, 10);
        const timeMin = `${date}T00:00:00Z`;
        const timeMax = `${date}T23:59:59Z`;
        const day = (new Date(`${date}T00:00:00Z`).getUTCDay() + 6) % 7;
        const payload = {
            time_min: timeMin,
            time_max: timeMax,
            duration_minutes: Number($('demoDuration')?.value || 30),
            allowed_windows: [{ day, start: $('demoWindowStart')?.value || '09:00', end: $('demoWindowEnd')?.value || '18:00' }],
            max_options: 3,
        };
        results.innerHTML = '<div class="alert alert-secondary">Loading Google free/busy data and calculating options…</div>';
        const [busyARes, busyBRes, optionsRes] = await Promise.all([
            fetch(`/freebusy/a?time_min=${encodeURIComponent(timeMin)}&time_max=${encodeURIComponent(timeMax)}`),
            fetch(`/freebusy/b?time_min=${encodeURIComponent(timeMin)}&time_max=${encodeURIComponent(timeMax)}`),
            fetch('/matching/options', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }),
        ]);
        const busyA = await busyARes.json().catch(() => ({}));
        const busyB = await busyBRes.json().catch(() => ({}));
        const data = await optionsRes.json().catch(() => ({}));
        if ($('demoBusyA')) $('demoBusyA').textContent = `${busyA.email || accounts.a.email}: ${(busyA.busy || []).length} busy block(s) found.`;
        if ($('demoBusyB')) $('demoBusyB').textContent = `${busyB.email || accounts.b.email}: ${(busyB.busy || []).length} busy block(s) found.`;
        if (!optionsRes.ok) { results.innerHTML = `<div class="alert alert-danger">${escapeHtml(data.detail || 'Demo matching failed')}</div>`; return; }
        if (!(data.options || []).length) { results.innerHTML = '<div class="alert alert-warning">No shared options found for this date and time window.</div>'; return; }
        results.innerHTML = (data.options || []).map((slot, index) => `<div class="col-md-4"><div class="card option-card h-100"><div class="card-body"><span class="badge ${index === 0 ? 'text-bg-success' : 'text-bg-light'}">Option ${index + 1}</span><h2 class="h5 mt-3">${escapeHtml(new Date(slot.start).toLocaleString())}</h2><p>${escapeHtml(new Date(slot.end).toLocaleTimeString())}</p><p class="small text-secondary">${escapeHtml(slot.reason)}</p></div></div></div>`).join('');
    }

    function initAuthCallbackBanner() {
        const params = new URLSearchParams(window.location.search);
        const accountLabel = params.get("account_label");
        const email = params.get("email");

        if (accountLabel && email) {
            showEmail(accountLabel, email);
            loadAccounts().catch(() => { });
            history.replaceState(null, "", window.location.pathname);
        }
    }

    function collectRequestPayload() {
        const weekdays = Array.from(new Set(Array.from(document.querySelectorAll("#timeWindowsContainer .weekday-input"))
            .filter((input) => input.checked)
            .map((input) => input.dataset.day)));
        const manualEmails = ($("inviteeEmail")?.value || "").split(",").map((email) => email.trim()).filter(Boolean);
        const friendEmails = Array.from(document.querySelectorAll(".request-friend-input"))
            .filter((input) => input.checked)
            .map((input) => input.value);
        const inviteeEmails = Array.from(new Set([...manualEmails, ...friendEmails]));
        return {
            title: $("requestTitle")?.value || "Meeting request",
            invitee_email: inviteeEmails[0] || "",
            invitee_emails: inviteeEmails,
            friend_ids: friendEmails,
            time_preset_id: $("timePresetSelect")?.value || null,
            owner_calendar_label: $("requestOwnerCalendar")?.value || null,
            duration_minutes: Number($("durationMinutes")?.value || 30),
            earliest_date: $("earliestDate")?.value || "",
            latest_date: $("latestDate")?.value || "",
            timezone: $("timezone")?.value || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
            window_start: $("windowStart")?.value || "09:00",
            window_end: $("windowEnd")?.value || "17:00",
            allowed_weekdays: weekdays,
            allowed_windows: convertPrefsArray(getPrefsFromTable()),
            notes: $("requestNotes")?.value || "",
        };
    }

    async function saveRequestDraft() {
        const status = $("requestSaveStatus");
        if (status) status.textContent = "Saving request draft…";

        const res = await fetch("/api/requests", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(collectRequestPayload()),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            if (status) {
                status.className = "small mt-2 text-danger";
                status.textContent = data.detail || "Could not save this request.";
            }
            return;
        }
        if (status) {
            status.className = "small mt-2 text-success";
            status.innerHTML = `Saved. <a href="/requests/${data.id}">Open request</a> · <a href="${data.invite_url}">Invite link</a>`;
        }
    }

    async function generateInviteLink(requestId) {
        const output = $(`inviteLink-${requestId}`);
        if (output) output.textContent = "Creating invite link…";
        const res = await fetch(`/api/requests/${encodeURIComponent(requestId)}/invite`, { method: "POST" });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            if (output) {
                output.className = "small text-danger d-block mt-2";
                output.textContent = data.detail || "Could not create invite link.";
            }
            return;
        }
        const absoluteUrl = `${window.location.origin}${data.invite_url}`;
        if (output) {
            output.className = "small text-success d-block mt-2";
            output.innerHTML = `<a href="${data.invite_url}">${absoluteUrl}</a>`;
        }
    }

    function requestStatusLabel(status) {
        const labels = {
            draft: 'Draft', sent: 'Invitation sent', opened: 'Opened', awaiting_calendar_connection: 'Waiting for calendar', ready_for_matching: 'Ready to find times', disagreed: 'Declined', cancelled: 'Cancelled', expired: 'Expired'
        };
        return labels[status] || status;
    }

    function renderRequestList(requests) {
        const list = $("requestList");
        if (!list) return;
        if (!requests || requests.length === 0) {
            list.innerHTML = `<div class="empty-state text-center"><h2 class="h4">No requests yet</h2><p class="text-secondary">Create your first meeting request and invite someone to share availability.</p><a class="btn btn-primary" href="/requests/new">Create request</a></div>`;
            return;
        }
        const ownEmail = currentUser?.email || '';
        list.innerHTML = `<h2 class="h5 mb-3">Your requests</h2>` + requests.map((req) => {
            const invitees = req.invitee_emails && req.invitee_emails.length ? req.invitee_emails : [req.invitee_email];
            const isInvitee = invitees.includes(ownEmail);
            const canAccept = isInvitee && !req.invite_accepted_at && !req.invite_declined_at && !['cancelled', 'expired', 'disagreed'].includes(req.status);
            const calendarLabel = req.owner_calendar_label || req.invitee_calendar_label || '';
            return `<div class="request-card card shadow-sm rounded-4 mb-3 position-relative">
                <button class="btn btn-sm btn-light border delete-card-btn delete-request" data-request-id="${req.id}" type="button" aria-label="Delete request">×</button>
                <div class="card-body p-4 pe-5">
                    <div class="d-flex justify-content-between gap-3">
                        <div><h3 class="h5">${escapeHtml(req.title)}</h3><p class="text-secondary mb-2">With ${escapeHtml(invitees.join(', '))} · ${escapeHtml(req.earliest_date)}–${escapeHtml(req.latest_date)} · ${escapeHtml(req.duration_minutes)} minutes</p></div>
                        <span class="badge text-bg-secondary align-self-start">${escapeHtml(requestStatusLabel(req.status))}</span>
                    </div>
                    <p class="mb-3">Preferred times: ${escapeHtml(presetToText({ windows: req.allowed_windows }) || ((req.allowed_weekdays || []).join(', ') || 'Any day'))}.</p>
                    ${calendarLabel ? `<p class="small text-secondary mb-3">Calendar selected for this request.</p>` : `<p class="small text-secondary mb-3">Choose or connect a calendar when you open this request.</p>`}
                    <a class="btn btn-outline-primary" href="/requests/${req.id}">Open request</a>
                    ${canAccept ? `<button class="btn btn-primary ms-2 accept-request" type="button" data-request-id="${req.id}">Accept request</button>` : ''}
                    ${!isInvitee ? `<button class="btn btn-outline-secondary ms-2 invite-link-btn" type="button" data-request-id="${req.id}">Create invite link</button>` : ''}
                    <span id="inviteLink-${req.id}" class="small text-secondary d-block mt-2"></span>
                </div>
            </div>`;
        }).join("");
        list.querySelectorAll(".invite-link-btn").forEach((button) => {
            button.addEventListener("click", () => generateInviteLink(button.dataset.requestId));
        });
        list.querySelectorAll(".accept-request").forEach((button) => {
            button.addEventListener("click", () => acceptVisibleRequest(button.dataset.requestId));
        });
        list.querySelectorAll(".delete-request").forEach((button) => {
            button.addEventListener("click", () => deleteMeetingRequest(button.dataset.requestId));
        });
    }

    async function loadRequests() {
        const list = $("requestList");
        if (!list) return;
        const res = await fetch("/api/requests");
        if (res.status === 401) {
            if (requiresAuth) window.location.replace("/login");
            return;
        }
        if (!res.ok) return;
        renderRequestList(await res.json());
    }

    function inviteTokenFromPath() {
        const parts = window.location.pathname.split("/");
        return parts[1] === "invite" ? parts[2] : "";
    }

    function setInviteStatus(message, isError = false) {
        const status = $("inviteStatus");
        if (!status) return;
        status.textContent = message;
        status.className = isError ? "small text-danger mb-3" : "small text-secondary mb-3";
    }

    async function loadInvitePreview() {
        const token = inviteTokenFromPath();
        if (!token || !$('inviteTitle')) return;
        const res = await fetch(`/api/invites/${encodeURIComponent(token)}`);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            setInviteStatus(data.detail || "This invite link is unavailable.", true);
            return;
        }
        currentInviteRequestId = data.request_id;
        setInviteStatus(`Invite expires ${new Date(data.expires_at).toLocaleString()}.`);
        setText("inviteTitle", data.title);
        setText("inviteSummary", `${data.requester_email} wants to find a shared ${data.duration_minutes}-minute meeting.`);
        setText("inviteRequester", data.requester_email);
        setText("inviteInvitee", data.invitee_email);
        setText("inviteDuration", `${data.duration_minutes} minutes`);
        setText("inviteDates", `${data.earliest_date}–${data.latest_date}`);
        setText("inviteWindow", `${(data.allowed_weekdays || []).join(", ") || "Any day"} · ${data.window_start}–${data.window_end} ${data.timezone}`);
        setText("inviteRequestStatus", data.status);
        if (window.location.search.includes("accepted=1") || data.status === "awaiting_calendar_connection") {
            showInviteCalendarPanel();
        }
    }

    function showInviteCalendarPanel() {
        const panel = $("inviteCalendarPanel");
        if (panel) panel.classList.remove("d-none");
        loadAccounts().catch(() => {
            setText("inviteCalendarStatus", "Log in to load linked calendars, or connect Google Calendar after accepting.");
        });
    }

    async function selectInviteCalendar() {
        const status = $("inviteCalendarStatus");
        const calendarLabel = $("inviteCalendarSelect")?.value || "";
        if (!currentInviteRequestId) {
            if (status) status.textContent = "Accept the invite before selecting a calendar.";
            return;
        }
        if (!calendarLabel) {
            if (status) status.textContent = "Choose one linked calendar first.";
            return;
        }
        if (status) status.textContent = "Saving calendar selection…";
        const res = await fetch(`/api/requests/${encodeURIComponent(currentInviteRequestId)}/calendar`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ calendar_label: calendarLabel }),
        });
        const data = await res.json().catch(() => ({}));
        if (status) {
            status.className = res.ok ? "small text-success mt-2" : "small text-danger mt-2";
            status.textContent = res.ok ? "Calendar selected for this request." : (data.detail || "Could not select that calendar.");
        }
        if (res.ok) setText("inviteRequestStatus", data.status);
    }

    function connectInviteCalendar() {
        if (!currentInviteRequestId) {
            setText("inviteCalendarStatus", "Accept the invite before connecting a calendar.");
            return;
        }
        const calendarLabel = $("inviteCalendarSelect")?.value || "a";
        const returnTo = `${window.location.pathname}?accepted=1`;
        window.location = `/oauth/start?account_label=${encodeURIComponent(calendarLabel || "a")}&request_id=${encodeURIComponent(currentInviteRequestId)}&return_to=${encodeURIComponent(returnTo)}`;
    }

    async function respondToInvite(action) {
        const token = inviteTokenFromPath();
        const res = await fetch(`/api/invites/${encodeURIComponent(token)}/${action}`, { method: "POST" });
        const data = await res.json().catch(() => ({}));
        if (res.status === 401) {
            window.location.replace(`/login?next=${encodeURIComponent(window.location.pathname)}`);
            return;
        }
        if (!res.ok) {
            setInviteStatus(data.detail || "Could not update this invite.", true);
            return;
        }
        setInviteStatus(data.message);
        setText("inviteRequestStatus", data.status);
        if (action === "accept") window.location.href = "/profile";
    }

    async function findMatchingTimes() {
        const selectedAccountLabel = $("requestAccountSelect")?.value;
        if (accountsLoaded < 1 || !selectedAccountLabel) {
            alert("Connect a calendar account in your profile first.");
            return;
        }

        const { timeMin, timeMax } = getDateRange();
        userPrefs = convertPrefsArray(getPrefsFromTable());

        const overview = $("overview");
        if (overview) overview.innerHTML = '<div class="alert alert-info">Checking calendars and finding the best options…</div>';

        const pairUrl = `/pair?time_min=${encodeURIComponent(timeMin)}&time_max=${encodeURIComponent(timeMax)}&account_label=${encodeURIComponent(selectedAccountLabel)}`;
        const res = await fetch(pairUrl);
        if (!res.ok) {
            if (overview) overview.innerHTML = '<div class="alert alert-danger">Error fetching calendar availability. Reconnect calendars or try again.</div>';
            return;
        }

        const data = await res.json();
        busyDataA = data.account_a || { busy: [] };
        busyDataB = data.account_b || { busy: [] };
        combinedBusy = data.combined_busy || [];

        const durationMinutes = Number($("durationMinutes")?.value || 30);
        const matchRes = await fetch("/matching/options", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                time_min: timeMin,
                time_max: timeMax,
                duration_minutes: durationMinutes,
                allowed_windows: userPrefs,
                account_label: selectedAccountLabel,
                max_options: 3,
            }),
        });

        if (matchRes.ok) {
            const matchData = await matchRes.json();
            suggestedSlots = matchData.options || [];
        } else {
            suggestedSlots = [];
            let last = timeMin;
            combinedBusy
                .slice()
                .sort((x, y) => String(x.start).localeCompare(String(y.start)))
                .forEach((b) => {
                    if (b.start > last) suggestedSlots.push({ start: last, end: b.start });
                    if (b.end > last) last = b.end;
                });
            if (last < timeMax) suggestedSlots.push({ start: last, end: timeMax });
            if (userPrefs.length) suggestedSlots = suggestedSlots.filter((s) => inPref(s.start, userPrefs));
            suggestedSlots = suggestedSlots.slice(0, 3);
        }

        currentDisplayDate = new Date(timeMin);
        showCalendarA = true;
        showCalendarB = true;

        const calendarContainer = $("calendarContainer");
        if (calendarContainer) calendarContainer.style.display = "block";

        renderCalendarGrid(currentDisplayDate);
        renderSuggestedSlots();

        if (overview) {
            overview.innerHTML = `<div class="privacy-note p-3 rounded-4">We checked the connected calendars and only used free/busy availability. Private event details stay hidden.</div>`;
        }
    }

    const prevBtn = $("prevDay");
    if (prevBtn) {
        prevBtn.onclick = () => {
            if (!currentDisplayDate) return;
            currentDisplayDate.setUTCDate(currentDisplayDate.getUTCDate() - 1);
            renderCalendarGrid(currentDisplayDate);
        };
    }

    const nextBtn = $("nextDay");
    if (nextBtn) {
        nextBtn.onclick = () => {
            if (!currentDisplayDate) return;
            currentDisplayDate.setUTCDate(currentDisplayDate.getUTCDate() + 1);
            renderCalendarGrid(currentDisplayDate);
        };
    }

    const toggleA = $("toggleA");
    if (toggleA) {
        toggleA.onclick = () => {
            showCalendarA = !showCalendarA;
            if (currentDisplayDate) renderCalendarGrid(currentDisplayDate);
        };
    }

    const toggleB = $("toggleB");
    if (toggleB) {
        toggleB.onclick = () => {
            showCalendarB = !showCalendarB;
            if (currentDisplayDate) renderCalendarGrid(currentDisplayDate);
        };
    }

    const acceptInviteBtn = $("acceptInviteBtn");
    if (acceptInviteBtn) acceptInviteBtn.onclick = () => respondToInvite("accept");

    const declineInviteBtn = $("declineInviteBtn");
    if (declineInviteBtn) declineInviteBtn.onclick = () => respondToInvite("decline");

    const selectInviteCalendarBtn = $("selectInviteCalendarBtn");
    if (selectInviteCalendarBtn) selectInviteCalendarBtn.onclick = selectInviteCalendar;
    const connectInviteCalendarBtn = $("connectInviteCalendarBtn");
    if (connectInviteCalendarBtn) connectInviteCalendarBtn.onclick = connectInviteCalendar;

    const findBtn = $("findBtn");
    if (findBtn) findBtn.onclick = findMatchingTimes;

    const saveRequestBtn = $("saveRequestBtn");
    if (saveRequestBtn) saveRequestBtn.onclick = saveRequestDraft;

    const saveProfileBtn = $("saveProfileBtn");
    if (saveProfileBtn) saveProfileBtn.onclick = saveProfile;
    const addPresetBtn = $("addPresetBtn");
    if (addPresetBtn) addPresetBtn.onclick = addPreset;
    const sendFriendBtn = $("sendFriendBtn");
    if (sendFriendBtn) sendFriendBtn.onclick = sendFriendRequest;
    const profileConnectGoogle = $("profileConnectGoogle");
    if (profileConnectGoogle) {
        profileConnectGoogle.onclick = async () => {
            const user = await loadCurrentUser();
            if (!user) return alert("Log in before connecting a calendar account");
            window.location = "/oauth/start?return_to=/profile";
        };
    }
    const requestConnectGoogle = $("requestConnectGoogle");
    if (requestConnectGoogle) {
        requestConnectGoogle.onclick = async () => {
            const user = await loadCurrentUser();
            if (!user) return alert("Log in before connecting a calendar account");
            window.location = "/oauth/start?return_to=/requests/new";
        };
    }
    const requestPlatformBtn = $("requestPlatformBtn");
    if (requestPlatformBtn) {
        requestPlatformBtn.onclick = () => $("platformRequestForm")?.classList.toggle("d-none");
    }
    const platformRequestForm = $("platformRequestForm");
    if (platformRequestForm) {
        platformRequestForm.onsubmit = (event) => {
            event.preventDefault();
            setText("platformRequestStatus", "Thanks — your platform request has been recorded for product review.");
            platformRequestForm.reset();
        };
    }
    const demoConnectA = $("demoConnectA");
    if (demoConnectA) demoConnectA.onclick = async () => { const user = await loadCurrentUser(); if (!user) return alert('Log in before connecting demo calendar A'); window.location = '/oauth/start?account_label=a&return_to=/requests/demo'; };
    const demoConnectB = $("demoConnectB");
    if (demoConnectB) demoConnectB.onclick = async () => { const user = await loadCurrentUser(); if (!user) return alert('Log in before connecting demo calendar B'); window.location = '/oauth/start?account_label=b&return_to=/requests/demo'; };
    const runDemoBtn = $("runDemoBtn");
    if (runDemoBtn) runDemoBtn.onclick = runDemoMatching;
    const addTimeWindowBtn = $("addTimeWindowBtn");
    if (addTimeWindowBtn) addTimeWindowBtn.onclick = () => addAvailabilityWindow();
    const demoAddTimeWindowBtn = $("demoAddTimeWindowBtn");
    if (demoAddTimeWindowBtn) demoAddTimeWindowBtn.onclick = () => addAvailabilityWindow("demoTimeWindowsContainer", { prefix: "demoWindow" });
    const demoPresetSelect = $("demoPresetSelect");
    if (demoPresetSelect) demoPresetSelect.onchange = () => setAvailabilityWindows(demoPresets[demoPresetSelect.value]?.windows || [], "demoTimeWindowsContainer", { prefix: "demoWindow" });

    populateTimeSelects();
    setDefaultDates();
    initAuthCallbackBanner();
    loadCurrentUser().catch(() => { if (requiresAuth) window.location.replace("/login"); });
    if ($("emails") || $("requestAccountSelect") || $("profileLinkedCalendarList")) loadAccounts().catch(() => { });
    loadProfile().catch(() => { });
    loadFriends().catch(() => { });
    loadRequests().catch(() => { });
    if ($("demoTimeWindowsContainer")) setAvailabilityWindows(demoPresets.overlap.windows, "demoTimeWindowsContainer", { prefix: "demoWindow" });
    if ($("runDemoBtn")) runDemoMatching().catch(() => { });
    loadInvitePreview().catch(() => setInviteStatus("Could not load this invite.", true));
});
