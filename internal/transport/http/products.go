package http

import (
	"net/http"

	"github.com/labstack/echo/v4"

	"pandabook/internal/domain"
	"pandabook/internal/service"
	"pandabook/pkg/off"
)

type ProductsHandler struct {
	prodSvc   *service.ProductService
	offClient *off.Client
}

func NewProductsHandler(prodSvc *service.ProductService, offClient *off.Client) *ProductsHandler {
	return &ProductsHandler{prodSvc: prodSvc, offClient: offClient}
}

func (h *ProductsHandler) List(c echo.Context) error {
	q := c.QueryParam("q")
	products, err := h.prodSvc.List(c.Request().Context(), q)
	if err != nil {
		return err
	}
	if products == nil {
		products = []domain.Product{}
	}
	return c.JSON(http.StatusOK, products)
}

func (h *ProductsHandler) Search(c echo.Context) error {
	q := c.QueryParam("q")
	limit := 10
	products := h.offClient.SearchProducts(q, limit)
	if products == nil {
		products = []domain.Product{}
	}
	return c.JSON(http.StatusOK, products)
}

func (h *ProductsHandler) ByBarcode(c echo.Context) error {
	code := c.Param("code")
	product := h.offClient.LookupBarcode(code)
	if product == nil {
		return echo.NewHTTPError(http.StatusNotFound, "Product not found")
	}
	return c.JSON(http.StatusOK, product)
}
