// Frontend behavior for the Calendar Matching prototype UI.
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
                <li class="nav-item"><a class="nav-link" href="/account">Account</a></li>
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
        p.textContent = `${String(label).toUpperCase()} connected: ${email}`;
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

    function getPrefsFromTable() {
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
            .map((p) => ({ day: days[p.day], start: p.start, end: p.end }))
            .filter((p) => Number.isInteger(p.day) && p.start && p.end && p.start < p.end);
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
                            <p class="small text-secondary">UTC / browser display placeholder</p>
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

        const accountA = list.find((acc) => acc.account_label === "a");
        const accountB = list.find((acc) => acc.account_label === "b");
        if (accountA) {
            setText("emailA", accountA.email);
            setBadge("statusA", "Connected", "text-bg-success");
        }
        if (accountB) {
            setText("emailB", accountB.email);
            setBadge("statusB", "Connected", "text-bg-success");
        }

        const selA = $("selectA");
        const selB = $("selectB");
        if (!selA || !selB) return;

        selA.innerHTML = "";
        selB.innerHTML = "";
        if (list.length === 0) {
            selA.innerHTML = '<option value="a">Connect account A first</option>';
            selB.innerHTML = '<option value="b">Connect account B first</option>';
            return;
        }

        list.forEach((acc) => {
            const optA = document.createElement("option");
            optA.value = acc.account_label;
            optA.textContent = acc.email;
            selA.appendChild(optA);

            const optB = optA.cloneNode(true);
            selB.appendChild(optB);
        });

        if (accountA) selA.value = "a";
        if (accountB) selB.value = "b";
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
            container.innerHTML = `<div class="border rounded-4 p-3 bg-white"><p class="mb-2 fw-semibold">No calendars connected yet.</p><p class="small text-secondary mb-0">Use the connector buttons below to add Google calendar slots to this profile.</p></div>`;
            return;
        }
        container.innerHTML = accounts.map((account) => {
            const label = escapeHtml(account.account_label);
            const checked = profileLinkedCalendarLabels.includes(account.account_label) ? 'checked' : '';
            return `<div class="linked-calendar-option border rounded-4 p-3 bg-white">
                <input class="form-check-input profile-calendar-input" type="checkbox" id="profileCalendar-${label}" value="${label}" ${checked}>
                <label class="form-check-label ms-2" for="profileCalendar-${label}"><strong>${escapeHtml(account.email)}</strong><span class="d-block small text-secondary">Google Calendar slot ${label.toUpperCase()}</span></label>
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

    function selectedWindowDays(preset) {
        return new Set((preset.windows || []).map((window) => Number(window.day)));
    }

    function firstPresetWindow(preset) {
        return (preset.windows || [])[0] || { day: 0, start: '09:00', end: '17:00' };
    }

    function syncPresetFromCard(card, index) {
        const start = card.querySelector('.preset-start')?.value || '09:00';
        const end = card.querySelector('.preset-end')?.value || '17:00';
        const days = Array.from(card.querySelectorAll('.preset-day-input'))
            .filter((input) => input.checked)
            .map((input) => Number(input.value));
        profilePresets[index].windows = days.map((day) => ({ day, start, end }));
        const summary = card.querySelector('.preset-summary');
        if (summary) summary.textContent = presetToText(profilePresets[index]) || 'Select at least one day.';
    }

    function renderPresetList() {
        const list = $('presetList');
        if (!list) return;
        const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        list.innerHTML = profilePresets.map((preset, index) => {
            const selectedDays = selectedWindowDays(preset);
            const firstWindow = firstPresetWindow(preset);
            const dayButtons = dayNames.map((name, day) => `
                <input class="btn-check preset-day-input" type="checkbox" id="preset-${index}-day-${day}" value="${day}" ${selectedDays.has(day) ? 'checked' : ''}>
                <label class="btn btn-outline-primary btn-sm" for="preset-${index}-day-${day}">${name}</label>`).join('');
            return `<div class="preset-card border rounded-4 p-3" data-index="${index}">
                <div class="d-flex justify-content-between gap-2 align-items-start">
                    <div class="flex-grow-1">
                        <label class="form-label small" for="presetName-${index}">Preset name</label>
                        <input id="presetName-${index}" class="form-control preset-name" value="${escapeHtml(preset.name)}">
                        <label class="form-label small mt-3">Selectable days</label>
                        <div class="weekday-selector preset-weekday-selector mb-3" role="group" aria-label="Preset weekdays">${dayButtons}</div>
                        <div class="row g-3">
                            <div class="col-sm-6"><label class="form-label small" for="presetStart-${index}">Between</label><input id="presetStart-${index}" type="time" class="form-control preset-start" value="${escapeHtml(firstWindow.start)}"></div>
                            <div class="col-sm-6"><label class="form-label small" for="presetEnd-${index}">And</label><input id="presetEnd-${index}" type="time" class="form-control preset-end" value="${escapeHtml(firstWindow.end)}"></div>
                        </div>
                        <p class="small text-secondary mt-2 mb-0 preset-summary">${escapeHtml(presetToText(preset) || 'Select at least one day.')}</p>
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
            card.querySelector('.preset-name').addEventListener('input', (event) => { profilePresets[index].name = event.target.value; });
            card.querySelectorAll('.preset-day-input, .preset-start, .preset-end').forEach((input) => input.addEventListener('change', () => syncPresetFromCard(card, index)));
            card.querySelector('.preset-up').addEventListener('click', () => { if (index > 0) { [profilePresets[index - 1], profilePresets[index]] = [profilePresets[index], profilePresets[index - 1]]; renderPresetList(); } });
            card.querySelector('.preset-down').addEventListener('click', () => { if (index < profilePresets.length - 1) { [profilePresets[index + 1], profilePresets[index]] = [profilePresets[index], profilePresets[index + 1]]; renderPresetList(); } });
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
        list.innerHTML = friends.map((friend) => `
            <div class="card rounded-4 shadow-sm"><div class="card-body p-4">
                <div class="d-flex justify-content-between gap-3"><div><h2 class="h5">${escapeHtml(friend.requester_email)} → ${escapeHtml(friend.recipient_email)}</h2><p class="mb-0 text-secondary">Status: ${escapeHtml(friend.status)}</p></div><span class="badge text-bg-secondary align-self-start">${escapeHtml(friend.status)}</span></div>
                ${friend.status === 'pending' ? `<button class="btn btn-outline-primary mt-3 accept-friend" data-id="${friend.id}" type="button">Accept if this is for you</button>` : ''}
            </div></div>`).join('');
        list.querySelectorAll('.accept-friend').forEach((button) => button.addEventListener('click', () => acceptFriend(button.dataset.id)));
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
        document.querySelectorAll('.weekday-input').forEach((input) => { input.checked = false; });
        const first = preset.windows[0];
        if ($('windowStart')) $('windowStart').value = first.start;
        if ($('windowEnd')) $('windowEnd').value = first.end === '23:59' ? '23:59' : first.end;
        const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
        preset.windows.forEach((window) => {
            const checkbox = document.querySelector(`.weekday-input[data-day="${dayNames[window.day]}"]`);
            if (checkbox) checkbox.checked = true;
        });
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
            busyEl.textContent = 'Connect this Google calendar to load its free/busy registry.';
        }
        if (busyEl && connected) {
            busyEl.textContent = JSON.stringify({ connector: `Google Calendar ${label}`, email: account.email, busy: [] }, null, 2);
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
        if ($('demoBusyA')) $('demoBusyA').textContent = JSON.stringify({ connector: 'Google Calendar A', email: busyA.email || accounts.a.email, busy: busyA.busy || [] }, null, 2);
        if ($('demoBusyB')) $('demoBusyB').textContent = JSON.stringify({ connector: 'Google Calendar B', email: busyB.email || accounts.b.email, busy: busyB.busy || [] }, null, 2);
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
        const weekdays = Array.from(document.querySelectorAll(".weekday-input"))
            .filter((input) => input.checked)
            .map((input) => input.dataset.day);
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
            duration_minutes: Number($("durationMinutes")?.value || 30),
            earliest_date: $("earliestDate")?.value || "",
            latest_date: $("latestDate")?.value || "",
            timezone: $("timezone")?.value || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
            window_start: $("windowStart")?.value || "09:00",
            window_end: $("windowEnd")?.value || "17:00",
            allowed_weekdays: weekdays,
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
            status.innerHTML = `Saved in SQLite. <a href="/requests/${data.id}">Open request</a> · <a href="${data.invite_url}">Invite link</a>`;
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

    function renderRequestList(requests) {
        const list = $("requestList");
        if (!list) return;
        if (!requests || requests.length === 0) {
            list.innerHTML = `<div class="empty-state text-center"><h2 class="h4">No requests yet</h2><p class="text-secondary">Create your first SQLite-backed request draft, then connect calendars and find options.</p><a class="btn btn-primary" href="/requests/new">Create request</a></div>`;
            return;
        }
        list.innerHTML = `<h2 class="h5 mb-3">Saved requests</h2>` + requests.map((req) => `
            <div class="request-card card shadow-sm rounded-4 mb-3">
                <div class="card-body p-4">
                    <div class="d-flex justify-content-between gap-3">
                        <div><h3 class="h5">${escapeHtml(req.title)}</h3><p class="text-secondary mb-2">With ${escapeHtml(req.invitee_email)} · ${escapeHtml(req.earliest_date)}–${escapeHtml(req.latest_date)} · ${escapeHtml(req.duration_minutes)} minutes</p></div>
                        <span class="badge text-bg-secondary align-self-start">${escapeHtml(req.status)}</span>
                    </div>
                    <p class="mb-3">Allowed ${escapeHtml((req.allowed_weekdays || []).join(", ") || "all days")} between ${escapeHtml(req.window_start)} and ${escapeHtml(req.window_end)}.</p>
                    <a class="btn btn-outline-primary" href="/requests/${req.id}">Open request</a>
                    <button class="btn btn-outline-secondary ms-2 invite-link-btn" type="button" data-request-id="${req.id}">Create invite link</button>
                    <span id="inviteLink-${req.id}" class="small text-secondary d-block mt-2"></span>
                </div>
            </div>`).join("");
        list.querySelectorAll(".invite-link-btn").forEach((button) => {
            button.addEventListener("click", () => generateInviteLink(button.dataset.requestId));
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
        setInviteStatus(`Invite expires ${new Date(data.expires_at).toLocaleString()}.`);
        setText("inviteTitle", data.title);
        setText("inviteSummary", `${data.requester_email} wants to find a shared ${data.duration_minutes}-minute meeting.`);
        setText("inviteRequester", data.requester_email);
        setText("inviteInvitee", data.invitee_email);
        setText("inviteDuration", `${data.duration_minutes} minutes`);
        setText("inviteDates", `${data.earliest_date}–${data.latest_date}`);
        setText("inviteWindow", `${(data.allowed_weekdays || []).join(", ") || "Any day"} · ${data.window_start}–${data.window_end} ${data.timezone}`);
        setText("inviteRequestStatus", data.status);
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
        if (action === "accept") window.location.href = "/account";
    }

    async function findMatchingTimes() {
        if (accountsLoaded < 2) {
            alert("Both calendars must be connected first. Use the Account page to connect Google Calendar slots A and B.");
            return;
        }

        const { timeMin, timeMax } = getDateRange();
        userPrefs = convertPrefsArray(getPrefsFromTable());

        const overview = $("overview");
        if (overview) overview.innerHTML = '<div class="alert alert-info">Checking calendars and finding the best options…</div>';

        const res = await fetch(`/pair?time_min=${encodeURIComponent(timeMin)}&time_max=${encodeURIComponent(timeMax)}`);
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
            overview.innerHTML = `
                <details>
                    <summary class="fw-semibold">Developer/debug response data</summary>
                    <h3 class="h6 mt-3">Requester (${escapeHtml(data?.account_a?.email || "unknown")})</h3>
                    <pre>${escapeHtml(JSON.stringify(data?.account_a?.busy || [], null, 2))}</pre>
                    <h3 class="h6">Invitee (${escapeHtml(data?.account_b?.email || "unknown")})</h3>
                    <pre>${escapeHtml(JSON.stringify(data?.account_b?.busy || [], null, 2))}</pre>
                    <h3 class="h6">Combined busy periods</h3>
                    <pre>${escapeHtml(JSON.stringify(data?.combined_busy || [], null, 2))}</pre>
                </details>`;
        }
    }

    const authA = $("authA");
    if (authA) {
        authA.onclick = async () => {
            const user = await loadCurrentUser();
            if (!user) return alert("Log in before connecting calendar A");
            window.location = "/oauth/start?account_label=a";
        };
    }

    const authB = $("authB");
    if (authB) {
        authB.onclick = async () => {
            const user = await loadCurrentUser();
            if (!user) return alert("Log in before connecting calendar B");
            window.location = "/oauth/start?account_label=b";
        };
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
    const profileConnectA = $("profileConnectA");
    if (profileConnectA) profileConnectA.onclick = async () => { const user = await loadCurrentUser(); if (!user) return alert("Log in before connecting calendar A"); window.location = "/oauth/start?account_label=a"; };
    const profileConnectB = $("profileConnectB");
    if (profileConnectB) profileConnectB.onclick = async () => { const user = await loadCurrentUser(); if (!user) return alert("Log in before connecting calendar B"); window.location = "/oauth/start?account_label=b"; };
    const demoConnectA = $("demoConnectA");
    if (demoConnectA) demoConnectA.onclick = async () => { const user = await loadCurrentUser(); if (!user) return alert('Log in before connecting demo calendar A'); window.location = '/oauth/start?account_label=a&return_to=/requests/demo'; };
    const demoConnectB = $("demoConnectB");
    if (demoConnectB) demoConnectB.onclick = async () => { const user = await loadCurrentUser(); if (!user) return alert('Log in before connecting demo calendar B'); window.location = '/oauth/start?account_label=b&return_to=/requests/demo'; };
    const runDemoBtn = $("runDemoBtn");
    if (runDemoBtn) runDemoBtn.onclick = runDemoMatching;

    populateTimeSelects();
    setDefaultDates();
    initAuthCallbackBanner();
    loadCurrentUser().catch(() => { if (requiresAuth) window.location.replace("/login"); });
    if ($("emails") || $("selectA") || $("statusA")) loadAccounts().catch(() => { });
    loadProfile().catch(() => { });
    loadFriends().catch(() => { });
    loadRequests().catch(() => { });
    if ($("runDemoBtn")) { loadDemoConnectors(); runDemoMatching().catch(() => { }); }
    loadInvitePreview().catch(() => setInviteStatus("Could not load this invite.", true));
});
