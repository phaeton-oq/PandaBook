package service

import (
	"context"
	"strings"

	"pandabook/internal/db/storage"
	"pandabook/internal/domain"
)

type productRepo interface {
	List(ctx context.Context, query string) ([]storage.Product, error)
	GetByID(ctx context.Context, id int64) (*storage.Product, error)
	GetByName(ctx context.Context, name string) (*storage.Product, error)
	GetByBarcode(ctx context.Context, barcode string) (*storage.Product, error)
	Create(ctx context.Context, name, category string, kcal, protein, fat, carbs float64, tags []string, barcode *string) (*storage.Product, error)
	Count(ctx context.Context) (int64, error)
}

type ProductService struct {
	repo productRepo
}

func NewProductService(repo productRepo) *ProductService {
	return &ProductService{repo: repo}
}

func storageToProduct(p storage.Product) domain.Product {
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
		s := p.OffBarcode.String
		prod.OffBarcode = &s
	}
	return prod
}

func (s *ProductService) List(ctx context.Context, query string) ([]domain.Product, error) {
	rows, err := s.repo.List(ctx, query)
	if err != nil {
		return nil, err
	}
	var products []domain.Product
	for _, p := range rows {
		products = append(products, storageToProduct(p))
	}
	if products == nil {
		products = []domain.Product{}
	}
	return products, nil
}

func (s *ProductService) GetByID(ctx context.Context, id int64) (*storage.Product, error) {
	return s.repo.GetByID(ctx, id)
}

func (s *ProductService) GetByName(ctx context.Context, name string) (*storage.Product, error) {
	return s.repo.GetByName(ctx, name)
}

func (s *ProductService) GetByBarcode(ctx context.Context, barcode string) (*storage.Product, error) {
	return s.repo.GetByBarcode(ctx, barcode)
}

func (s *ProductService) Create(ctx context.Context, name, category string, kcal, protein, fat, carbs float64, tags []string, barcode *string) (*storage.Product, error) {
	return s.repo.Create(ctx, name, category, kcal, protein, fat, carbs, tags, barcode)
}

func (s *ProductService) Count(ctx context.Context) (int64, error) {
	return s.repo.Count(ctx)
}
