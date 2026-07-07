package http

import (
	"fmt"
	"strings"
)

func fmtFloat(f float64) string {
	return fmt.Sprintf("%.0f", f)
}

func stringsJoin(s []string, sep string) string {
	return strings.Join(s, sep)
}
