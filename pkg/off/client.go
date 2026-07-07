package off

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"

	"pandabook/internal/domain"
)

const (
	searchURL  = "https://search.openfoodfacts.org/search"
	productURL = "https://world.openfoodfacts.org/api/v2/product/%s.json"
	userAgent  = "PandaBook/1.0 (hackathon)"
)

var nameTags = map[string][]string{
	"dairy": {"творог", "молоко", "молочн", "сыр", "йогурт", "сметан", "сливк", "кефир", "ряженк", "сливочн", "творож"},
	"meat":  {"свинин", "говядин", "куриц", "курин", "индейк", "мясо", "колбас", "ветчин", "бекон", "сосиск", "котлет", "фарш", "баранин", "телятин", "паштет", "пельмен", "стейк"},
	"pork":  {"свинин", "бекон", "ветчин", "сало"},
	"fish":  {"рыб", "лосось", "тунец", "сельд", "форел", "треск", "креветк", "краб", "икра", "скумбри", "горбуш", "морепродукт"},
	"egg":   {"яйц", "яичн", "омлет", "глазунь"},
	"gluten": {"хлеб", "макарон", "мука", "булк", "пшениц", "пицц", "лазан", "вафл", "печенье", "сухар", "батон", "лаваш", "пряник", "тесто"},
	"nuts":  {"орех", "миндал", "фундук", "арахис", "кешью", "фисташк"},
	"honey": {"мёд", "мед "},
}

type Client struct {
	httpClient *http.Client
}

func New() *Client {
	return &Client{httpClient: &http.Client{}}
}

func toFloat(v interface{}) float64 {
	if v == nil {
		return 0
	}
	switch x := v.(type) {
	case float64:
		return x
	case string:
		var f float64
		fmt.Sscanf(x, "%f", &f)
		return f
	}
	return 0
}

func getName(raw map[string]interface{}) string {
	for _, key := range []string{"product_name", "product_name_ru"} {
		if nm, ok := raw[key]; ok {
			switch v := nm.(type) {
			case string:
				if v != "" {
					return strings.TrimSpace(v)
				}
			case map[string]interface{}:
				for _, lang := range []string{"ru", "main"} {
					if s, ok := v[lang].(string); ok && s != "" {
						return strings.TrimSpace(s)
					}
				}
				for _, val := range v {
					if s, ok := val.(string); ok && s != "" {
						return strings.TrimSpace(s)
					}
				}
			}
		}
	}
	return ""
}

func inferTags(name string, raw map[string]interface{}) []string {
	text := strings.ToLower(name)
	tagSet := make(map[string]bool)
	for tag, words := range nameTags {
		for _, w := range words {
			if strings.Contains(text, w) {
				tagSet[tag] = true
				break
			}
		}
	}
	if allergens, ok := raw["allergens_tags"].([]interface{}); ok {
		for _, a := range allergens {
			s := fmt.Sprint(a)
			if strings.Contains(s, "milk") {
				tagSet["dairy"] = true
			}
			if strings.Contains(s, "gluten") {
				tagSet["gluten"] = true
			}
			if strings.Contains(s, "egg") {
				tagSet["egg"] = true
			}
			if strings.Contains(s, "nut") {
				tagSet["nuts"] = true
			}
			if strings.Contains(s, "fish") {
				tagSet["fish"] = true
			}
		}
	}
	var tags []string
	for t := range tagSet {
		tags = append(tags, t)
	}
	return tags
}

func mapProduct(raw map[string]interface{}) *domain.Product {
	name := getName(raw)
	if name == "" {
		return nil
	}
	nutriments, _ := raw["nutriments"].(map[string]interface{})
	if nutriments == nil {
		nutriments = raw
	}
	kcal := toFloat(nutriments["energy-kcal_100g"])
	if kcal == 0 {
		if e := toFloat(nutriments["energy_100g"]); e != 0 {
			kcal = e / 4.184
		}
	}
	categories := "other"
	if cat, ok := raw["categories"].(string); ok && cat != "" {
		categories = strings.Split(cat, ",")[0]
	}
	barcode := ""
	if code, ok := raw["code"].(string); ok {
		barcode = code
	} else if id, ok := raw["_id"].(string); ok {
		barcode = id
	}
	var barcodePtr *string
	if barcode != "" {
		barcodePtr = &barcode
	}
	return &domain.Product{
		Name:       name,
		Category:   strings.TrimSpace(categories),
		Kcal100:    kcal,
		Protein100: toFloat(nutriments["proteins_100g"]),
		Fat100:     toFloat(nutriments["fat_100g"]),
		Carbs100:   toFloat(nutriments["carbohydrates_100g"]),
		Tags:       inferTags(name, raw),
		OffBarcode: barcodePtr,
	}
}

func (c *Client) LookupBarcode(barcode string) *domain.Product {
	url := fmt.Sprintf(productURL, barcode)
	resp, err := c.httpClient.Get(url)
	if err != nil {
		return nil
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	var result map[string]interface{}
	if err := json.Unmarshal(body, &result); err != nil {
		return nil
	}
	product, _ := result["product"].(map[string]interface{})
	if product == nil {
		return nil
	}
	return mapProduct(product)
}

func (c *Client) SearchProducts(query string, limit int) []domain.Product {
	resp, err := c.httpClient.Get(searchURL + "?q=" + query + "&page_size=" + fmt.Sprintf("%d", limit) + "&lang=ru&fields=product_name,nutriments,code,categories,allergens_tags")
	if err != nil {
		return nil
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	var result map[string]interface{}
	if err := json.Unmarshal(body, &result); err != nil {
		return nil
	}
	hits, _ := result["hits"].([]interface{})
	var out []domain.Product
	seen := make(map[string]bool)
	for _, hit := range hits {
		raw, ok := hit.(map[string]interface{})
		if !ok {
			continue
		}
		p := mapProduct(raw)
		if p == nil || p.Kcal100 <= 0 {
			continue
		}
		key := strings.ToLower(strings.TrimSpace(p.Name))
		if seen[key] {
			continue
		}
		seen[key] = true
		p.ID = 0
		out = append(out, *p)
	}
	return out
}
