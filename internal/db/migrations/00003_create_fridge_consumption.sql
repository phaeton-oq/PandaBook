-- +goose Up
CREATE TABLE IF NOT EXISTS fridge_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity_g REAL NOT NULL DEFAULT 0,
    expiry_date DATE
);

CREATE INDEX IF NOT EXISTS idx_fridge_user ON fridge_items(user_id);

CREATE TABLE IF NOT EXISTS consumption_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    day DATE NOT NULL,
    meal_type TEXT NOT NULL DEFAULT 'snack',
    grams REAL NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_consumption_user ON consumption_log(user_id);

-- +goose Down
DROP TABLE IF EXISTS consumption_log;
DROP TABLE IF EXISTS fridge_items;
