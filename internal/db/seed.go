package db

import (
	"context"
	"database/sql"
	"strings"

	"pandabook/internal/db/storage"
)

type CatalogItem struct {
	Name     string
	Category string
	Kcal     float64
	Protein  float64
	Fat      float64
	Carbs    float64
	Tags     []string
}

var Catalog = []CatalogItem{
	{"Куриная грудка", "meat", 165, 31, 3.6, 0, []string{"meat"}},
	{"Говядина", "meat", 250, 26, 15, 0, []string{"meat"}},
	{"Свинина", "meat", 242, 27, 14, 0, []string{"meat", "pork"}},
	{"Лосось", "fish", 208, 20, 13, 0, []string{"fish"}},
	{"Тунец консерв.", "fish", 116, 26, 1, 0, []string{"fish"}},
	{"Яйцо куриное", "egg", 155, 13, 11, 1.1, []string{"egg"}},
	{"Творог 5%", "dairy", 121, 17, 5, 3, []string{"dairy"}},
	{"Молоко 2.5%", "dairy", 52, 2.8, 2.5, 4.7, []string{"dairy"}},
	{"Йогурт натур.", "dairy", 60, 5, 3.2, 4, []string{"dairy"}},
	{"Сыр твёрдый", "dairy", 364, 25, 29, 2, []string{"dairy"}},
	{"Овсянка", "grain", 366, 12, 6, 62, []string{"gluten"}},
	{"Гречка", "grain", 343, 13, 3.4, 62, []string{}},
	{"Рис белый", "grain", 344, 6.7, 0.7, 78, []string{}},
	{"Макароны", "grain", 371, 13, 1.5, 75, []string{"gluten"}},
	{"Хлеб цельнозерн.", "grain", 247, 9, 3.4, 47, []string{"gluten"}},
	{"Картофель", "veg", 77, 2, 0.4, 17, []string{}},
	{"Брокколи", "veg", 34, 2.8, 0.4, 7, []string{}},
	{"Помидор", "veg", 18, 0.9, 0.2, 3.9, []string{}},
	{"Огурец", "veg", 15, 0.7, 0.1, 3.6, []string{}},
	{"Морковь", "veg", 41, 0.9, 0.2, 10, []string{}},
	{"Шпинат", "veg", 23, 2.9, 0.4, 3.6, []string{}},
	{"Банан", "fruit", 89, 1.1, 0.3, 23, []string{}},
	{"Яблоко", "fruit", 52, 0.3, 0.2, 14, []string{}},
	{"Авокадо", "fruit", 160, 2, 15, 9, []string{}},
	{"Фасоль", "legume", 333, 21, 2, 54, []string{}},
	{"Чечевица", "legume", 352, 24, 1.5, 63, []string{}},
	{"Нут", "legume", 364, 19, 6, 61, []string{}},
	{"Тофу", "legume", 76, 8, 4.8, 1.9, []string{}},
	{"Миндаль", "nuts", 579, 21, 50, 22, []string{"nuts"}},
	{"Оливковое масло", "fat", 884, 0, 100, 0, []string{}},
	{"Сливочное масло", "fat", 717, 0.9, 81, 0.1, []string{"dairy"}},
	{"Мёд", "sweet", 304, 0.3, 0, 82, []string{"honey"}},
}

func SeedProducts(ctx context.Context, queries *storage.Queries) error {
	count, err := queries.GetProductCount(ctx)
	if err != nil {
		return err
	}
	if count > 0 {
		return nil
	}
	for _, item := range Catalog {
		tagsCsv := strings.Join(item.Tags, ",")
		_, err := queries.CreateProduct(ctx, storage.CreateProductParams{
			Name:       item.Name,
			Category:   item.Category,
			Kcal100:    item.Kcal,
			Protein100: item.Protein,
			Fat100:     item.Fat,
			Carbs100:   item.Carbs,
			TagsCsv:    tagsCsv,
			OffBarcode: sql.NullString{Valid: false},
		})
		if err != nil {
			return err
		}
	}
	return nil
}
