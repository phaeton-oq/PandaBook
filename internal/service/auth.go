package service

import (
	"context"
	"errors"
	"regexp"
	"strings"

	"pandabook/internal/db/storage"
	"pandabook/internal/domain"
	"pandabook/internal/errorz"
	"pandabook/internal/jwt"
	"pandabook/pkg/crypto"
)

type AuthService struct {
	repo userRepo
	jwt  *jwt.Manager
}

func NewAuthService(repo userRepo, jwt *jwt.Manager) *AuthService {
	return &AuthService{repo: repo, jwt: jwt}
}

var emailRE = regexp.MustCompile(`^[^@\s]+@[^@\s]+\.[^@\s]+$`)

func (s *AuthService) Register(ctx context.Context, email, password, name string, profile domain.UserProfile) (string, error) {
	email = s.normalizeEmail(email)
	if !emailRE.MatchString(email) || len(email) < 3 || len(email) > 254 {
		return "", errorz.ErrInvalidInput
	}
	if len(password) < 8 || len(password) > 128 {
		return "", errorz.ErrInvalidInput
	}
	hash, err := crypto.GenerateHash(password)
	if err != nil {
		return "", err
	}
	user, err := s.repo.Create(ctx, &profile, email, hash, name)
	if err != nil {
		return "", err
	}
	return s.jwt.GenerateToken(user.ID)
}

func (s *AuthService) Login(ctx context.Context, email, password string) (string, error) {
	email = s.normalizeEmail(email)
	user, err := s.repo.GetByEmail(ctx, email)
	if err != nil {
		if errors.Is(err, errorz.ErrNotFound) {
			return "", errorz.ErrInvalidCredentials
		}
		return "", err
	}
	ok, err := crypto.ComparePasswordAndHash(password, user.PasswordHash)
	if err != nil || !ok {
		return "", errorz.ErrInvalidCredentials
	}
	return s.jwt.GenerateToken(user.ID)
}

func (s *AuthService) GetProfile(ctx context.Context, userID int64) (*domain.UserProfile, string, string, error) {
	user, err := s.repo.GetByID(ctx, userID)
	if err != nil {
		return nil, "", "", err
	}
	profile := domain.UserProfile{
		Sex:      domain.Sex(user.Sex),
		Age:      int(user.Age),
		WeightKg: user.WeightKg,
		HeightCm: user.HeightCm,
		Activity: domain.ActivityLevel(user.Activity),
		Goal:     domain.Goal(user.Goal),
		Prefs:    parsePrefs(user.PrefsCsv),
	}
	return &profile, user.Email, user.Name, nil
}

func (s *AuthService) UpdateProfile(ctx context.Context, userID int64, name *string, profile *domain.UserProfile) error {
	_, err := s.repo.Update(ctx, userID, name, profile, nil)
	return err
}

func (s *AuthService) normalizeEmail(email string) string {
	return strings.TrimSpace(strings.ToLower(email))
}

type userRepo interface {
	Create(ctx context.Context, profile *domain.UserProfile, email, passwordHash, name string) (*storage.User, error)
	GetByEmail(ctx context.Context, email string) (*storage.User, error)
	GetByID(ctx context.Context, id int64) (*storage.User, error)
	Update(ctx context.Context, id int64, name *string, profile *domain.UserProfile, passwordHash *string) (*storage.User, error)
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
