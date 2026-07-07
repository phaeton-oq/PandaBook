package service

import (
	"context"
	"fmt"
	"math"
	"sort"
	"strings"
	"time"

	"pandabook/internal/domain"
)

type dietProductRepo interface {
	List(ctx context.Context, query string) ([]domain.Product, error)
}

type DietService struct {
	productRepo dietProductRepo
}

func NewDietService(productRepo dietProductRepo) *DietService {
	return &DietService{productRepo: productRepo}
}

var activityFactor = map[domain.ActivityLevel]float64{
	domain.ActivitySedentary:  1.2,
	domain.ActivityLight:      1.375,
	domain.ActivityModerate:   1.55,
	domain.ActivityActive:     1.725,
	domain.ActivityVeryActive: 1.9,
}

var goalKcalAdjust = map[domain.Goal]float64{
	domain.GoalLose:     0.80,
	domain.GoalMaintain: 1.0,
	domain.GoalGain:     1.15,
}

var proteinPerKg = map[domain.Goal]float64{
	domain.GoalLose:     2.0,
	domain.GoalMaintain: 1.6,
	domain.GoalGain:     1.8,
}

const fatKcalShare = 0.27

func bmr(profile domain.UserProfile) float64 {
	base := 10*profile.WeightKg + 6.25*profile.HeightCm - 5*float64(profile.Age)
	if profile.Sex == domain.SexMale {
		return base + 5
	}
	return base - 161
}

func (s *DietService) ComputeTargets(profile domain.UserProfile) domain.Targets {
	tdee := bmr(profile) * activityFactor[profile.Activity]
	kcal := tdee * goalKcalAdjust[profile.Goal]
	proteinG := proteinPerKg[profile.Goal] * profile.WeightKg
	fatG := (kcal * fatKcalShare) / 9
	carbsKcal := kcal - proteinG*4 - fatG*9
	carbsG := math.Max(carbsKcal, 0) / 4
	return domain.Targets{
		Kcal:     math.Round(kcal),
		ProteinG: math.Round(proteinG),
		FatG:     math.Round(fatG),
		CarbsG:   math.Round(carbsG),
	}
}

var veganBlock = map[string]bool{"meat": true, "pork": true, "fish": true, "egg": true, "dairy": true, "honey": true}
var vegetarianBlock = map[string]bool{"meat": true, "pork": true, "fish": true}

func isAllowed(tags []string, prefs domain.DietaryPrefs) bool {
	tagSet := make(map[string]bool)
	for _, t := range tags {
		tagSet[t] = true
	}
	if prefs.Vegan {
		for t := range tagSet {
			if veganBlock[t] {
				return false
			}
		}
	}
	if prefs.Vegetarian {
		for t := range tagSet {
			if vegetarianBlock[t] {
				return false
			}
		}
	}
	if prefs.Halal && tagSet["pork"] {
		return false
	}
	if prefs.GlutenFree && tagSet["gluten"] {
		return false
	}
	if prefs.LactoseFree && tagSet["dairy"] {
		return false
	}
	for _, a := range prefs.Allergens {
		if tagSet[a] {
			return false
		}
	}
	return true
}

var mealOrder = []domain.MealType{domain.MealBreakfast, domain.MealLunch, domain.MealDinner, domain.MealSnack}

var mealSplit = map[domain.MealType]float64{
	domain.MealBreakfast: 0.25,
	domain.MealLunch:     0.35,
	domain.MealDinner:    0.30,
	domain.MealSnack:     0.10,
}

const minPortionG = 20.0
const maxPortionG = 300.0
const expiringSoonDays = 3

var drinkWords = []string{"напит", "газиров", "тархун", "лимонад", "cola", "pepsi", "soda", "juice", "water", "квас", "морс", "сок", "чай", "кофе", "компот", "beverage", "drink", "вода"}
var sweetWords = []string{"конфет", "шоколад", "chocolate", "батончик", "мармелад", "candy", "вафл", "wafer", "печенье", "пастил", "зефир"}

func isEdible(name, category string) bool {
	text := strings.ToLower(name + " " + category)
	for _, w := range drinkWords {
		if strings.Contains(text, w) {
			return false
		}
	}
	for _, w := range sweetWords {
		if strings.Contains(text, w) {
			return false
		}
	}
	return true
}

