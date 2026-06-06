// frontend behavior for Calendar Matching
document.addEventListener("DOMContentLoaded", () => {
    // State variables for calendar
    let currentDisplayDate = null;
    let busyDataA = { busy: [] };
    let busyDataB = { busy: [] };
    let combinedBusy = [];
    let suggestedSlots = [];
    let userPrefs = [];
    let showCalendarA = true;
    let showCalendarB = true;

    // -----------------------------
    // Utilities
    // -----------------------------
    function $(id) {
        return document.getElementById(id);
    }

    function ensureSuggestedContainer() {
        // Renders suggested slots outside the grid (so we don't wipe the calendar)
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

    // -----------------------------
    // Health indicator
    // -----------------------------
    function updateHealth() {
        fetch("/api/health")
            .then((r) => r.json())
            .then((d) => {
                const el = $("health");
                if (el) el.style.background = d.status === "healthy" ? "green" : "red";
            })
            .catch(() => {
                const el = $("health");
                if (el) el.style.background = "red";
            });
    }
    setInterval(updateHealth, 5000);
    updateHealth();

    function setSessionUi(user) {
        const status = $("sessionStatus");
        const form = $("authForm");
        const logout = $("logoutBtn");
        if (user) {
            if (status) status.textContent = `Logged in as ${user.email}`;
            if (form) form.style.display = "none";
            if (logout) logout.style.display = "inline-block";
        } else {
            if (status) status.textContent = "Log in or register before connecting calendars.";
            if (form) form.style.display = "block";
            if (logout) logout.style.display = "none";
        }
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

    async function submitAuth(mode) {
        const email = $("authEmail")?.value || "";
        const password = $("authPassword")?.value || "";
        const displayName = $("authDisplayName")?.value || "";
        const body = { email, password };
        if (mode === "register") body.display_name = displayName;

        const res = await fetch(`/auth/${mode}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const error = await res.json().catch(() => ({}));
            alert(error.detail || "Authentication failed");
            return;
        }
        const data = await res.json();
        setSessionUi(data.user);
        await loadAccounts();
    }

    const loginBtn = $("loginBtn");
    if (loginBtn) loginBtn.onclick = () => submitAuth("login");

    const registerBtn = $("registerBtn");
    if (registerBtn) registerBtn.onclick = () => submitAuth("register");

    const logoutBtn = $("logoutBtn");
    if (logoutBtn) {
        logoutBtn.onclick = async () => {
            await fetch("/auth/logout", { method: "POST" });
            setSessionUi(null);
            accountsLoaded = 0;
        };
    }

    function showEmail(label, email) {
        const container = $("emails");
        if (!container) return;
        const p = document.createElement("p");
        p.textContent = `${String(label).toUpperCase()} logged in: ${email}`;
        container.appendChild(p);
    }

    // -----------------------------
    // Preferences UI
    // -----------------------------
    function populateTimeSelects() {
        const table = $("prefsTable");
        if (!table) return;

        const selects = table.querySelectorAll("select");
        selects.forEach((sel) => {
            // prevent duplicate options if called twice
            if (sel.options && sel.options.length > 0) return;

            for (let h = 0; h < 24; h++) {
                const hh = String(h).padStart(2, "0");
                const opt = document.createElement("option");
                opt.value = hh; // hour-only, convert later
                opt.textContent = hh;
                sel.appendChild(opt);
            }
        });
    }

    function getPrefsFromTable() {
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

            // convert hour-only value to hh:00 for comparison
            prefs.push({ day, start: `${startSel.value}:00`, end: `${endSel.value}:00` });
        });
        return prefs;
    }

    function convertPrefsArray(arr) {
        const days = { Mon: 0, Tue: 1, Wed: 2, Thu: 3, Fri: 4, Sat: 5, Sun: 6 };
        return (arr || [])
            .map((p) => ({
                day: days[p.day],
                start: p.start,
                end: p.end,
            }))
            .filter((p) => Number.isInteger(p.day) && p.start && p.end);
    }

    function inPref(isoDateTime, prefs) {
        const d = new Date(isoDateTime);
        const weekday = d.getUTCDay();
        const time = d.toISOString().slice(11, 16); // HH:MM
        return prefs.some((p) => p.day === weekday && time >= p.start && time < p.end);
    }

    // -----------------------------
    // Busy checks
    // -----------------------------
    function isBusy(dateStr, busyData) {
        const busyArr = (busyData && busyData.busy) || [];
        return busyArr.some((b) => {
            if (!b?.start || !b?.end) return false;

            // Handle zero-duration events (start === end)
            if (b.start === b.end) return dateStr === b.start;

            // ISO string compare works if all are UTC ISO strings
            return dateStr >= b.start && dateStr < b.end;
        });
    }

    function isSuggested(dateStr) {
        const isBusyCombined = (combinedBusy || []).some((b) => dateStr >= b.start && dateStr < b.end);
        const inPrefTime = userPrefs.length === 0 || inPref(dateStr, userPrefs);
        return !isBusyCombined && inPrefTime;
    }

    // -----------------------------
    // Rendering
    // -----------------------------
    function renderSuggestedSlots() {
        const el = ensureSuggestedContainer();

        let html = "<h3>Top suggested meeting times (next 7 days)</h3>";
        if (!suggestedSlots || suggestedSlots.length === 0) {
            html += "<div class='suggestedItem'>No suggested slots found.</div>";
            el.innerHTML = html;
            return;
        }

        suggestedSlots.slice(0, 10).forEach((slot) => {
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
            html += `<div class="suggestedItem">${startDate} → ${endTime}</div>`;
        });

        el.innerHTML = html;
    }

    function renderCalendarGrid(displayDate) {
        const container = $("calendarGrid");
        if (!container) return;
        container.innerHTML = "";

        const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
        const dayName = dayNames[displayDate.getUTCDay()];
        const dateStr = displayDate.toISOString().split("T")[0];

        const currentDateEl = $("currentDate");
        if (currentDateEl) currentDateEl.textContent = `${dateStr} (${dayName})`;

        // Dynamic grid columns
        let gridCols = "60px"; // Time column
        if (showCalendarA) gridCols += " 1fr";
        if (showCalendarB) gridCols += " 1fr";
        gridCols += " 1fr"; // Available
        container.style.gridTemplateColumns = gridCols;

        // Header row
        const headerTime = document.createElement("div");
        headerTime.className = "timeColumnHeader";
        headerTime.textContent = "Time";
        container.appendChild(headerTime);

        if (showCalendarA) {
            const headerA = document.createElement("div");
            headerA.className = "dayColumnHeader";
            headerA.textContent = "Account A";
            container.appendChild(headerA);
        }

        if (showCalendarB) {
            const headerB = document.createElement("div");
            headerB.className = "dayColumnHeader";
            headerB.textContent = "Account B";
            container.appendChild(headerB);
        }

        const headerAvail = document.createElement("div");
        headerAvail.className = "dayColumnHeader";
        headerAvail.textContent = "Available";
        container.appendChild(headerAvail);

        // 30-minute slots
        for (let hour = 0; hour < 24; hour++) {
            for (let min = 0; min < 60; min += 30) {
                const hh = String(hour).padStart(2, "0");
                const mm = String(min).padStart(2, "0");
                const timeStr = `${hh}:${mm}`;
                const slotDateTime = `${dateStr}T${timeStr}:00Z`;

                // Time label
                const timeCell = document.createElement("div");
                timeCell.className = "timeSlot timeLabel";
                timeCell.textContent = timeStr;
                container.appendChild(timeCell);

                // Account A
                if (showCalendarA) {
                    const slotA = document.createElement("div");
                    slotA.className = "timeSlot";
                    if (isBusy(slotDateTime, busyDataA)) {
                        slotA.classList.add("busyA");
                        slotA.textContent = "Busy";
                    }
                    container.appendChild(slotA);
                }

                // Account B
                if (showCalendarB) {
                    const slotB = document.createElement("div");
                    slotB.className = "timeSlot";
                    if (isBusy(slotDateTime, busyDataB)) {
                        slotB.classList.add("busyB");
                        slotB.textContent = "Busy";
                    }
                    container.appendChild(slotB);
                }

                // Available/Suggested
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

    // -----------------------------
    // Navigation handlers
    // -----------------------------
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

    // -----------------------------
    // Accounts
    // -----------------------------
    let accountsLoaded = 0;

    async function loadAccounts() {
        const res = await fetch("/accounts");
        if (res.status === 401) {
            setSessionUi(null);
            return;
        }
        if (!res.ok) return;

        const list = await res.json();
        const selA = $("selectA");
        const selB = $("selectB");
        if (!selA || !selB) return;

        // Prevent duplicates if called again
        selA.innerHTML = "";
        selB.innerHTML = "";

        list.forEach((acc) => {
            const optA = document.createElement("option");
            optA.value = acc.account_label;
            optA.textContent = acc.email;
            selA.appendChild(optA);

            const optB = optA.cloneNode(true);
            selB.appendChild(optB);

            if (acc.cached_busy) {
                console.log(`cached busy for ${acc.account_label}:`, acc.cached_busy);
            }
        });

        accountsLoaded = list.length;

        // Save selection
        [selA, selB].forEach((sel) => {
            sel.onchange = () => {
                const params = new URLSearchParams({
                    account_label: sel.value,
                    selected_as: sel === selA ? "a" : "b",
                });
                fetch(`/accounts/select?${params.toString()}`, {
                    method: "POST",
                }).catch(() => { });
            };
        });
    }

    // -----------------------------
    // One-time init & handlers
    // -----------------------------
    function initAuthCallbackBanner() {
        const params = new URLSearchParams(window.location.search);
        const accountLabel = params.get("account_label");
        const email = params.get("email");

        if (accountLabel && email) {
            showEmail(accountLabel, email);
            // Just refresh accounts list once (do not recurse init)
            loadAccounts().catch(() => { });
            history.replaceState(null, "", window.location.pathname);
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

    // Toggle columns (A/B) and re-render
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
    if (findBtn) {
        findBtn.onclick = async () => {
            if (accountsLoaded < 2) {
                alert("Both calendars must be connected first");
                return;
            }

            const now = new Date();
            const later = new Date(now.getTime() + 7 * 24 * 3600 * 1000);

            const nowISO = now.toISOString();
            const laterISO = later.toISOString();

            const rawPrefs = getPrefsFromTable();
            userPrefs = convertPrefsArray(rawPrefs);

            const res = await fetch(
                `/pair?time_min=${encodeURIComponent(nowISO)}&time_max=${encodeURIComponent(laterISO)}`
            );

            if (!res.ok) {
                const overview = $("overview");
                if (overview) overview.textContent = "Error fetching data";
                return;
            }

            const data = await res.json();
            busyDataA = data.account_a || { busy: [] };
            busyDataB = data.account_b || { busy: [] };
            combinedBusy = data.combined_busy || [];

            const durationSelect = $("durationMinutes");
            const durationMinutes = durationSelect ? Number(durationSelect.value) : 30;
            const matchRes = await fetch("/matching/options", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    time_min: nowISO,
                    time_max: laterISO,
                    duration_minutes: durationMinutes,
                    allowed_windows: userPrefs,
                    max_options: 3,
                }),
            });

            if (matchRes.ok) {
                const matchData = await matchRes.json();
                suggestedSlots = matchData.options || [];
            } else {
                // Fallback to client-side free gaps if the matching endpoint is unavailable.
                suggestedSlots = [];
                let last = nowISO;

                combinedBusy
                    .slice()
                    .sort((x, y) => String(x.start).localeCompare(String(y.start)))
                    .forEach((b) => {
                        if (b.start > last) suggestedSlots.push({ start: last, end: b.start });
                        if (b.end > last) last = b.end;
                    });

                if (last < laterISO) suggestedSlots.push({ start: last, end: laterISO });

                if (userPrefs.length) {
                    suggestedSlots = suggestedSlots.filter((s) => inPref(s.start, userPrefs));
                }
            }

            // Initialize calendar display
            currentDisplayDate = new Date(now);
            showCalendarA = true;
            showCalendarB = true;

            const calendarContainer = $("calendarContainer");
            if (calendarContainer) calendarContainer.style.display = "block";

            renderCalendarGrid(currentDisplayDate);
            renderSuggestedSlots();

            // Raw data for reference
            const overview = $("overview");
            if (overview) {
                let rawHtml = "<h2>Raw API Response Data</h2>";
                rawHtml += "<details><summary>Click to expand raw data</summary>";
                rawHtml += `<h3>Account A (${data?.account_a?.email || "unknown"})</h3>`;
                rawHtml += `<pre>${JSON.stringify(data?.account_a?.busy || [], null, 2)}</pre>`;
                rawHtml += `<h3>Account B (${data?.account_b?.email || "unknown"})</h3>`;
                rawHtml += `<pre>${JSON.stringify(data?.account_b?.busy || [], null, 2)}</pre>`;
                rawHtml += "<h3>Combined Busy Periods</h3>";
                rawHtml += `<pre>${JSON.stringify(data?.combined_busy || [], null, 2)}</pre>`;
                rawHtml += "</details>";
                overview.innerHTML = rawHtml;
            }
        };
    }

    // -----------------------------
    // Boot
    // -----------------------------
    populateTimeSelects();
    initAuthCallbackBanner();
    loadCurrentUser()
        .then((user) => {
            if (user) return loadAccounts();
            return null;
        })
        .catch(() => setSessionUi(null));
});
