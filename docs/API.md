# API контракт для фронта — PandaBook

База: сервер на `http://127.0.0.1:8000`. Все ответы — JSON, UTF-8.
Готовые эндпоинты движка (Backend-1) ниже. Fridge/Auth — зона Backend-2 (в работе).

---

## `GET /api/diet/demo`
Готовый пример рациона на сид-данных. **Ничего не принимает.** Отдаёт тот же
объект, что и `/plan` в режиме `fast`. Удобно верстать экран рациона прямо сейчас.

## `POST /api/diet/plan`
Основной эндпоинт. Профиль + холодильник → рацион, список докупок, (в Pro) рецепт и объяснение.

### Запрос
```jsonc
{
  "mode": "fast",              // "fast" (бесплатно) | "thinking" (Pro). По умолчанию "fast"
  "request": "хочу побольше белка",  // необязательно, учитывается только в "thinking"
  "profile": {
    "sex": "male",             // "male" | "female"
    "age": 25,
    "weight_kg": 78,
    "height_cm": 182,
    "activity": "moderate",    // sedentary | light | moderate | active | very_active
    "goal": "lose",            // lose | maintain | gain
    "prefs": {                 // все поля необязательны, по умолчанию false/[]
      "vegan": false,
      "vegetarian": false,
      "halal": false,
      "gluten_free": false,
      "lactose_free": false,
      "allergens": []          // список тегов-исключений, напр. ["nuts","fish"]
    }
  },
  "fridge": [
    {
      "product": {
        "name": "Куриная грудка",
        "kcal_100": 165, "protein_100": 31, "fat_100": 3.6, "carbs_100": 0,
        "tags": ["meat"],      // meat, pork, fish, egg, dairy, gluten, nuts, honey
        "category": "meat"     // необязательно
      },
      "quantity_g": 300,
      "expiry_date": "2026-07-08"   // "YYYY-MM-DD" или null
    }
  ]
}
```

### Ответ
```jsonc
{
  "mode": "fast",
  "targets": {                 // дневная норма (цель)
    "kcal": 2229, "protein_g": 156, "fat_g": 67, "carbs_g": 251
  },
  "plan": {
    "day": "2026-07-06",
    "targets": { "kcal": 2229, "protein_g": 156, "fat_g": 67, "carbs_g": 251 },
    "totals": {                // фактически собрано из холодильника
      "kcal": 1440, "protein_g": 117, "fat_g": 20, "carbs_g": 190
    },
    "coverage_pct": 64.6,      // % покрытия нормы по калориям (0..100)
    "notes": [                 // строки-предупреждения, могут быть пустыми
      "В рацион включены продукты с истекающим сроком годности."
    ],
    "meals": [
      {
        "type": "breakfast",   // breakfast | lunch | dinner | snack
        "kcal": 556.2, "protein": 98.0, "fat": 11.5, "carbs": 12.6,
        "items": [
          {
            "product_name": "Куриная грудка",
            "grams": 300.0,
            "kcal": 495.0, "protein": 93.0, "fat": 10.8, "carbs": 0.0,
            "expiring_soon": true   // true → рисуем бейдж "⏳ скоро истекает"
          }
        ]
      }
    ]
  },
  "shopping_list": [           // может быть пустым []
    {
      "product_name": "Куриная грудка",
      "grams": 200,
      "reason": "покрывает нехватку белка (~40 г)"
    }
  ],

  // Заполнены ТОЛЬКО при mode="thinking", иначе null:
  "explanation": null,         // строка: почему такой рацион (2-3 предложения)
  "recipe": null               // объект Recipe (ниже) или null
}
```

**В режиме `thinking`** те же поля + заполнены:
```jsonc
{
  "mode": "thinking",
  "explanation": "Ваш план даёт ~1440 ккал — дефицит помогает снижать вес...",
  "recipe": {
    "title": "Куриная грудка с рисом и брокколи",
    "ingredients": ["куриная грудка 300 г", "рис 200 г", "брокколи"],
    "steps": ["Промыть рис...", "Обжарить курицу...", "..."]
  }
}
```

> ⚠️ `thinking` дёргает ИИ PandaBook → ответ ~3 сек. Показывайте лоадер «🧠 думает…».
> `fast` — мгновенный, без ИИ.

