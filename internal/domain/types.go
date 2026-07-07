package domain

import "time"

type Sex string
type Goal string
type ActivityLevel string
type MealType string

const (
	SexMale   Sex = "male"
	SexFemale Sex = "female"

	GoalLose     Goal = "lose"
	GoalMaintain Goal = "maintain"
	GoalGain     Goal = "gain"

	ActivitySedentary  ActivityLevel = "sedentary"
	ActivityLight      ActivityLevel = "light"
	ActivityModerate   ActivityLevel = "moderate"
	ActivityActive     ActivityLevel = "active"
	ActivityVeryActive ActivityLevel = "very_active"

	MealBreakfast MealType = "breakfast"
	MealLunch     MealType = "lunch"
	MealDinner    MealType = "dinner"
	MealSnack     MealType = "snack"
)

type DietaryPrefs struct {
	Vegan       bool     `json:"vegan"`
	Vegetarian  bool     `json:"vegetarian"`
	Halal       bool     `json:"halal"`
	GlutenFree  bool     `json:"gluten_free"`
	LactoseFree bool     `json:"lactose_free"`
	Allergens   []string `json:"allergens"`
}

type UserProfile struct {
	Sex      Sex           `json:"sex"`
	Age      int           `json:"age"`
	WeightKg float64       `json:"weight_kg"`
	HeightCm float64       `json:"height_cm"`
	Activity ActivityLevel `json:"activity"`
	Goal     Goal          `json:"goal"`
	Prefs    DietaryPrefs  `json:"prefs"`
}

type Product struct {
	ID          int64   `json:"id"`
	Name        string  `json:"name"`
	Category    string  `json:"category"`
	Kcal100     float64 `json:"kcal_100"`
	Protein100  float64 `json:"protein_100"`
	Fat100      float64 `json:"fat_100"`
	Carbs100    float64 `json:"carbs_100"`
	Tags        []string `json:"tags"`
	OffBarcode  *string `json:"off_barcode,omitempty"`
}

type FridgeItem struct {
	Product    Product    `json:"product"`
	QuantityG  float64    `json:"quantity_g"`
	ExpiryDate *time.Time `json:"expiry_date,omitempty"`
}

type Targets struct {
	Kcal     float64 `json:"kcal"`
	ProteinG float64 `json:"protein_g"`
	FatG     float64 `json:"fat_g"`
	CarbsG   float64 `json:"carbs_g"`
}

type MealItem struct {
	ProductName  string  `json:"product_name"`
	Grams        float64 `json:"grams"`
	Kcal         float64 `json:"kcal"`
	Protein      float64 `json:"protein"`
	Fat          float64 `json:"fat"`
	Carbs        float64 `json:"carbs"`
	ExpiringSoon bool    `json:"expiring_soon"`
}

type Meal struct {
	Type    MealType   `json:"type"`
	Items   []MealItem `json:"items"`
	Kcal    float64    `json:"kcal"`
	Protein float64    `json:"protein"`
	Fat     float64    `json:"fat"`
	Carbs   float64    `json:"carbs"`
}

type DayPlan struct {
	Day         string   `json:"day"`
	Targets     Targets  `json:"targets"`
	Meals       []Meal   `json:"meals"`
	Totals      Targets  `json:"totals"`
	CoveragePct float64  `json:"coverage_pct"`
	Notes       []string `json:"notes"`
}

type ShoppingItem struct {
	ProductName string  `json:"product_name"`
	Grams       float64 `json:"grams"`
	Reason      string  `json:"reason"`
}

type Recipe struct {
	Title       string   `json:"title"`
	Ingredients []string `json:"ingredients"`
	Steps       []string `json:"steps"`
}

type DayNutrition struct {
	Day      string  `json:"day"`
	Kcal     float64 `json:"kcal"`
	ProteinG float64 `json:"protein_g"`
	FatG     float64 `json:"fat_g"`
	CarbsG   float64 `json:"carbs_g"`
	GoalMet  bool    `json:"goal_met"`
}
