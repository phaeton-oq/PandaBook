package app

import (
	"context"
	"database/sql"
	"log/slog"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"github.com/labstack/echo/v4"
	"github.com/labstack/echo/v4/middleware"
	_ "modernc.org/sqlite"

	"pandabook/internal/config"
	"pandabook/internal/db"
	"pandabook/internal/db/storage"
	"pandabook/internal/jwt"
	"pandabook/internal/repository"
	"pandabook/internal/service"
	httptransport "pandabook/internal/transport/http"
	"pandabook/integrations"
	"pandabook/pkg/off"
)

type App struct {
	cfg  *config.Config
	echo *echo.Echo
	sqlDB *sql.DB
}

func New(ctx context.Context, cfg *config.Config) (*App, error) {
	a := &App{cfg: cfg}

	if err := a.initDB(ctx); err != nil {
		return nil, err
	}

	a.initEcho()

	return a, nil
}

func (a *App) initDB(ctx context.Context) error {
	var err error
	a.sqlDB, err = sql.Open("sqlite", a.cfg.Database.Path)
	if err != nil {
		return err
	}
	a.sqlDB.SetMaxOpenConns(1)
	a.sqlDB.SetMaxIdleConns(1)

	if err := db.Migrate(a.sqlDB); err != nil {
		return err
	}

	q := storage.New(a.sqlDB)
	if err := db.SeedProducts(ctx, q); err != nil {
		return err
	}

	return nil
}

func (a *App) initEcho() {
	e := echo.New()
	e.HideBanner = true
	e.HidePort = true
	e.Server.ReadHeaderTimeout = 10 * time.Second

	e.Use(middleware.Logger())
	e.Use(middleware.Recover())
	e.Use(middleware.CORSWithConfig(middleware.CORSConfig{
		AllowOrigins:     []string{"*"},
		AllowMethods:     []string{"GET", "POST", "PATCH", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"*"},
		AllowCredentials: false,
	}))
	e.HTTPErrorHandler = httptransport.ErrorHandler

	jwtManager := jwt.NewManager(a.cfg.JWT.Secret, 7*24*time.Hour)

	// Repos
	userRepo := repository.NewUserRepo(a.sqlDB)
	productRepo := repository.NewProductRepo(a.sqlDB)
	fridgeRepo := repository.NewFridgeRepo(a.sqlDB)
	consumptionRepo := repository.NewConsumptionRepo(a.sqlDB)

	// Services
	productSvc := service.NewProductService(productRepo)
	dietSvc := service.NewDietService(productSvc)
	authSvc := service.NewAuthService(userRepo, jwtManager)
	fridgeSvc := service.NewFridgeService(fridgeRepo)
	progressSvc := service.NewProgressService(userRepo, consumptionRepo, dietSvc)

	// Integrations
	offClient := off.New()
	llmClient := integrations.NewLLMClient(a.cfg.LLM.APIKey, a.cfg.LLM.BaseURL, a.cfg.LLM.Model)

	// Handlers
	authHandler := httptransport.NewAuthHandler(authSvc, jwtManager)
	dietHandler := httptransport.NewDietHandler(dietSvc, productSvc, authSvc, fridgeSvc, llmClient)
	fridgeHandler := httptransport.NewFridgeHandler(fridgeSvc, productSvc, offClient)
	productsHandler := httptransport.NewProductsHandler(productSvc, offClient)
	progressHandler := httptransport.NewProgressHandler(progressSvc)

	authMw := httptransport.AuthMiddleware(jwtManager)
	optionalAuthMw := httptransport.OptionalAuthMiddleware(jwtManager)

	// API routes
	api := e.Group("/api")

	// Auth
	authGrp := api.Group("/auth")
	authGrp.POST("/register", authHandler.Register)
	authGrp.POST("/login", authHandler.Login)
	authGrp.GET("/me", authHandler.Me, authMw)
	authGrp.PATCH("/me", authHandler.UpdateMe, authMw)

	// Diet
	dietGrp := api.Group("/diet")
	dietGrp.POST("/plan", dietHandler.Plan)
	dietGrp.GET("/demo", dietHandler.Demo)
	dietGrp.GET("/plan/me", dietHandler.PlanMe, authMw)
	dietGrp.GET("/shopping/me", dietHandler.ShoppingMe, authMw)
	dietGrp.POST("/recipe", dietHandler.Recipe)

	// Fridge
	fridgeGrp := api.Group("/fridge")
	fridgeGrp.GET("", fridgeHandler.List, authMw)
	fridgeGrp.POST("", fridgeHandler.Add, authMw)
	fridgeGrp.PATCH("/:item_id", fridgeHandler.Update, authMw)
	fridgeGrp.DELETE("/:item_id", fridgeHandler.Delete, authMw)

	// Products
	prods := api.Group("/products")
	prods.GET("", productsHandler.List)
	prods.GET("/search", productsHandler.Search)
	prods.GET("/barcode/:code", productsHandler.ByBarcode)

	// Progress
	progressGrp := api.Group("/progress")
	progressGrp.GET("/dashboard", progressHandler.Dashboard, optionalAuthMw)
	progressGrp.POST("/log", progressHandler.Log, optionalAuthMw)

	// Health
	e.GET("/health", func(c echo.Context) error {
		return c.JSON(http.StatusOK, map[string]string{"status": "ok", "layer": "go"})
	})

	// Frontend static files
	frontendDir := filepath.Join(getRootDir(), "frontend")
	e.Use(middleware.StaticWithConfig(middleware.StaticConfig{
		Root:   frontendDir,
		Index:  "landing.html",
		HTML5:  true,
		Browse: false,
	}))

	a.echo = e
}

func (a *App) Start() error {
	slog.Info("starting pandabook", "addr", a.cfg.HTTP.Addr)
	return a.echo.Start(a.cfg.HTTP.Addr)
}

func (a *App) Stop(ctx context.Context) error {
	slog.Info("shutting down...")
	if err := a.echo.Shutdown(ctx); err != nil {
		return err
	}
	return a.sqlDB.Close()
}

func getRootDir() string {
	wd, _ := os.Getwd()
	return wd
}
