document.addEventListener("DOMContentLoaded", () => {
    function $(id) {
        return document.getElementById(id);
    }

    const pendingRegistrationKey = "calendarMatching.pendingRegistration";

    function setStatus(message, isError = false) {
        const status = $("loginStatus");
        if (!status) return;
        status.textContent = message;
        status.className = isError ? "errorText" : "";
    }

    function displayNameFromEmail(email) {
        const localPart = String(email || "").split("@")[0].trim();
        return localPart || "";
    }

    function savePendingRegistration(email, password) {
        try {
            window.sessionStorage.setItem(
                pendingRegistrationKey,
                JSON.stringify({ email, password })
            );
        } catch {
            // Prefill is a convenience only; registration still works without storage.
        }
    }

    function loadPendingRegistration() {
        try {
            const raw = window.sessionStorage.getItem(pendingRegistrationKey);
            return raw ? JSON.parse(raw) : null;
        } catch {
            return null;
        }
    }

    function clearPendingRegistration() {
        try {
            window.sessionStorage.removeItem(pendingRegistrationKey);
        } catch {
            // Nothing to clean up when storage is unavailable.
        }
    }

    function showRegistrationPrompt(email, password) {
        const prompt = $("registrationPrompt");
        if (!prompt) return;
        savePendingRegistration(email, password);
        prompt.classList.remove("d-none");
        prompt.textContent = "";

        const strong = document.createElement("strong");
        strong.textContent = `No account exists for ${email || "that email address"}.`;
        const link = document.createElement("a");
        link.className = "alert-link";
        link.href = "/register";
        link.id = "registrationPromptLink";
        link.textContent = "Go to registration";

        prompt.append(
            strong,
            " Register first and we will carry over the email and password you entered. ",
            link,
            "."
        );
    }

    function prefillRegistrationForm() {
        const emailInput = $("authEmail");
        const passwordInput = $("authPassword");
        const displayNameInput = $("authDisplayName");
        if (!emailInput || !passwordInput || !displayNameInput) return;

        const pending = loadPendingRegistration();
        if (pending?.email && !emailInput.value) emailInput.value = pending.email;
        if (pending?.password && !passwordInput.value) passwordInput.value = pending.password;
        if (!displayNameInput.value) {
            displayNameInput.value = displayNameFromEmail(emailInput.value);
            displayNameInput.dataset.autoFilled = "true";
        }

        emailInput.addEventListener("input", () => {
            if (!displayNameInput.value || displayNameInput.dataset.autoFilled === "true") {
                displayNameInput.value = displayNameFromEmail(emailInput.value);
                displayNameInput.dataset.autoFilled = "true";
            }
        });
        displayNameInput.addEventListener("input", () => {
            displayNameInput.dataset.autoFilled = "false";
        });
    }

    function nextUrl() {
        const next = new URLSearchParams(window.location.search).get("next");
        return next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";
    }

    async function redirectIfLoggedIn() {
        const res = await fetch("/auth/me");
        if (res.ok) window.location.replace(nextUrl());
    }

    async function submitAuth(mode) {
        const email = $("authEmail")?.value || "";
        const password = $("authPassword")?.value || "";
        const displayName = $("authDisplayName")?.value || "";
        const body = { email, password };
        if (mode === "register") body.display_name = displayName;

        setStatus(mode === "register" ? "Creating account..." : "Logging in...");
        const res = await fetch(`/auth/${mode}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const error = await res.json().catch(() => ({}));
            if (mode === "login" && res.status === 404) {
                showRegistrationPrompt(email, password);
            }
            setStatus(error.detail || "Authentication failed", true);
            return;
        }
        clearPendingRegistration();
        window.location.replace(nextUrl());
    }

    $("loginBtn")?.addEventListener("click", () => submitAuth("login"));
    const registerBtn = $("registerBtn");
    if (registerBtn && registerBtn.tagName === "BUTTON") {
        registerBtn.addEventListener("click", () => submitAuth("register"));
    }
    $("authPassword")?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") submitAuth($("authDisplayName") ? "register" : "login");
    });

    prefillRegistrationForm();
    redirectIfLoggedIn().catch(() => {});
});
