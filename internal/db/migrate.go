package db

import (
	"database/sql"
	"embed"
	"log/slog"

	"github.com/pressly/goose/v3"
)

//go:embed migrations/*.sql
var migrations embed.FS

func Migrate(db *sql.DB) error {
	goose.SetBaseFS(migrations)
	goose.SetDialect("sqlite3")
	if err := goose.Up(db, "migrations"); err != nil {
		return err
	}
	slog.Info("database migrations applied")
	return nil
}
