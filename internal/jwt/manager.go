package jwt

import (
	"fmt"
	"time"

	jwtv5 "github.com/golang-jwt/jwt/v5"
)

type Manager struct {
	secret   string
	duration time.Duration
}

func NewManager(secret string, duration time.Duration) *Manager {
	return &Manager{secret: secret, duration: duration}
}

type Claims struct {
	UserID int64  `json:"sub"`
	jwtv5.RegisteredClaims
}

func (m *Manager) GenerateToken(userID int64) (string, error) {
	now := time.Now()
	claims := Claims{
		UserID: userID,
		RegisteredClaims: jwtv5.RegisteredClaims{
			IssuedAt:  jwtv5.NewNumericDate(now),
			ExpiresAt: jwtv5.NewNumericDate(now.Add(m.duration)),
		},
	}
	token := jwtv5.NewWithClaims(jwtv5.SigningMethodHS256, claims)
	return token.SignedString([]byte(m.secret))
}

func (m *Manager) ParseToken(tokenString string) (int64, error) {
	token, err := jwtv5.ParseWithClaims(tokenString, &Claims{}, func(t *jwtv5.Token) (interface{}, error) {
		if _, ok := t.Method.(*jwtv5.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
		}
		return []byte(m.secret), nil
	})
	if err != nil {
		return 0, fmt.Errorf("invalid token: %w", err)
	}
	claims, ok := token.Claims.(*Claims)
	if !ok || !token.Valid {
		return 0, fmt.Errorf("invalid token claims")
	}
	return claims.UserID, nil
}