func macros(p domain.Product, grams float64) (kcal, protein, fat, carbs float64) {
	f := grams / 100
	return p.Kcal100 * f, p.Protein100 * f, p.Fat100 * f, p.Carbs100 * f
}

func (s *DietService) GenerateDayPlan(fridge []domain.FridgeItem, targets domain.Targets, prefs domain.DietaryPrefs, day *time.Time) domain.DayPlan {
	planDay := time.Now()
	if day != nil {
		planDay = *day
	}
	soon := planDay.AddDate(0, 0, expiringSoonDays)

	var pool []domain.FridgeItem
	for _, f := range fridge {
		if f.Product.Kcal100 <= 0 || !isEdible(f.Product.Name, f.Product.Category) || !isAllowed(f.Product.Tags, prefs) {
			continue
		}
		pool = append(pool, f)
	}
	sort.Slice(pool, func(i, j int) bool {
		if pool[i].ExpiryDate == nil && pool[j].ExpiryDate == nil {
			return false
		}
		if pool[i].ExpiryDate == nil {
			return false
		}
		if pool[j].ExpiryDate == nil {
			return true
		}
		return pool[i].ExpiryDate.Before(*pool[j].ExpiryDate)
	})

	assigned := make(map[domain.MealType][]domain.FridgeItem)
	for _, mt := range mealOrder {
		assigned[mt] = nil
	}
	for idx, item := range pool {
		mt := mealOrder[idx%len(mealOrder)]
		assigned[mt] = append(assigned[mt], item)
	}

	var meals []domain.Meal
	for _, mt := range mealOrder {
		budget := targets.Kcal * mealSplit[mt]
		meal := domain.Meal{Type: mt, Items: []domain.MealItem{}}
		var accKcal float64
		for _, item := range assigned[mt] {
			if accKcal >= budget*0.95 {
				break
			}
			kcalPerG := item.Product.Kcal100 / 100
			grams := math.Min((budget-accKcal)/kcalPerG, math.Min(item.QuantityG, maxPortionG))
			grams = math.Round(grams/10) * 10
			if grams < minPortionG {
				continue
			}
			k, p, f, c := macros(item.Product, grams)
			expiring := item.ExpiryDate != nil && !item.ExpiryDate.After(soon)
			meal.Items = append(meal.Items, domain.MealItem{
				ProductName:  item.Product.Name,
				Grams:        grams,
				Kcal:         math.Round(k),
				Protein:      math.Round(p*10) / 10,
				Fat:          math.Round(f*10) / 10,
				Carbs:        math.Round(c*10) / 10,
				ExpiringSoon: expiring,
			})
			meal.Kcal += k
			meal.Protein += p
			meal.Fat += f
			meal.Carbs += c
			accKcal += k
		}
		meal.Kcal = math.Round(meal.Kcal*10) / 10
		meal.Protein = math.Round(meal.Protein*10) / 10
		meal.Fat = math.Round(meal.Fat*10) / 10
		meal.Carbs = math.Round(meal.Carbs*10) / 10
		meals = append(meals, meal)
	}

	var totKcal, totProtein, totFat, totCarbs float64
	for _, m := range meals {
		totKcal += m.Kcal
		totProtein += m.Protein
		totFat += m.Fat
		totCarbs += m.Carbs
	}
	totals := domain.Targets{
		Kcal:     math.Round(totKcal),
		ProteinG: math.Round(totProtein),
		FatG:     math.Round(totFat),
		CarbsG:   math.Round(totCarbs),
	}
	var coverage float64
	if targets.Kcal > 0 {
		coverage = math.Min(totals.Kcal/targets.Kcal, 1.0) * 100
		coverage = math.Round(coverage*10) / 10
	}

	var notes []string
	for _, m := range meals {
		for _, it := range m.Items {
			if it.ExpiringSoon {
				notes = append(notes, "В рацион включены продукты с истекающим сроком годности.")
				goto doneNotes
			}
		}
	}
doneNotes:
	if coverage < 90 {
		notes = append(notes, "Холодильника не хватает на дневную норму — смотри список докупок.")
	}

	planDayStr := planDay.Format("2006-01-02")
	return domain.DayPlan{
		Day:         planDayStr,
		Targets:     targets,
		Meals:       meals,
		Totals:      totals,
		CoveragePct: coverage,
		Notes:       notes,
	}
}

