package repository

import (
	"context"
	"database/sql"
	"errors"
	"strings"
	"time"

	"pandabook/internal/db/storage"
	"pandabook/internal/domain"
	"pandabook/internal/errorz"
)

type UserRepo struct {
	q *storage.Queries
}

func NewUserRepo(dbtx DBTX) *UserRepo {
	return &UserRepo{q: storage.New(dbtx)}
}

func (r *UserRepo) Create(ctx context.Context, profile *domain.UserProfile, email, passwordHash, name string) (*storage.User, error) {
	user, err := r.q.CreateUser(ctx, storage.CreateUserParams{
		Email:        email,
		PasswordHash: passwordHash,
		Name:         name,
		Sex:          string(profile.Sex),
		Age:          int64(profile.Age),
		WeightKg:     profile.WeightKg,
		HeightCm:     profile.HeightCm,
		Activity:     string(profile.Activity),
		Goal:         string(profile.Goal),
		PrefsCsv:     prefsToCSV(profile.Prefs),
	})
	if err != nil {
		if strings.Contains(err.Error(), "UNIQUE") {
			return nil, errorz.ErrAlreadyExists
		}
		return nil, err
	}
	return &user, nil
}

func (r *UserRepo) GetByEmail(ctx context.Context, email string) (*storage.User, error) {
	user, err := r.q.GetUserByEmail(ctx, email)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, errorz.ErrNotFound
		}
		return nil, err
	}
	return &user, nil
}

func (r *UserRepo) GetByID(ctx context.Context, id int64) (*storage.User, error) {
	user, err := r.q.GetUserByID(ctx, id)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, errorz.ErrNotFound
		}
		return nil, err
	}
	return &user, nil
}

func (r *UserRepo) Update(ctx context.Context, id int64, name *string, profile *domain.UserProfile, passwordHash *string) (*storage.User, error) {
	user, err := r.GetByID(ctx, id)
	if err != nil {
		return nil, err
	}
	if name != nil {
		user.Name = *name
	}
	if profile != nil {
		user.Sex = string(profile.Sex)
		user.Age = int64(profile.Age)
		user.WeightKg = profile.WeightKg
		user.HeightCm = profile.HeightCm
		user.Activity = string(profile.Activity)
		user.Goal = string(profile.Goal)
		user.PrefsCsv = prefsToCSV(profile.Prefs)
	}
	if passwordHash != nil {
		user.PasswordHash = *passwordHash
	}
	updated, err := r.q.UpdateUser(ctx, storage.UpdateUserParams{
		ID:           user.ID,
		Name:         user.Name,
		Sex:          user.Sex,
		Age:          user.Age,
		WeightKg:     user.WeightKg,
		HeightCm:     user.HeightCm,
		Activity:     user.Activity,
		Goal:         user.Goal,
		PrefsCsv:     user.PrefsCsv,
		PasswordHash: user.PasswordHash,
	})
	if err != nil {
		return nil, err
	}
	return &updated, nil
}

func prefsToCSV(p domain.DietaryPrefs) string {
	var flags []string
	if p.Vegan {
		flags = append(flags, "vegan")
	}
	if p.Vegetarian {
		flags = append(flags, "vegetarian")
	}
	if p.Halal {
		flags = append(flags, "halal")
	}
	if p.GlutenFree {
		flags = append(flags, "gluten_free")
	}
	if p.LactoseFree {
		flags = append(flags, "lactose_free")
	}
	flags = append(flags, p.Allergens...)
	return strings.Join(flags, ",")
}

func userToProfile(u storage.User) domain.UserProfile {
	return domain.UserProfile{
		Sex:      domain.Sex(u.Sex),
		Age:      int(u.Age),
		WeightKg: u.WeightKg,
		HeightCm: u.HeightCm,
		Activity: domain.ActivityLevel(u.Activity),
		Goal:     domain.Goal(u.Goal),
		Prefs:    parsePrefs(u.PrefsCsv),
	}
}

