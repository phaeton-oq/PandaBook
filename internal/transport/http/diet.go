package http

import (
	"net/http"
	"strings"
	"time"

	"github.com/labstack/echo/v4"

	"pandabook/internal/domain"
	"pandabook/internal/service"
)

type DietHandler struct {
	dietSvc   *service.DietService
	prodSvc   *service.ProductService
	authSvc   *service.AuthService
	fridgeSvc *service.FridgeService
	llm       interface {
		SuggestRecipe([]string) domain.Recipe
		ExplainPlan(string) string
		SuggestShoppingList(string) *[]domain.ShoppingItem
	}
}

func NewDietHandler(
	dietSvc *service.DietService,
	prodSvc *service.ProductService,
	authSvc *service.AuthService,
	fridgeSvc *service.FridgeService,
	llm interface {
		SuggestRecipe([]string) domain.Recipe
		ExplainPlan(string) string
		SuggestShoppingList(string) *[]domain.ShoppingItem
	},
) *DietHandler {
	return &DietHandler{
		dietSvc:   dietSvc,
		prodSvc:   prodSvc,
		authSvc:   authSvc,
		fridgeSvc: fridgeSvc,
		llm:       llm,
	}
}

type planRequest struct {
	Profile domain.UserProfile      `json:"profile"`
	Fridge  []domain.FridgeItem     `json:"fridge"`
	Mode    string                  `json:"mode"`
	Request *string                 `json:"request,omitempty"`
}

type planResponse struct {
	Mode         string                `json:"mode"`
	Targets      domain.Targets        `json:"targets"`
	Plan         domain.DayPlan        `json:"plan"`
	ShoppingList []domain.ShoppingItem `json:"shopping_list"`
	Explanation  *string               `json:"explanation,omitempty"`
	Recipe       *domain.Recipe        `json:"recipe,omitempty"`
}

func (h *DietHandler) Plan(c echo.Context) error {
	var req planRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid request body")
	}
	targets := h.dietSvc.ComputeTargets(req.Profile)
	dayPlan := h.dietSvc.GenerateDayPlan(req.Fridge, targets, req.Profile.Prefs, nil)
	catalog, _ := h.prodSvc.List(c.Request().Context(), "")

	shopping := h.buildShopping(req.Profile, req.Fridge, targets, dayPlan, catalog, req.Mode)

	var explanation *string
	var recipe *domain.Recipe
	if req.Mode == "thinking" {
		used := usedProducts(dayPlan)
		if len(used) > 0 {
			r := h.llm.SuggestRecipe(used)
			recipe = &r
		}
		exp := h.llm.ExplainPlan(planSummary(req.Profile, dayPlan, req.Request))
		if exp != "" {
			explanation = &exp
		}
	}

	return c.JSON(http.StatusOK, planResponse{
		Mode:         req.Mode,
		Targets:      targets,
		Plan:         dayPlan,
		ShoppingList: shopping,
		Explanation:  explanation,
		Recipe:       recipe,
	})
}

func (h *DietHandler) buildShopping(profile domain.UserProfile, fridge []domain.FridgeItem, targets domain.Targets, plan domain.DayPlan, catalog []domain.Product, mode string) []domain.ShoppingItem {
	if mode == "thinking" {
		ctx := shoppingContext(profile, fridge, targets, plan)
		if llmItems := h.llm.SuggestShoppingList(ctx); llmItems != nil {
			cleaned := dropRedundantCarbs(*llmItems, fridge)
			if len(cleaned) > 0 {
				return cleaned
			}
		}
	}
	fallback := h.dietSvc.SmartShoppingFallback(catalog, fridge, targets, plan.Totals, profile.Prefs)
	if fallback != nil {
		return fallback
	}
	available := h.dietSvc.CatalogWithoutFridge(catalog, fridge)
	return h.dietSvc.Recommend(available, targets, plan.Totals, profile.Prefs)
}

