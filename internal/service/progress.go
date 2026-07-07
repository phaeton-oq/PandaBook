package service

import (
	"context"
	"math"
	"time"

	"pandabook/internal/domain"
	"pandabook/internal/repository"
)

type consumptionRepo interface {
	Create(ctx context.Context, userID, productID int64, day time.Time, mealType string, grams float64) error
	ListByUser(ctx context.Context, userID int64) ([]repository.ConsumeLogEntry, error)
}

const goalBandLow = 0.85
const goalBandHigh = 1.15

type ProgressService struct {
	userRepo        userRepo
	consumptionRepo consumptionRepo
	dietService     *DietService
}

func NewProgressService(userRepo userRepo, consumptionRepo consumptionRepo, dietService *DietService) *ProgressService {
	return &ProgressService{userRepo: userRepo, consumptionRepo: consumptionRepo, dietService: dietService}
}

func (s *ProgressService) GetDashboard(ctx context.Context, userID int64) (*domain.Targets, []domain.DayNutrition, int, string, string, error) {
	user, err := s.userRepo.GetByID(ctx, userID)
	if err != nil {
		return nil, nil, 0, "", "", err
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
	targets := s.dietService.ComputeTargets(profile)

	logs, err := s.consumptionRepo.ListByUser(ctx, userID)
	if err != nil {
		return nil, nil, 0, "", "", err
	}

	type dayEntry struct {
		kcal, protein, fat, carbs float64
	}
	agg := make(map[string]*dayEntry)
	daySet := make(map[string]bool)
	for _, entry := range logs {
		dayStr := entry.Day.Format("2006-01-02")
		if _, ok := agg[dayStr]; !ok {
			agg[dayStr] = &dayEntry{}
			daySet[dayStr] = true
		}
		f := entry.Grams / 100
		agg[dayStr].kcal += entry.Kcal100 * f
		agg[dayStr].protein += entry.Protein100 * f
		agg[dayStr].fat += entry.Fat100 * f
		agg[dayStr].carbs += entry.Carbs100 * f
	}

	var dayOrder []string
	for d := range daySet {
		dayOrder = append(dayOrder, d)
	}
	sortDays(dayOrder)

	var days []domain.DayNutrition
	for _, day := range dayOrder {
		e := agg[day]
		met := targets.Kcal > 0 && goalBandLow*targets.Kcal <= e.kcal && e.kcal <= goalBandHigh*targets.Kcal
		days = append(days, domain.DayNutrition{
			Day:      day,
			Kcal:     math.Round(e.kcal),
			ProteinG: math.Round(e.protein),
			FatG:     math.Round(e.fat),
			CarbsG:   math.Round(e.carbs),
			GoalMet:  met,
		})
	}

	streak := currentStreak(days)
	todayMet := len(days) > 0 && days[len(days)-1].GoalMet
	emoji, label := pandaMood(streak, todayMet)
	return &targets, days, streak, emoji, label, nil
}

func (s *ProgressService) Log(ctx context.Context, userID, productID int64, day time.Time, mealType string, grams float64) error {
	return s.consumptionRepo.Create(ctx, userID, productID, day, mealType, grams)
}

func currentStreak(days []domain.DayNutrition) int {
	streak := 0
	for i := len(days) - 1; i >= 0; i-- {
		if !days[i].GoalMet {
			break
		}
		streak++
	}
	return streak
}

func pandaMood(streak int, todayMet bool) (string, string) {
	if streak >= 3 {
		return "🐼✨", "Панда в восторге — так держать!"
	}
	if todayMet || streak >= 1 {
		return "🐼", "Панда довольна"
	}
	return "🐼💤", "Панду пора покормить по плану"
}

func sortDays(days []string) {
	for i := 0; i < len(days); i++ {
		for j := i + 1; j < len(days); j++ {
			if days[j] < days[i] {
				days[i], days[j] = days[j], days[i]
			}
		}
	}
}
