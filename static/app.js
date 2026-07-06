// Minimal demo wiring — frontend team replaces this with the real UI.
document.getElementById("demo").addEventListener("click", async () => {
  const out = document.getElementById("out");
  out.textContent = "Загрузка…";
  try {
    const res = await fetch("/api/diet/demo");
    out.textContent = JSON.stringify(await res.json(), null, 2);
  } catch (e) {
    out.textContent = "Ошибка: " + e;
  }
});
