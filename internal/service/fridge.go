package service

import (
	"context"
	"time"

	"pandabook/internal/db/storage"
	"pandabook/internal/domain"
)

type fridgeRepo interface {
	List(ctx context.Context, userID int64) ([]domain.FridgeItem, error)
	GetByID(ctx context.Context, itemID, userID int64) (*storage.FridgeItem, *storage.Product, error)
	Create(ctx context.Context, userID, productID int64, quantityG float64, expiryDate *time.Time) (*storage.FridgeItem, error)
	Update(ctx context.Context, itemID, userID int64, quantityG *float64, expiryDate *time.Time) (*storage.FridgeItem, error)
	Delete(ctx context.Context, itemID, userID int64) error
}

type FridgeService struct {
	repo fridgeRepo
}

func NewFridgeService(repo fridgeRepo) *FridgeService {
	return &FridgeService{repo: repo}
}

func (s *FridgeService) List(ctx context.Context, userID int64) ([]domain.FridgeItem, error) {
	return s.repo.List(ctx, userID)
}

func (s *FridgeService) Create(ctx context.Context, userID, productID int64, quantityG float64, expiryDate *time.Time) (*storage.FridgeItem, error) {
	return s.repo.Create(ctx, userID, productID, quantityG, expiryDate)
}

func (s *FridgeService) Update(ctx context.Context, itemID, userID int64, quantityG *float64, expiryDate *time.Time) (*storage.FridgeItem, error) {
	return s.repo.Update(ctx, itemID, userID, quantityG, expiryDate)
}

func (s *FridgeService) Delete(ctx context.Context, itemID, userID int64) error {
	return s.repo.Delete(ctx, itemID, userID)
}

func (s *FridgeService) GetByID(ctx context.Context, itemID, userID int64) (*storage.FridgeItem, *storage.Product, error) {
	return s.repo.GetByID(ctx, itemID, userID)
}
