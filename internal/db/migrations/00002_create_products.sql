-- +goose Up
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'other',
    kcal_100 REAL NOT NULL DEFAULT 0,
    protein_100 REAL NOT NULL DEFAULT 0,
    fat_100 REAL NOT NULL DEFAULT 0,
    carbs_100 REAL NOT NULL DEFAULT 0,
    tags_csv TEXT NOT NULL DEFAULT '',
    off_barcode TEXT
);

CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);

-- +goose Down
DROP TABLE IF EXISTS products;
