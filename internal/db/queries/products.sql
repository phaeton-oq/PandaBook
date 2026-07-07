-- name: ListProducts :many
SELECT * FROM products ORDER BY name;

-- name: SearchProducts :many
SELECT * FROM products WHERE name LIKE ? ORDER BY name;

-- name: GetProductByID :one
SELECT * FROM products WHERE id = ?;

-- name: GetProductByName :one
SELECT * FROM products WHERE name = ?;

-- name: GetProductByBarcode :one
SELECT * FROM products WHERE off_barcode = ?;

-- name: CreateProduct :one
INSERT INTO products (name, category, kcal_100, protein_100, fat_100, carbs_100, tags_csv, off_barcode)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
RETURNING *;

-- name: GetProductCount :one
SELECT COUNT(*) FROM products;
