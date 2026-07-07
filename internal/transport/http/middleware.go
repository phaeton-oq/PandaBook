package http

import (
	"errors"
	"net/http"
	"strings"

	"github.com/labstack/echo/v4"

	"pandabook/internal/errorz"
	"pandabook/internal/jwt"
)

func AuthMiddleware(jwtManager *jwt.Manager) echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			auth := c.Request().Header.Get("Authorization")
			if auth == "" || !strings.HasPrefix(auth, "Bearer ") {
				return echo.NewHTTPError(http.StatusUnauthorized, "Not authenticated")
			}
			token := strings.TrimPrefix(auth, "Bearer ")
			userID, err := jwtManager.ParseToken(token)
			if err != nil {
				return echo.NewHTTPError(http.StatusUnauthorized, "Invalid or expired token")
			}
			c.Set("userID", userID)
			return next(c)
		}
	}
}

func OptionalAuthMiddleware(jwtManager *jwt.Manager) echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			auth := c.Request().Header.Get("Authorization")
			if auth != "" && strings.HasPrefix(auth, "Bearer ") {
				token := strings.TrimPrefix(auth, "Bearer ")
				if userID, err := jwtManager.ParseToken(token); err == nil {
					c.Set("userID", userID)
				}
			}
			return next(c)
		}
	}
}

type ErrorResponse struct {
	Detail string `json:"detail"`
}

func ErrorHandler(err error, c echo.Context) {
	code := http.StatusInternalServerError
	msg := "Internal server error"
	var he *echo.HTTPError
	if errors.As(err, &he) {
		code = he.Code
		msg = he.Message.(string)
	} else if errors.Is(err, errorz.ErrNotFound) {
		code = http.StatusNotFound
		msg = "Not found"
	} else if errors.Is(err, errorz.ErrAlreadyExists) {
		code = http.StatusConflict
		msg = "Already exists"
	} else if errors.Is(err, errorz.ErrInvalidCredentials) {
		code = http.StatusUnauthorized
		msg = "Invalid email or password"
	} else if errors.Is(err, errorz.ErrInvalidInput) {
		code = http.StatusBadRequest
		msg = "Invalid input"
	}
	c.JSON(code, ErrorResponse{Detail: msg})
}
