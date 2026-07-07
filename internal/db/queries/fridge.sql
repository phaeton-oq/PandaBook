-- name: ListFridgeItems :many
SELECT fi.*, p.*
FROM fridge_items fi
JOIN products p ON p.id = fi.product_id
WHERE fi.user_id = ?
ORDER BY fi.id;

-- name: GetFridgeItemByID :one
SELECT fi.*, p.*
FROM fridge_items fi
JOIN products p ON p.id = fi.product_id
WHERE fi.id = ? AND fi.user_id = ?;

-- name: CreateFridgeItem :one
INSERT INTO fridge_items (user_id, product_id, quantity_g, expiry_date)
VALUES (?, ?, ?, ?)
RETURNING *;

-- name: UpdateFridgeItem :one
UPDATE fridge_items
SET quantity_g = ?1, expiry_date = ?2
WHERE id = ?3 AND user_id = ?4
RETURNING *;

-- name: DeleteFridgeItem :exec
DELETE FROM fridge_items WHERE id = ? AND user_id = ?;
