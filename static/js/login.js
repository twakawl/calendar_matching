document.addEventListener("DOMContentLoaded", () => {
    function $(id) {
        return document.getElementById(id);
    }

    function setStatus(message, isError = false) {
        const status = $("loginStatus");
        if (!status) return;
        status.textContent = message;
        status.className = isError ? "errorText" : "";
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
            setStatus(error.detail || "Authentication failed", true);
            return;
        }
        window.location.replace(nextUrl());
    }

    $("loginBtn")?.addEventListener("click", () => submitAuth("login"));
    $("registerBtn")?.addEventListener("click", () => submitAuth("register"));
    $("authPassword")?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") submitAuth("login");
    });

    redirectIfLoggedIn().catch(() => {});
});
