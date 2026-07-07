package http

import (
	"net/http"
	"time"

	"github.com/labstack/echo/v4"

	"pandabook/internal/domain"
	"pandabook/internal/service"
)

type ProgressHandler struct {
	progressSvc *service.ProgressService
}

func NewProgressHandler(progressSvc *service.ProgressService) *ProgressHandler {
	return &ProgressHandler{progressSvc: progressSvc}
}

type dashboardResponse struct {
	Targets    domain.Targets        `json:"targets"`
	Days       []domain.DayNutrition `json:"days"`
	Streak     int                   `json:"streak"`
	PandaEmoji string                `json:"panda_emoji"`
	PandaLabel string                `json:"panda_label"`
}

type logRequest struct {
	ProductID int64   `json:"product_id"`
	Grams     float64 `json:"grams"`
	MealType  string  `json:"meal_type"`
	Day       *string `json:"day,omitempty"`
}

func (h *ProgressHandler) Dashboard(c echo.Context) error {
	userID := int64(1) // default demo user
	if uid, ok := c.Get("userID").(int64); ok {
		userID = uid
	}
	targets, days, streak, emoji, label, err := h.progressSvc.GetDashboard(c.Request().Context(), userID)
	if err != nil {
		return err
	}
	return c.JSON(http.StatusOK, dashboardResponse{
		Targets:    *targets,
		Days:       days,
		Streak:     streak,
		PandaEmoji: emoji,
		PandaLabel: label,
	})
}

func (h *ProgressHandler) Log(c echo.Context) error {
	userID := int64(1)
	if uid, ok := c.Get("userID").(int64); ok {
		userID = uid
	}
	var req logRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid request body")
	}
	day := time.Now()
	if req.Day != nil {
		parsed, err := time.Parse("2006-01-02", *req.Day)
		if err == nil {
			day = parsed
		}
	}
	if err := h.progressSvc.Log(c.Request().Context(), userID, req.ProductID, day, req.MealType, req.Grams); err != nil {
		return err
	}
	return c.JSON(http.StatusOK, map[string]bool{"ok": true})
}