func parsePrefs(csv string) domain.DietaryPrefs {
	flags := make(map[string]struct{})
	for _, f := range strings.Split(csv, ",") {
		f = strings.TrimSpace(f)
		if f != "" {
			flags[f] = struct{}{}
		}
	}
	known := map[string]bool{"vegan": true, "vegetarian": true, "halal": true, "gluten_free": true, "lactose_free": true}
	var allergens []string
	for f := range flags {
		if !known[f] {
			allergens = append(allergens, f)
		}
	}
	return domain.DietaryPrefs{
		Vegan:       has(flags, "vegan"),
		Vegetarian:  has(flags, "vegetarian"),
		Halal:       has(flags, "halal"),
		GlutenFree:  has(flags, "gluten_free"),
		LactoseFree: has(flags, "lactose_free"),
		Allergens:   allergens,
	}
}

func has(m map[string]struct{}, k string) bool {
	_, ok := m[k]
	return ok
}

type ProductRepo struct {
	q *storage.Queries
}

func NewProductRepo(dbtx DBTX) *ProductRepo {
	return &ProductRepo{q: storage.New(dbtx)}
}

func (r *ProductRepo) List(ctx context.Context, query string) ([]storage.Product, error) {
	if query != "" {
		return r.q.SearchProducts(ctx, "%"+query+"%")
	}
	return r.q.ListProducts(ctx)
}

func (r *ProductRepo) GetByID(ctx context.Context, id int64) (*storage.Product, error) {
	p, err := r.q.GetProductByID(ctx, id)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, errorz.ErrNotFound
		}
		return nil, err
	}
	return &p, nil
}

func (r *ProductRepo) GetByName(ctx context.Context, name string) (*storage.Product, error) {
	p, err := r.q.GetProductByName(ctx, name)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &p, nil
}

func (r *ProductRepo) GetByBarcode(ctx context.Context, barcode string) (*storage.Product, error) {
	p, err := r.q.GetProductByBarcode(ctx, sql.NullString{String: barcode, Valid: true})
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	return &p, nil
}

func (r *ProductRepo) Create(ctx context.Context, name, category string, kcal, protein, fat, carbs float64, tags []string, barcode *string) (*storage.Product, error) {
	var offBarcode sql.NullString
	if barcode != nil {
		offBarcode = sql.NullString{String: *barcode, Valid: true}
	}
	p, err := r.q.CreateProduct(ctx, storage.CreateProductParams{
		Name:       name,
		Category:   category,
		Kcal100:    kcal,
		Protein100: protein,
		Fat100:     fat,
		Carbs100:   carbs,
		TagsCsv:    strings.Join(tags, ","),
		OffBarcode: offBarcode,
	})
	if err != nil {
		return nil, err
	}
	return &p, nil
}

func (r *ProductRepo) Count(ctx context.Context) (int64, error) {
	return r.q.GetProductCount(ctx)
}

func productToDomain(p storage.Product) domain.Product {
	prod := domain.Product{
		ID:         p.ID,
		Name:       p.Name,
		Category:   p.Category,
		Kcal100:    p.Kcal100,
		Protein100: p.Protein100,
		Fat100:     p.Fat100,
		Carbs100:   p.Carbs100,
	}
	if p.TagsCsv != "" {
		prod.Tags = strings.Split(p.TagsCsv, ",")
	}
	if p.OffBarcode.Valid {
		prod.OffBarcode = &p.OffBarcode.String
	}
	return prod
}

type FridgeRepo struct {
	q *storage.Queries
}

func NewFridgeRepo(dbtx DBTX) *FridgeRepo {
	return &FridgeRepo{q: storage.New(dbtx)}
}

func fridgeRowToDomain(row storage.ListFridgeItemsRow) domain.FridgeItem {
	item := domain.FridgeItem{
		Product:   productToDomain(storage.Product{ID: row.ID_2, Name: row.Name, Category: row.Category, Kcal100: row.Kcal100, Protein100: row.Protein100, Fat100: row.Fat100, Carbs100: row.Carbs100, TagsCsv: row.TagsCsv, OffBarcode: row.OffBarcode}),
		QuantityG: row.QuantityG,
	}
	if row.ExpiryDate.Valid {
		item.ExpiryDate = &row.ExpiryDate.Time
	}
	return item
}

func (r *FridgeRepo) List(ctx context.Context, userID int64) ([]domain.FridgeItem, error) {
	rows, err := r.q.ListFridgeItems(ctx, userID)
	if err != nil {
		return nil, err
	}
	var items []domain.FridgeItem
	for _, row := range rows {
		items = append(items, fridgeRowToDomain(row))
	}
	if items == nil {
		items = []domain.FridgeItem{}
	}
	return items, nil
}

