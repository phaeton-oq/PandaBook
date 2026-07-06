/** Shared UI: toasts, email validation, sidebar logout. */

function toast(message, type = "info") {
  let host = document.getElementById("toast-host");
  if (!host) {
    host = document.createElement("div");
    host.id = "toast-host";
    document.body.appendChild(host);
  }
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = message;
  host.appendChild(el);
  requestAnimationFrame(() => el.classList.add("show"));
  setTimeout(() => {
    el.classList.remove("show");
    setTimeout(() => el.remove(), 300);
  }, 3500);
}

function isValidEmail(email) {
  const e = email.trim().toLowerCase();
  if (e.length < 3 || e.length > 254 || !e.includes("@")) return false;
  const [local, domain] = e.split("@");
  return Boolean(local && domain && domain.includes("."));
}

function injectLogout() {
  const ul = document.querySelector(".menu-links");
  if (!ul || ul.querySelector(".menu-logout")) return;
  const li = document.createElement("li");
  li.innerHTML = '<a href="#" class="menu-item menu-logout">Выйти</a>';
  li.querySelector("a").addEventListener("click", (e) => {
    e.preventDefault();
    logout();
  });
  ul.appendChild(li);
}

const PAGE_LABELS = {
  "dashboard.html": "Главный экран",
  "fridge.html": "Холодильник",
  "shopping.html": "Список докупок",
  "profile.html": "Профиль",
  "landing.html": "Главная",
};

function currentPageName() {
  const path = location.pathname.split("/").pop();
  return path || "dashboard.html";
}

function safeFromPage(from) {
  if (!from || !/^[\w-]+\.html$/i.test(from)) return null;
  return from;
}

/** Internal link that remembers where the user came from. */
function pageHref(path) {
  const target = path.split("?")[0];
  const from = encodeURIComponent(currentPageName());
  const sep = path.includes("?") ? "&" : "?";
  return `${path}${sep}from=${from}`;
}

function backLabel(from) {
  return "← " + (PAGE_LABELS[from] || "Назад");
}

function initBackButton(id = "backBtn") {
  const el = document.getElementById(id);
  if (!el) return;

  const from = safeFromPage(new URLSearchParams(location.search).get("from"));
  if (!from) return;

  el.href = from;
  el.textContent = backLabel(from);
  el.hidden = false;
}

function wireFromLinks() {
  document.querySelectorAll("a.nav-from-current").forEach((a) => {
    const raw = a.getAttribute("href");
    if (raw) a.href = pageHref(raw);
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (typeof Auth !== "undefined" && Auth.token) injectLogout();
  wireFromLinks();
  initBackButton();
});
