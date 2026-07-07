package integrations

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strings"

	"pandabook/internal/domain"
)

type LLMClient struct {
	apiKey  string
	baseURL string
	model   string
	client  *http.Client
}

func NewLLMClient(apiKey, baseURL, model string) *LLMClient {
	if baseURL == "" {
		baseURL = "https://api.openai.com/v1"
	}
	if model == "" {
		model = "pandabook-pro"
	}
	return &LLMClient{
		apiKey:  apiKey,
		baseURL: strings.TrimRight(baseURL, "/"),
		model:   model,
		client:  &http.Client{},
	}
}

type llmMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type llmRequest struct {
	Model       string       `json:"model"`
	Messages    []llmMessage `json:"messages"`
	Temperature float64      `json:"temperature"`
	MaxTokens   int          `json:"max_tokens"`
}

type llmResponse struct {
	Choices []struct {
		Message struct {
			Content   string `json:"content"`
			Reasoning string `json:"reasoning,omitempty"`
		} `json:"message"`
	} `json:"choices"`
}

func (c *LLMClient) chat(messages []llmMessage, maxTokens int) (string, error) {
	if c.apiKey == "" {
		return "", fmt.Errorf("no api key")
	}
	body := llmRequest{
		Model:       c.model,
		Messages:    messages,
		Temperature: 0.7,
		MaxTokens:   maxTokens,
	}
	data, _ := json.Marshal(body)
	req, err := http.NewRequest("POST", c.baseURL+"/chat/completions", bytes.NewReader(data))
	if err != nil {
		return "", err
	}
	req.Header.Set("Authorization", "Bearer "+c.apiKey)
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	respBody, _ := io.ReadAll(resp.Body)
	var result llmResponse
	if err := json.Unmarshal(respBody, &result); err != nil {
		return "", err
	}
	if len(result.Choices) == 0 {
		return "", fmt.Errorf("no choices in response")
	}
	return result.Choices[0].Message.Content, nil
}

func extractJSONContent(msg map[string]interface{}) string {
	content, _ := msg["content"].(string)
	content = strings.TrimSpace(content)
	if content != "" {
		return content
	}
	reasoning, _ := msg["reasoning"].(string)
	patterns := []string{
		`\{"items"\s*:\s*\[\s*\]\s*\}`,
		`\{"items"\s*:\s*\[.*?\]\s*\}`,
		`\{"title"\s*:.*?"steps"\s*:\s*\[.*?\]\s*\}`,
	}
	for _, pattern := range patterns {
		re := regexp.MustCompile(pattern)
		matches := re.FindAllString(reasoning, -1)
		if len(matches) > 0 {
			return matches[len(matches)-1]
		}
	}
	return ""
}

func (c *LLMClient) SuggestRecipe(ingredients []string) domain.Recipe {
	messages := []llmMessage{
		{Role: "system", Content: "Ты шеф-повар. По списку продуктов предложи ОДИН вариант приёма пищи. Если это сырые ингредиенты — дай рецепт блюда. Если продукты уже готовые (суп, борщ, консервы, полуфабрикаты) — предложи, как их удобно скомбинировать и подать, без лишних шагов. Не добавляй продуктов, которых нет в списке (допустимы только базовые специи, соль, масло, вода). Верни СТРОГО JSON без markdown по схеме: {\"title\": строка, \"ingredients\": [строки], \"steps\": [строки]}. Пиши по-русски."},
		{Role: "user", Content: "Ингредиенты: " + strings.Join(ingredients, ", ")},
	}
	content, err := c.chat(messages, 2000)
	if err != nil {
		return domain.Recipe{Title: "Рецепт временно недоступен", Ingredients: ingredients}
	}
	var recipe domain.Recipe
	if err := json.Unmarshal([]byte(content), &recipe); err != nil {
		return domain.Recipe{Title: "Рецепт временно недоступен", Ingredients: ingredients}
	}
	if recipe.Title == "" {
		recipe.Title = "Рецепт"
	}
	return recipe
}

func (c *LLMClient) ExplainPlan(summary string) string {
	messages := []llmMessage{
		{Role: "system", Content: "Ты персональный диетолог. Объясни коротко (2-3 предложения, простым языком, без markdown), почему составленный рацион подходит под цель пользователя. Если пользователь оставил пожелание — учти его в ответе."},
		{Role: "user", Content: summary},
	}
	content, err := c.chat(messages, 1500)
	if err != nil {
		return ""
	}
	return strings.TrimSpace(content)
}

func (c *LLMClient) SuggestShoppingList(context string) *[]domain.ShoppingItem {
	messages := []llmMessage{
		{Role: "system", Content: "Ты персональный диетолог и помощник по закупкам. Составь список докупок на ОДИН день.\n\nСТРОГИЕ ПРАВИЛА:\n1. Верни ТОЛЬКО JSON без markdown: {\"items\":[{\"product_name\":\"...\",\"grams\":123,\"reason\":\"...\"}]}\n2. product_name — конкретный продукт из обычного российского магазина.\n3. grams — целое число граммов (не штуки, не упаковки).\n4. reason — одно короткое предложение: зачем именно этот продукт (дефицит макроса, замена скоропортящемуся, разнообразие и т.д.).\n5. Учитывай цель (похудеть/поддерживать/набрать), диет-ограничения и аллергены.\n6. ЗАПРЕЩЕНО включать продукты из блока «УЖЕ ЕСТЬ В ХОЛОДИЛЬНИКЕ» — даже под другим названием.\n7. Докупай только то, чего нет дома, чтобы дополнить рацион и закрыть дефицит.\n8. Если дома уже есть макароны/каша/рис — НЕ докупай углеводы; предложи белок, овощи и жиры К НИМ.\n9. Подстраивайся под реальное содержимое холодильника, а не выдавай один и тот же шаблон.\n10. От 1 до 6 позиций. Если докупать нечего — {\"items\":[]}.\n11. Пиши по-русски. Только реалистичные продукты из обычного магазина."},
		{Role: "user", Content: context},
	}
	content, err := c.chat(messages, 1200)
	if err != nil {
		return nil
	}
	var result struct {
		Items []struct {
			ProductName string  `json:"product_name"`
			Grams       float64 `json:"grams"`
			Reason      string  `json:"reason"`
		} `json:"items"`
	}
	if err := json.Unmarshal([]byte(content), &result); err != nil {
		return nil
	}
	var items []domain.ShoppingItem
	for _, raw := range result.Items {
		name := strings.TrimSpace(raw.ProductName)
		if name != "" && raw.Grams > 0 && strings.TrimSpace(raw.Reason) != "" {
			items = append(items, domain.ShoppingItem{
				ProductName: name,
				Grams:       raw.Grams,
				Reason:      strings.TrimSpace(raw.Reason),
			})
		}
	}
	return &items
}
