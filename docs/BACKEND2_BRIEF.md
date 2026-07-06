# Бриф для Backend-2 — PandaBook

Привет! Каркас бэка готов и запушен. Твои задачи ниже. Контракт заморожен,
зоны не пересекаются — работаем параллельно без конфликтов.

## Старт
```bash
git clone https://github.com/phaeton-oq/PandaBook
cd PandaBook
git checkout feat/backend-core        # база
git checkout -b feat/backend-api       # твоя ветка от неё
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://127.0.0.1:8000
pytest                                 # 5/5 должно проходить
```

## Правила
- **Не трогай:** `app/core/`, `app/db/models.py`, `app/schemas/` (контракт заморожен).
- **Твоё:** `app/api/routes_fridge.py`, `app/api/routes_auth.py`, `app/integrations/off.py`.
- Все точки входа помечены `TODO(Backend-2)` прямо в файлах.
- Переиспользуй готовое: `app/db/converters.py` (`fridge_to_schema`, `product_to_schema`,
  `parse_prefs`), `app/db/session.py` (`get_db`), модели в `app/db/models.py`.
- LLM (`llm.py`) уже сделан нами — **не трогай**.

## Задачи

### 1. Auth + профиль — `app/api/routes_auth.py`
Модель `models.User` уже есть (email, имя, поля профиля, `prefs_csv`).
- `POST /api/auth/register` — создать юзера (email, name, профиль).
- `POST /api/auth/login` — выдать сессию/JWT (для хакатона можно упростить).
- `GET  /api/auth/me` — вернуть профиль как `schemas.UserProfile`
  (поля User → UserProfile 1:1; для prefs — `converters.parse_prefs(user.prefs_csv)`).
- Профиль нужен движку: из него считаются цели (`core.nutrition.compute_targets`).

### 2. Fridge CRUD — `app/api/routes_fridge.py`
Модель `models.FridgeItem` (user_id, product_id, quantity_g, expiry_date).
- `GET    /api/fridge?user_id=` — список; ответ через `converters.fridge_to_schema`.
- `POST   /api/fridge` — добавить (product_id ИЛИ найти/создать продукт по названию
  через OFF, + quantity_g, expiry_date).
- `PATCH  /api/fridge/{item_id}` — изменить количество/срок.
- `DELETE /api/fridge/{item_id}` — удалить.
- Эти данные фронт потом шлёт в `POST /api/diet/plan` (см. `docs/API.md`).

### 3. Open Food Facts — `app/integrations/off.py`
Сайт (не приложение): поиск по НАЗВАНИЮ.
- Эндпоинт без ключа:
  `https://world.openfoodfacts.org/cgi/search.pl?search_terms=<q>&json=1&page_size=10`
- Маппинг nutriments → `schemas.Product`:
  `energy-kcal_100g → kcal_100`, `proteins_100g → protein_100`,
  `fat_100g → fat_100`, `carbohydrates_100g → carbs_100`, `product_name → name`.
- Используй `httpx` (уже в зависимостях). Верни `list[Product]`.
- Подключи к `POST /api/fridge` (поиск при добавлении по названию).

## Контракт и справка
- Схемы: `app/schemas/__init__.py` (UserProfile, Product, FridgeItem, ...).
- Формат ответов движка: `docs/API.md`.
- Вопросы по границам зон — пиши, но схему не меняем без общего согласия.
