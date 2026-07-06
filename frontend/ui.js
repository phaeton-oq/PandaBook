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

document.addEventListener("DOMContentLoaded", () => {
  if (typeof Auth !== "undefined" && Auth.token) injectLogout();
});
