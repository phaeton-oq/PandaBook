-- name: CreateConsumptionLog :one
INSERT INTO consumption_log (user_id, product_id, day, meal_type, grams)
VALUES (?, ?, ?, ?, ?)
RETURNING *;

-- name: ListConsumptionByUser :many
SELECT cl.*, p.*
FROM consumption_log cl
JOIN products p ON p.id = cl.product_id
WHERE cl.user_id = ?
ORDER BY cl.day DESC;

-- name: ListConsumptionByUserAndDateRange :many
SELECT cl.*, p.*
FROM consumption_log cl
JOIN products p ON p.id = cl.product_id
WHERE cl.user_id = ? AND cl.day >= ? AND cl.day <= ?
ORDER BY cl.day;
