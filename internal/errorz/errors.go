package errorz

import "errors"

var (
	ErrInternalServer    = errors.New("internal server error")
	ErrNotFound          = errors.New("not found")
	ErrAlreadyExists     = errors.New("already exists")
	ErrInvalidCredentials = errors.New("invalid email or password")
	ErrNotAuthenticated  = errors.New("not authenticated")
	ErrInvalidInput      = errors.New("invalid input")
)
