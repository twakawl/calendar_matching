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
            window.location.replace("/login");
            return;
        }

        const menuName = $("userMenuName");
        if (menuName) menuName.textContent = userDisplayName(user);
    }

    async function loadCurrentUser() {
        const res = await fetch("/auth/me");
        if (!res.ok) {
            setSessionUi(null);
            return null;
        }
        const user = await res.json();
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
            window.location.replace("/login");
            return;
        }
        if (!res.ok) return;

        const list = await res.json();
        accountsLoaded = list.length;

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

    const findBtn = $("findBtn");
    if (findBtn) findBtn.onclick = findMatchingTimes;

    populateTimeSelects();
    setDefaultDates();
    initAuthCallbackBanner();
    loadAccounts().catch(() => { });
});
