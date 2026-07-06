// PandaBook frontend ↔ backend glue.
// Same-origin when served by our Flask; falls back to localhost:8000 for
// file:// or a separate dev server (Live Server). CORS is enabled backend-side.
const API_BASE =
  location.protocol === "file:" || ["5500", "5501", "5173", "3000"].includes(location.port)
    ? "http://127.0.0.1:8000"
    : "";

const Auth = {
  get token() { return localStorage.getItem("panda_token"); },
  set token(t) { t ? localStorage.setItem("panda_token", t) : localStorage.removeItem("panda_token"); },
  clear() { localStorage.removeItem("panda_token"); },
};

async function api(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  if (Auth.token) headers.Authorization = "Bearer " + Auth.token;
  const res = await fetch(API_BASE + path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return null;
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = text; }
  if (!res.ok) throw { status: res.status, data };
  return data;
}

// Redirect to login if not authenticated. Call at the top of protected pages.
function requireAuth() {
  if (!Auth.token) { location.href = "index.html"; return false; }
  return true;
}

function logout() { Auth.clear(); location.href = "index.html"; }

// activity radio value (1..5) <-> API enum
const ACTIVITY = ["sedentary", "light", "moderate", "active", "very_active"];
const activityToApi = (num) => ACTIVITY[Number(num) - 1] || "moderate";
const activityToNum = (name) => String(ACTIVITY.indexOf(name) + 1 || 3);

// human-readable API errors
function apiError(e) {
  if (e && e.data) {
    if (typeof e.data === "string") return e.data;
    if (e.data.detail) {
      if (Array.isArray(e.data.detail)) return e.data.detail.map((d) => d.msg).join(", ");
      return e.data.detail;
    }
  }
  return "Ошибка сети";
}