func (h *DietHandler) PlanMe(c echo.Context) error {
	userID := c.Get("userID").(int64)
	profile, _, _, err := h.authSvc.GetProfile(c.Request().Context(), userID)
	if err != nil {
		return err
	}
	fridge, err := h.fridgeSvc.List(c.Request().Context(), userID)
	if err != nil {
		return err
	}
	mode := c.QueryParam("mode")
	if mode == "" {
		mode = "fast"
	}
	reqStr := c.QueryParam("request")
	var reqPtr *string
	if reqStr != "" {
		reqPtr = &reqStr
	}

	targets := h.dietSvc.ComputeTargets(*profile)
	dayPlan := h.dietSvc.GenerateDayPlan(fridge, targets, profile.Prefs, nil)
	catalog, _ := h.prodSvc.List(c.Request().Context(), "")

	shopping := h.buildShopping(*profile, fridge, targets, dayPlan, catalog, mode)

	var explanation *string
	var recipe *domain.Recipe
	if mode == "thinking" {
		used := usedProducts(dayPlan)
		if len(used) > 0 {
			r := h.llm.SuggestRecipe(used)
			recipe = &r
		}
		exp := h.llm.ExplainPlan(planSummary(*profile, dayPlan, reqPtr))
		if exp != "" {
			explanation = &exp
		}
	}

	return c.JSON(http.StatusOK, planResponse{
		Mode:         mode,
		Targets:      targets,
		Plan:         dayPlan,
		ShoppingList: shopping,
		Explanation:  explanation,
		Recipe:       recipe,
	})
}

func (h *DietHandler) ShoppingMe(c echo.Context) error {
	userID := c.Get("userID").(int64)
	profile, _, _, err := h.authSvc.GetProfile(c.Request().Context(), userID)
	if err != nil {
		return err
	}
	fridge, err := h.fridgeSvc.List(c.Request().Context(), userID)
	if err != nil {
		return err
	}
	mode := c.QueryParam("mode")
	if mode == "" {
		mode = "thinking"
	}
	targets := h.dietSvc.ComputeTargets(*profile)
	dayPlan := h.dietSvc.GenerateDayPlan(fridge, targets, profile.Prefs, nil)
	catalog, _ := h.prodSvc.List(c.Request().Context(), "")

	shopping := h.buildShopping(*profile, fridge, targets, dayPlan, catalog, mode)
	return c.JSON(http.StatusOK, shopping)
}

func (h *DietHandler) Recipe(c echo.Context) error {
	var req struct {
		Ingredients []string `json:"ingredients"`
	}
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid request body")
	}
	recipe := h.llm.SuggestRecipe(req.Ingredients)
	return c.JSON(http.StatusOK, recipe)
}

func (h *DietHandler) Demo(c echo.Context) error {
	catalog, _ := h.prodSvc.List(c.Request().Context(), "")
	byName := make(map[string]domain.Product)
	for _, p := range catalog {
		byName[p.Name] = p
	}

	type pick struct {
		name string
		q    float64
		d    int
	}
	picks := []pick{
		{"Куриная грудка", 300, 2},
		{"Овсянка", 200, 20},
		{"Яйцо куриное", 300, 5},
		{"Брокколи", 250, 4},
		{"Рис белый", 200, 30},
	}
	var fridge []domain.FridgeItem
	now := time.Now()
	for _, p := range picks {
		if prod, ok := byName[p.name]; ok {
			exp := now.AddDate(0, 0, p.d)
			fridge = append(fridge, domain.FridgeItem{
				Product:    prod,
				QuantityG:  p.q,
				ExpiryDate: &exp,
			})
		}
	}

	profile := domain.UserProfile{
		Sex:      domain.SexMale,
		Age:      25,
		WeightKg: 78,
		HeightCm: 182,
		Activity: domain.ActivityModerate,
		Goal:     domain.GoalLose,
		Prefs:    domain.DietaryPrefs{},
	}
	targets := h.dietSvc.ComputeTargets(profile)
	dayPlan := h.dietSvc.GenerateDayPlan(fridge, targets, profile.Prefs, nil)
	shopping := h.dietSvc.Recommend(catalog, targets, dayPlan.Totals, profile.Prefs)
	return c.JSON(http.StatusOK, planResponse{
		Mode:         "fast",
		Targets:      targets,
		Plan:         dayPlan,
		ShoppingList: shopping,
	})
}

func usedProducts(plan domain.DayPlan) []string {
	var seen []string
	seenSet := make(map[string]bool)
	for _, meal := range plan.Meals {
		for _, item := range meal.Items {
			if !seenSet[item.ProductName] {
				seenSet[item.ProductName] = true
				seen = append(seen, item.ProductName)
			}
		}
	}
	return seen
}

