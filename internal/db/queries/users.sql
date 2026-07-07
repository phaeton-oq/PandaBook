-- name: CreateUser :one
INSERT INTO users (email, password_hash, name, sex, age, weight_kg, height_cm, activity, goal, prefs_csv)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
RETURNING *;

-- name: GetUserByEmail :one
SELECT * FROM users WHERE email = ?;

-- name: GetUserByID :one
SELECT * FROM users WHERE id = ?;

-- name: UpdateUser :one
UPDATE users
SET name = COALESCE(?1, name),
    sex = COALESCE(?2, sex),
    age = COALESCE(?3, age),
    weight_kg = COALESCE(?4, weight_kg),
    height_cm = COALESCE(?5, height_cm),
    activity = COALESCE(?6, activity),
    goal = COALESCE(?7, goal),
    prefs_csv = COALESCE(?8, prefs_csv),
    password_hash = COALESCE(?9, password_hash)
WHERE id = ?10
RETURNING *;

-- name: GetUserCount :one
SELECT COUNT(*) FROM users;
