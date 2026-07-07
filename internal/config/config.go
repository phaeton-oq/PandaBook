package config

import (
	"os"

	"github.com/ilyakaznacheev/cleanenv"
)

type Config struct {
	HTTP      HTTPConfig
	Database  DatabaseConfig
	JWT       JWTConfig
	LLM       LLMConfig
}

type HTTPConfig struct {
	Addr string `env:"SERVER_ADDR" env-default:":8080"`
}

type DatabaseConfig struct {
	Path string `env:"DATABASE_PATH" env-default:"pandabook.db"`
}

type JWTConfig struct {
	Secret string `env:"JWT_SECRET" env-required:"true"`
}

type LLMConfig struct {
	APIKey  string `env:"LLM_API_KEY" env-default:""`
	BaseURL string `env:"LLM_BASE_URL" env-default:""`
	Model   string `env:"LLM_MODEL" env-default:"pandabook-pro"`
}

func New() (*Config, error) {
	var cfg Config
	if err := cleanenv.ReadConfig(".env", &cfg); err != nil {
		if err := cleanenv.ReadEnv(&cfg); err != nil {
			return nil, err
		}
	}
	if cfg.LLM.APIKey == "" {
		cfg.LLM.APIKey = os.Getenv("CEREBRAS_API_KEY")
	}
	return &cfg, nil
}