## Авторизация (Backend-2)

### `POST /api/auth/register`
```jsonc
// запрос
{ "email": "user@mail.com", "password": "min8chars", "name": "Имя", "profile": { /* UserProfile, см. выше */ } }
// ответ
{ "access_token": "…", "token_type": "bearer" }   // 201; 409 если email занят
```
### `POST /api/auth/login`
```jsonc
{ "email": "user@mail.com", "password": "…" }      // → access_token; 401 при неверных
```
### `GET /api/auth/me` 🔒
`Authorization: Bearer <token>` → `{ id, email, name, profile }`.

Токен клади в заголовок `Authorization: Bearer <token>` для всех 🔒-ручек.
**Демо-юзер:** `demo@pandabook.local` / `demo12345`.

---

## `GET /api/products` — каталог для пикера
Список известных продуктов (для сетки/дропдауна быстрого выбора в холодильник).
- `?q=молоко` — необязательный фильтр по названию (регистронезависимо).
```jsonc
[
  { "id": 1, "name": "Куриная грудка", "category": "meat",
    "kcal_100": 165, "protein_100": 31, "fat_100": 3.6, "carbs_100": 0,
    "tags": ["meat"], "off_barcode": null }
]
```
Берёшь `id` продукта → шлёшь в `POST /api/fridge` как `product_id`.

## `GET /api/products/search?q=nutella&limit=10` — автокомплит
Живой поиск в Open Food Facts. Возвращает несколько кандидатов с КБЖУ — юзер
выбирает нужный. Формат элемента = тот же `Product` (у внешних `id: null`,
но есть `off_barcode`). Добавление в холодильник — по `name` или `off_barcode`.
> ⚠️ Внешний API: первый запрос может быть медленным. Показывай лоадер.

## `GET /api/diet/plan/me` — план из сохранённого холодильника 🔒
Требует авторизации (`Authorization: Bearer <token>`). Берёт **профиль и
холодильник залогиненного юзера** и сразу отдаёт план — фронту не нужно
вручную собирать `fridge` для `/plan`.
- `?mode=fast|thinking` (по умолчанию `fast`), `?request=...` (пожелание для thinking).
- Ответ — тот же `PlanResponse`, что у `POST /api/diet/plan`.

## `POST /api/diet/recipe`
Отдельная генерация рецепта (если нужно вне плана).
```jsonc
// запрос
{ "ingredients": ["куриная грудка", "рис", "брокколи"] }
// ответ = объект Recipe
{ "title": "...", "ingredients": ["..."], "steps": ["..."] }
```

---

## `GET /api/progress/dashboard`
История КБЖУ по дням + стрик + настроение панды (геймификация).
**Auth-aware:** с заголовком `Authorization: Bearer <token>` — данные залогиненного
юзера; **без токена** — демо-юзер с готовой историей (для наполненного демо).
```jsonc
{
  "targets": { "kcal": 2229, "protein_g": 156, "fat_g": 67, "carbs_g": 251 },
  "days": [
    { "day": "2026-07-06", "kcal": 2193, "protein_g": 120, "fat_g": 55,
      "carbs_g": 210, "goal_met": true }
  ],
  "streak": 3,                 // дней подряд «в цель» — для счётчика/огонька
  "panda_emoji": "🐼✨",        // рисуем маскота
  "panda_label": "Панда в восторге — так держать!"
}
```
Для графиков бери массив `days` (КБЖУ по дням). Панда: `panda_emoji` + `panda_label`.

## `POST /api/progress/log`
Отметить съеденный продукт (обновляет дашборд). Пишет в юзера из токена
(или в демо-юзера без токена).
```jsonc
// запрос (+ опционально Authorization: Bearer <token>)
{ "product_id": 1, "grams": 200, "meal_type": "lunch" }
// ответ
{ "ok": true }
```

---

## Подсказки по UI
- Кольца/бары КБЖУ: `plan.totals` из `plan.targets` (или общий `targets`).
- Процент готовности дня — `plan.coverage_pct`.
- Бейдж «Pro / 🧠» — когда `mode === "thinking"`; блоки `explanation` и `recipe`
  показывать только если они не `null`.
- Бейдж срока годности — на `item.expiring_soon === true`.