const minDeficitG = 15.0
const maxBuyG = 400.0

func (s *DietService) Recommend(catalog []domain.Product, targets, planned domain.Targets, prefs domain.DietaryPrefs) []domain.ShoppingItem {
	macros := []struct {
		attr     string
		ru       string
		targetFn func(domain.Targets) float64
		totalFn  func(domain.Targets) float64
	}{
		{"Protein100", "белка", func(t domain.Targets) float64 { return t.ProteinG }, func(t domain.Targets) float64 { return planned.ProteinG }},
		{"Fat100", "жиров", func(t domain.Targets) float64 { return t.FatG }, func(t domain.Targets) float64 { return planned.FatG }},
		{"Carbs100", "углеводов", func(t domain.Targets) float64 { return t.CarbsG }, func(t domain.Targets) float64 { return planned.CarbsG }},
	}
	var recs []domain.ShoppingItem
	for _, m := range macros {
		deficit := m.targetFn(targets) - m.totalFn(planned)
		if deficit < minDeficitG {
			continue
		}
		product := s.richest(catalog, m.attr, prefs)
		if product == nil || getFloatAttr(*product, m.attr) <= 0 {
			continue
		}
		grams := math.Min(math.Round(deficit/(getFloatAttr(*product, m.attr)/100)/10)*10, maxBuyG)
		if grams <= 0 {
			continue
		}
		recs = append(recs, domain.ShoppingItem{
			ProductName: product.Name,
			Grams:       grams,
			Reason:      "покрывает нехватку " + m.ru + " (~" + fmt.Sprintf("%.0f", deficit) + " г)",
		})
	}
	return recs
}

func (s *DietService) richest(catalog []domain.Product, attr string, prefs domain.DietaryPrefs) *domain.Product {
	var best *domain.Product
	var bestVal float64
	for i := range catalog {
		if !isAllowed(catalog[i].Tags, prefs) {
			continue
		}
		val := getFloatAttr(catalog[i], attr)
		if val > bestVal {
			bestVal = val
			best = &catalog[i]
		}
	}
	return best
}

func getFloatAttr(p domain.Product, attr string) float64 {
	switch attr {
	case "Protein100":
		return p.Protein100
	case "Fat100":
		return p.Fat100
	case "Carbs100":
		return p.Carbs100
	}
	return 0
}

func (s *DietService) SmartShoppingFallback(catalog []domain.Product, fridge []domain.FridgeItem, targets, planned domain.Targets, prefs domain.DietaryPrefs) []domain.ShoppingItem {
	inFridge := make(map[string]bool)
	for _, f := range fridge {
		inFridge[strings.ToLower(strings.TrimSpace(f.Product.Name))] = true
	}
	var available []domain.Product
	for _, p := range catalog {
		if !inFridge[strings.ToLower(strings.TrimSpace(p.Name))] {
			available = append(available, p)
		}
	}
	if len(available) == 0 {
		return nil
	}

	byName := make(map[string]domain.Product)
	for _, p := range available {
		byName[strings.ToLower(strings.TrimSpace(p.Name))] = p
	}

	defProtein := targets.ProteinG - planned.ProteinG
	defFat := targets.FatG - planned.FatG
	defCarbs := targets.CarbsG - planned.CarbsG
	hasGrain := fridgeHasGrains(fridge)
	seed := fridgeSeed(fridge)
	var recs []domain.ShoppingItem

	if defProtein >= minDeficitG {
		var candidates []string
		var reason string
		if hasGrain {
			candidates = []string{"Яйцо куриное", "Тунец консерв.", "Творог 5%", "Куриная грудка", "Фасоль"}
			reason = "к имеющимся макаронам/гарниру не хватает белка"
		} else {
			candidates = []string{"Куриная грудка", "Яйцо куриное", "Творог 5%", "Лосось", "Чечевица"}
			reason = "закрывает нехватку белка (~" + fmt.Sprintf("%.0f", defProtein) + " г)"
		}
		if product := pickProduct(candidates, byName, prefs, seed+":p"); product != nil {
			if grams := gramsForMacro(*product, "Protein100", defProtein); grams > 0 {
				recs = append(recs, domain.ShoppingItem{ProductName: product.Name, Grams: grams, Reason: reason})
			}
		}
	}

	if defFat >= minDeficitG {
		var candidates []string
		var reason string
		if hasGrain {
			candidates = []string{"Сыр твёрдый", "Авокадо", "Сливочное масло", "Йогурт натур."}
			reason = "добавит жиры к текущим продуктам"
		} else {
			candidates = []string{"Авокадо", "Оливковое масло", "Сыр твёрдый", "Миндаль"}
			reason = "закрывает нехватку жиров (~" + fmt.Sprintf("%.0f", defFat) + " г)"
		}
		if product := pickProduct(candidates, byName, prefs, seed+":f"); product != nil {
			if grams := gramsForMacro(*product, "Fat100", defFat); grams > 0 {
				recs = append(recs, domain.ShoppingItem{ProductName: product.Name, Grams: grams, Reason: reason})
			}
		}
	}

	if defCarbs >= minDeficitG && !hasGrain {
		candidates := []string{"Гречка", "Рис белый", "Картофель", "Овсянка"}
		if product := pickProduct(candidates, byName, prefs, seed+":c"); product != nil {
			if grams := gramsForMacro(*product, "Carbs100", defCarbs); grams > 0 {
				recs = append(recs, domain.ShoppingItem{ProductName: product.Name, Grams: grams, Reason: "закрывает нехватку углеводов (~" + fmt.Sprintf("%.0f", defCarbs) + " г)"})
			}
		}
	}

	if hasGrain && !fridgeHasCategory(fridge, "veg") {
		veg := pickProduct([]string{"Брокколи", "Помидор", "Огурец", "Шпинат", "Морковь"}, byName, prefs, seed+":v")
		if veg != nil {
			found := false
			for _, r := range recs {
				if strings.EqualFold(r.ProductName, veg.Name) {
					found = true
					break
				}
			}
			if !found {
				recs = append(recs, domain.ShoppingItem{ProductName: veg.Name, Grams: 250, Reason: "овощи к имеющимся макаронам/гарниру"})
			}
		}
	}
	if len(recs) > 6 {
		recs = recs[:6]
	}
	return recs
}

