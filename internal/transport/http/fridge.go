package http

import (
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/labstack/echo/v4"

	"pandabook/internal/db/storage"
	"pandabook/internal/domain"
	"pandabook/internal/errorz"
	"pandabook/internal/service"
	"pandabook/pkg/off"
)

type FridgeHandler struct {
	fridgeSvc *service.FridgeService
	prodSvc   *service.ProductService
	offClient *off.Client
}

func NewFridgeHandler(fridgeSvc *service.FridgeService, prodSvc *service.ProductService, offClient *off.Client) *FridgeHandler {
	return &FridgeHandler{fridgeSvc: fridgeSvc, prodSvc: prodSvc, offClient: offClient}
}

type addFridgeRequest struct {
	ProductID  *int64  `json:"product_id,omitempty"`
	Name       *string `json:"name,omitempty"`
	OffBarcode *string `json:"off_barcode,omitempty"`
	QuantityG  float64 `json:"quantity_g"`
	ExpiryDate *string `json:"expiry_date,omitempty"`
}

type updateFridgeRequest struct {
	QuantityG  *float64 `json:"quantity_g,omitempty"`
	ExpiryDate *string  `json:"expiry_date,omitempty"`
}

type fridgeItemOut struct {
	ID   int64             `json:"id"`
	Item domain.FridgeItem `json:"item"`
}

type fridgeListResponse struct {
	Items []fridgeItemOut `json:"items"`
}

func parseExpiry(s *string) *time.Time {
	if s == nil || *s == "" {
		return nil
	}
	t, err := time.Parse("2006-01-02", *s)
	if err != nil {
		return nil
	}
	return &t
}

func storageProductToDomain(p storage.Product) domain.Product {
	prod := domain.Product{
		ID:         p.ID,
		Name:       p.Name,
		Category:   p.Category,
		Kcal100:    p.Kcal100,
		Protein100: p.Protein100,
		Fat100:     p.Fat100,
		Carbs100:   p.Carbs100,
	}
	if p.TagsCsv != "" {
		prod.Tags = strings.Split(p.TagsCsv, ",")
	}
	if p.OffBarcode.Valid {
		s := p.OffBarcode.String
		prod.OffBarcode = &s
	}
	return prod
}

func (h *FridgeHandler) List(c echo.Context) error {
	userID := c.Get("userID").(int64)
	items, err := h.fridgeSvc.List(c.Request().Context(), userID)
	if err != nil {
		return err
	}
	var out []fridgeItemOut
	for _, item := range items {
		out = append(out, fridgeItemOut{ID: item.Product.ID, Item: item})
	}
	return c.JSON(http.StatusOK, fridgeListResponse{Items: out})
}

func (h *FridgeHandler) Add(c echo.Context) error {
	userID := c.Get("userID").(int64)
	var req addFridgeRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid request body")
	}

	var productID int64
	var prod *storage.Product
	if req.ProductID != nil {
		var err error
		prod, err = h.prodSvc.GetByID(c.Request().Context(), *req.ProductID)
		if err != nil {
			return echo.NewHTTPError(http.StatusNotFound, "Product not found")
		}
		productID = prod.ID
	} else if req.OffBarcode != nil {
		existing, _ := h.prodSvc.GetByBarcode(c.Request().Context(), *req.OffBarcode)
		if existing != nil {
			prod = existing
			productID = existing.ID
		} else {
			offProduct := h.offClient.LookupBarcode(*req.OffBarcode)
			if offProduct == nil {
				return echo.NewHTTPError(http.StatusNotFound, "Product not found in Open Food Facts")
			}
			var err error
			prod, err = h.prodSvc.Create(c.Request().Context(), offProduct.Name, offProduct.Category,
				offProduct.Kcal100, offProduct.Protein100, offProduct.Fat100, offProduct.Carbs100,
				offProduct.Tags, offProduct.OffBarcode)
			if err != nil {
				return err
			}
			productID = prod.ID
		}
	} else if req.Name != nil {
		existing, _ := h.prodSvc.GetByName(c.Request().Context(), *req.Name)
		if existing != nil {
			prod = existing
			productID = existing.ID
		} else {
			matches := h.offClient.SearchProducts(*req.Name, 1)
			if len(matches) > 0 {
				m := matches[0]
				var err error
				prod, err = h.prodSvc.Create(c.Request().Context(), m.Name, m.Category,
					m.Kcal100, m.Protein100, m.Fat100, m.Carbs100,
					m.Tags, m.OffBarcode)
				if err != nil {
					return err
				}
				productID = prod.ID
			} else {
				var err error
				prod, err = h.prodSvc.Create(c.Request().Context(), *req.Name, "other", 0, 0, 0, 0, nil, nil)
				if err != nil {
					return err
				}
				productID = prod.ID
			}
		}
	} else {
		return echo.NewHTTPError(http.StatusUnprocessableEntity, "Provide product_id or name/off_barcode")
	}

	expiry := parseExpiry(req.ExpiryDate)
	item, err := h.fridgeSvc.Create(c.Request().Context(), userID, productID, req.QuantityG, expiry)
	if err != nil {
		return err
	}

	out := fridgeItemOut{
		ID: item.ID,
		Item: domain.FridgeItem{
			Product:    storageProductToDomain(*prod),
			QuantityG:  req.QuantityG,
			ExpiryDate: expiry,
		},
	}
	return c.JSON(http.StatusCreated, out)
}

func (h *FridgeHandler) Update(c echo.Context) error {
	userID := c.Get("userID").(int64)
	itemIDStr := c.Param("item_id")
	itemID, err := strconv.ParseInt(itemIDStr, 10, 64)
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid item_id")
	}

	var req updateFridgeRequest
	if err := c.Bind(&req); err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid request body")
	}

	expiry := parseExpiry(req.ExpiryDate)
	_, err = h.fridgeSvc.Update(c.Request().Context(), itemID, userID, req.QuantityG, expiry)
	if err != nil {
		if err == errorz.ErrNotFound {
			return echo.NewHTTPError(http.StatusNotFound, "Fridge item not found")
		}
		return err
	}

	return c.JSON(http.StatusOK, map[string]string{"ok": "updated"})
}

func (h *FridgeHandler) Delete(c echo.Context) error {
	userID := c.Get("userID").(int64)
	itemIDStr := c.Param("item_id")
	itemID, err := strconv.ParseInt(itemIDStr, 10, 64)
	if err != nil {
		return echo.NewHTTPError(http.StatusBadRequest, "Invalid item_id")
	}

	if err := h.fridgeSvc.Delete(c.Request().Context(), itemID, userID); err != nil {
		return echo.NewHTTPError(http.StatusNotFound, "Fridge item not found")
	}
	return c.NoContent(http.StatusNoContent)
}