type ConsumeLogEntry struct {
	Day       time.Time
	ProductID int64
	Grams     float64
	Kcal100   float64
	Protein100 float64
	Fat100    float64
	Carbs100  float64
}

func (r *FridgeRepo) GetByID(ctx context.Context, itemID, userID int64) (*storage.FridgeItem, *storage.Product, error) {
	row, err := r.q.GetFridgeItemByID(ctx, storage.GetFridgeItemByIDParams{ID: itemID, UserID: userID})
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil, errorz.ErrNotFound
		}
		return nil, nil, err
	}
	fi := &storage.FridgeItem{
		ID:         row.ID,
		UserID:     row.UserID,
		ProductID:  row.ProductID,
		QuantityG:  row.QuantityG,
		ExpiryDate: row.ExpiryDate,
	}
	p := &storage.Product{
		ID:         row.ID_2,
		Name:       row.Name,
		Category:   row.Category,
		Kcal100:    row.Kcal100,
		Protein100: row.Protein100,
		Fat100:     row.Fat100,
		Carbs100:   row.Carbs100,
		TagsCsv:    row.TagsCsv,
		OffBarcode: row.OffBarcode,
	}
	return fi, p, nil
}

func (r *FridgeRepo) Create(ctx context.Context, userID, productID int64, quantityG float64, expiryDate *time.Time) (*storage.FridgeItem, error) {
	var exp sql.NullTime
	if expiryDate != nil {
		exp = sql.NullTime{Time: *expiryDate, Valid: true}
	}
	item, err := r.q.CreateFridgeItem(ctx, storage.CreateFridgeItemParams{
		UserID:     userID,
		ProductID:  productID,
		QuantityG:  quantityG,
		ExpiryDate: exp,
	})
	if err != nil {
		return nil, err
	}
	return &item, nil
}

func (r *FridgeRepo) Update(ctx context.Context, itemID, userID int64, quantityG *float64, expiryDate *time.Time) (*storage.FridgeItem, error) {
	var q float64
	if quantityG != nil {
		q = *quantityG
	}
	var exp sql.NullTime
	if expiryDate != nil {
		exp = sql.NullTime{Time: *expiryDate, Valid: true}
	}
	item, err := r.q.UpdateFridgeItem(ctx, storage.UpdateFridgeItemParams{
		QuantityG:  q,
		ExpiryDate: exp,
		ID:         itemID,
		UserID:     userID,
	})
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, errorz.ErrNotFound
		}
		return nil, err
	}
	return &item, nil
}

func (r *FridgeRepo) Delete(ctx context.Context, itemID, userID int64) error {
	return r.q.DeleteFridgeItem(ctx, storage.DeleteFridgeItemParams{ID: itemID, UserID: userID})
}

type ConsumptionRepo struct {
	q *storage.Queries
}

func NewConsumptionRepo(dbtx DBTX) *ConsumptionRepo {
	return &ConsumptionRepo{q: storage.New(dbtx)}
}

func (r *ConsumptionRepo) Create(ctx context.Context, userID, productID int64, day time.Time, mealType string, grams float64) error {
	_, err := r.q.CreateConsumptionLog(ctx, storage.CreateConsumptionLogParams{
		UserID:    userID,
		ProductID: productID,
		Day:       day,
		MealType:  mealType,
		Grams:     grams,
	})
	return err
}

func (r *ConsumptionRepo) ListByUser(ctx context.Context, userID int64) ([]ConsumeLogEntry, error) {
	rows, err := r.q.ListConsumptionByUser(ctx, userID)
	if err != nil {
		return nil, err
	}
	var entries []ConsumeLogEntry
	for _, row := range rows {
		entries = append(entries, ConsumeLogEntry{
			Day:        row.Day,
			ProductID:  row.ProductID,
			Grams:      row.Grams,
			Kcal100:    row.Kcal100,
			Protein100: row.Protein100,
			Fat100:     row.Fat100,
			Carbs100:   row.Carbs100,
		})
	}
	return entries, nil
}

type DBTX interface {
	ExecContext(context.Context, string, ...interface{}) (sql.Result, error)
	PrepareContext(context.Context, string) (*sql.Stmt, error)
	QueryContext(context.Context, string, ...interface{}) (*sql.Rows, error)
	QueryRowContext(context.Context, string, ...interface{}) *sql.Row
}