func fridgeHasGrains(fridge []domain.FridgeItem) bool {
	hints := []string{"макар", "рис", "овсян", "греч", "хлеб", "grain", "паст"}
	for _, f := range fridge {
		text := strings.ToLower(f.Product.Name + " " + f.Product.Category)
		if f.Product.Category == "grain" {
			return true
		}
		for _, h := range hints {
			if strings.Contains(text, h) {
				return true
			}
		}
	}
	return false
}

func fridgeHasCategory(fridge []domain.FridgeItem, cat string) bool {
	for _, f := range fridge {
		if f.Product.Category == cat {
			return true
		}
	}
	return false
}

func fridgeSeed(fridge []domain.FridgeItem) string {
	var names []string
	for _, f := range fridge {
		names = append(names, strings.ToLower(strings.TrimSpace(f.Product.Name)))
	}
	sort.Strings(names)
	return strings.Join(names, "|")
}

func pickProduct(names []string, byName map[string]domain.Product, prefs domain.DietaryPrefs, seed string) *domain.Product {
	var allowed []domain.Product
	for _, n := range names {
		key := strings.ToLower(strings.TrimSpace(n))
		if p, ok := byName[key]; ok && isAllowed(p.Tags, prefs) {
			allowed = append(allowed, p)
		}
	}
	if len(allowed) == 0 {
		return nil
	}
	hash := 0
	for _, c := range seed {
		hash = hash*31 + int(c)
	}
	if hash < 0 {
		hash = -hash
	}
	return &allowed[hash%len(allowed)]
}

func gramsForMacro(p domain.Product, attr string, deficitG float64) float64 {
	per100 := getFloatAttr(p, attr)
	if per100 <= 0 {
		return 0
	}
	grams := math.Min(math.Round(deficitG/(per100/100)/10)*10, maxBuyG)
	if grams < 0 {
		return 0
	}
	return grams
}

func (s *DietService) CatalogWithoutFridge(catalog []domain.Product, fridge []domain.FridgeItem) []domain.Product {
	inFridge := make(map[string]bool)
	for _, f := range fridge {
		inFridge[strings.ToLower(strings.TrimSpace(f.Product.Name))] = true
	}
	var result []domain.Product
	for _, p := range catalog {
		if !inFridge[strings.ToLower(strings.TrimSpace(p.Name))] {
			result = append(result, p)
		}
	}
	return result
}
