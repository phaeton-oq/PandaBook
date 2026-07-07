-- +goose Up
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL DEFAULT '',
    sex TEXT NOT NULL DEFAULT 'male',
    age INTEGER NOT NULL DEFAULT 30,
    weight_kg REAL NOT NULL DEFAULT 70,
    height_cm REAL NOT NULL DEFAULT 175,
    activity TEXT NOT NULL DEFAULT 'moderate',
    goal TEXT NOT NULL DEFAULT 'maintain',
    prefs_csv TEXT NOT NULL DEFAULT ''
);

-- +goose Down
DROP TABLE IF EXISTS users;