func planSummary(profile domain.UserProfile, plan domain.DayPlan, userReq *string) string {
	s := "Цель пользователя: " + string(profile.Goal) + ". " +
		"Норма на день: " + fmtFloat(plan.Targets.Kcal) + " ккал, Б " + fmtFloat(plan.Targets.ProteinG) + " / Ж " + fmtFloat(plan.Targets.FatG) + " / У " + fmtFloat(plan.Targets.CarbsG) + " г. " +
		"Составлено из холодильника: " + fmtFloat(plan.Totals.Kcal) + " ккал, Б " + fmtFloat(plan.Totals.ProteinG) + " / Ж " + fmtFloat(plan.Totals.FatG) + " / У " + fmtFloat(plan.Totals.CarbsG) + " г. " +
		"Покрытие нормы: " + fmtFloat(plan.CoveragePct) + "%. " +
		"Продукты в рационе: " + stringsJoin(usedProducts(plan), ", ") + "."
	if userReq != nil && *userReq != "" {
		s += " Пожелание пользователя: " + *userReq
	}
	return s
}

func shoppingContext(profile domain.UserProfile, fridge []domain.FridgeItem, targets domain.Targets, plan domain.DayPlan) string {
	var flags []string
	if profile.Prefs.Vegan {
		flags = append(flags, "веган")
	}
	if profile.Prefs.Vegetarian {
		flags = append(flags, "вегетарианец")
	}
	if profile.Prefs.Halal {
		flags = append(flags, "халяль")
	}
	if profile.Prefs.GlutenFree {
		flags = append(flags, "без глютена")
	}
	if profile.Prefs.LactoseFree {
		flags = append(flags, "без лактозы")
	}

	dProtein := fmtFloat(targets.ProteinG - plan.Totals.ProteinG)
	dFat := fmtFloat(targets.FatG - plan.Totals.FatG)
	dCarbs := fmtFloat(targets.CarbsG - plan.Totals.CarbsG)

	grainNote := ""
	if fridgeHasGrains2(fridge) {
		grainNote = "Дома уже есть гарнир/углеводы (макароны, каша, рис и т.п.) — НЕ предлагай докупать углеводы; предложи белок, овощи и жиры к тому, что уже есть.\n"
	}

	restrictions := "нет"
	if len(flags) > 0 {
		restrictions = stringsJoin(flags, ", ")
	}
	allergens := "нет"
	if len(profile.Prefs.Allergens) > 0 {
		allergens = stringsJoin(profile.Prefs.Allergens, ", ")
	}

	s := "Цель: " + string(profile.Goal) + ". Активность: " + string(profile.Activity) + ".\n" +
		"Ограничения: " + restrictions + "; аллергены-исключения: " + allergens + ".\n\n" +
		"Норма на день: " + fmtFloat(targets.Kcal) + " ккал, Б " + fmtFloat(targets.ProteinG) + " / Ж " + fmtFloat(targets.FatG) + " / У " + fmtFloat(targets.CarbsG) + " г.\n" +
		"Из холодильника набрано: " + fmtFloat(plan.Totals.Kcal) + " ккал, Б " + fmtFloat(plan.Totals.ProteinG) + " / Ж " + fmtFloat(plan.Totals.FatG) + " / У " + fmtFloat(plan.Totals.CarbsG) + " г.\n" +
		"Покрытие нормы: " + fmtFloat(plan.CoveragePct) + "%.\n" +
		"Дефицит: белок " + dProtein + " г, жиры " + dFat + " г, углеводы " + dCarbs + " г.\n" +
		grainNote

	s += "Продукты в рационе на сегодня: " + stringsJoin(usedProducts(plan), ", ") + ".\n\n"
	s += "УЖЕ ЕСТЬ В ХОЛОДИЛЬНИКЕ (эти продукты НЕЛЬЗЯ добавлять в список докупок):\n"
	for _, item := range fridge {
		exp := ""
		if item.ExpiryDate != nil {
			exp = ", годен до " + item.ExpiryDate.Format("2006-01-02")
		}
		s += "- " + item.Product.Name + ": " + fmtFloat(item.QuantityG) + " г" + exp + "\n"
	}
	s += "\nСоставь список докупок под ЭТО содержимое холодильника, а не универсальный шаблон."
	return s
}

func fridgeHasGrains2(fridge []domain.FridgeItem) bool {
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

var carbFillers = []string{"мёд", "мед", "сахар", "рис", "овсян", "греч", "макар", "хлеб", "банан"}

func dropRedundantCarbs(items []domain.ShoppingItem, fridge []domain.FridgeItem) []domain.ShoppingItem {
	if !fridgeHasGrains2(fridge) {
		return items
	}
	var out []domain.ShoppingItem
	for _, item := range items {
		name := strings.ToLower(strings.TrimSpace(item.ProductName))
		isCarb := false
		for _, h := range carbFillers {
			if strings.Contains(name, h) {
				isCarb = true
				break
			}
		}
		if !isCarb {
			out = append(out, item)
		}
	}
	return out
}
