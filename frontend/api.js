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
  const headers = { "Content-Type": "application/json", Accept: "application/json" };
  if (Auth.token) headers.Authorization = "Bearer " + Auth.token;
  const res = await fetch(API_BASE + path, {
    method,
    headers,
    cache: "no-store",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return null;
  if (res.status === 304) throw { status: 304, data: "Кэш устарел — обновите страницу" };
  const text = await res.text();
  if (!text) throw { status: res.status, data: "Пустой ответ сервера" };
  let data;
  try { data = JSON.parse(text); } catch { data = text; }
  if (!res.ok) throw { status: res.status, data };
  return data;
}

function requireAuth() {
  if (!Auth.token) { location.href = "index.html"; return false; }
  return true;
}

function logout() { Auth.clear(); location.href = "index.html"; }

const ACTIVITY = ["sedentary", "light", "moderate", "active", "very_active"];
const activityToApi = (num) => ACTIVITY[Number(num) - 1] || "moderate";
const activityToNum = (name) => String(ACTIVITY.indexOf(name) + 1 || 3);

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

/** Remove duplicates when merging local catalog + OFF (same name/barcode/id). */
function dedupeProducts(list) {
  const seen = new Set();
  return list.filter((p) => {
    const key = p.id != null ? `id:${p.id}`
      : p.off_barcode ? `bc:${p.off_barcode}`
      : `name:${p.name.trim().toLowerCase()}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/** Suggested portion in grams when picking a product — user can edit before save. */
function defaultGrams(product) {
  const cat = (product.category || "").toLowerCase();
  const name = (product.name || "").toLowerCase();
  if (cat.includes("fat") || name.includes("масл")) return 30;
  if (cat.includes("egg") || name.includes("яйц")) return 100;
  if (cat.includes("fruit") || name.includes("фрукт")) return 150;
  if (cat.includes("veg") || name.includes("овощ")) return 200;
  if (cat.includes("meat") || cat.includes("fish") || name.includes("филе")) return 300;
  if (cat.includes("dairy") || name.includes("творог") || name.includes("йогурт")) return 200;
  if (cat.includes("grain") || name.includes("рис") || name.includes("овсян")) return 150;
  if (cat.includes("legume")) return 200;
  return 250;
}

function fillProductForm(product) {
  document.getElementById("prodName").value = product.name;
  document.getElementById("prodWeight").value = defaultGrams(product);
  const today = new Date();
  today.setDate(today.getDate() + 5);
  document.getElementById("prodExpiry").value = today.toISOString().split("T")[0];
}
