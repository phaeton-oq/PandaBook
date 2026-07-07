package http

import (
	"errors"
	"net/http"

	"github.com/labstack/echo/v4"

	"pandabook/internal/domain"
	"pandabook/internal/errorz"
	"pandabook/internal/jwt"
	"pandabook/internal/service"
)

type AuthHandler struct {
	svc  *service.AuthService
	jwt  *jwt.Manager
}

func NewAuthHandler(svc *service.AuthService, jwt *jwt.Manager) *AuthHandler {
	return &AuthHandler{svc: svc, jwt: jwt}
}

type registerRequest struct {
	Email    string            `json:"email"`
	Password string            `json:"password"`
	Name     string            `json:"name"`
	Profile  domain.UserProfile `json:"profile"`
}

type loginRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

type tokenResponse struct {
	AccessToken string `json:"access_token"`
	TokenType   string `json:"token_type"`
}

type meResponse struct {
	ID      int64              `json:"id"`
	Email   string             `json:"email"`
	Name    string             `json:"name"`
	Profile domain.UserProfile `json:"profile"`
}

type updateMeRequest struct {
	Name    *string            `json:"name,omitempty"`
	Profile *domain.UserProfile `json:"profile,omitempty"`
}

func (h *AuthHandler) Register(c echo.Context) error {
	var req registerRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid request body")
	}
	token, err := h.svc.Register(c.Request().Context(), req.Email, req.Password, req.Name, req.Profile)
	if err != nil {
		if errors.Is(err, errorz.ErrAlreadyExists) {
			return c.JSON(http.StatusConflict, errorResponse("Email already registered"))
		}
		if errors.Is(err, errorz.ErrInvalidInput) {
			return c.JSON(http.StatusBadRequest, errorResponse("Invalid email or password"))
		}
		return err
	}
	return c.JSON(http.StatusCreated, tokenResponse{AccessToken: token, TokenType: "bearer"})
}

func (h *AuthHandler) Login(c echo.Context) error {
	var req loginRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid request body")
	}
	token, err := h.svc.Login(c.Request().Context(), req.Email, req.Password)
	if err != nil {
		return c.JSON(http.StatusUnauthorized, errorResponse("Invalid email or password"))
	}
	return c.JSON(http.StatusOK, tokenResponse{AccessToken: token, TokenType: "bearer"})
}

func (h *AuthHandler) Me(c echo.Context) error {
	userID := c.Get("userID").(int64)
	profile, email, name, err := h.svc.GetProfile(c.Request().Context(), userID)
	if err != nil {
		return err
	}
	return c.JSON(http.StatusOK, meResponse{
		ID:      userID,
		Email:   email,
		Name:    name,
		Profile: *profile,
	})
}

func (h *AuthHandler) UpdateMe(c echo.Context) error {
	var req updateMeRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid request body")
	}
	userID := c.Get("userID").(int64)
	if err := h.svc.UpdateProfile(c.Request().Context(), userID, req.Name, req.Profile); err != nil {
		return err
	}
	return h.Me(c)
}

func errorResponse(s string) map[string]string {
	return map[string]string{"detail": s}
}
