package config

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type Config struct {
	Root    string
	DataDir string
	DBPath  string
	Host    string
	Port    int
	CORS    []string
}

func Load() Config {
	root := strings.TrimSpace(os.Getenv("QUESTS_ROOT"))
	if root == "" {
		root = findRepoRoot()
	}
	data := strings.TrimSpace(os.Getenv("QUESTS_DATA_DIR"))
	if data == "" {
		data = filepath.Join(root, "data")
	}
	host := strings.TrimSpace(os.Getenv("QUESTS_HOST"))
	if host == "" {
		host = "127.0.0.1"
	}
	port := 8765
	if raw := strings.TrimSpace(os.Getenv("QUESTS_PORT")); raw != "" {
		if n, err := strconv.Atoi(raw); err == nil && n > 0 {
			port = n
		}
	}
	cors := []string{"http://127.0.0.1:5173", "http://localhost:5173"}
	if raw := strings.TrimSpace(os.Getenv("QUESTS_CORS_ORIGINS")); raw != "" {
		cors = nil
		for _, o := range strings.Split(raw, ",") {
			o = strings.TrimSpace(o)
			if o != "" {
				cors = append(cors, o)
			}
		}
	}
	return Config{
		Root:    root,
		DataDir: data,
		DBPath:  filepath.Join(data, "quests.db"),
		Host:    host,
		Port:    port,
		CORS:    cors,
	}
}

func findRepoRoot() string {
	wd, err := os.Getwd()
	if err != nil {
		return "."
	}
	dir := wd
	for {
		if _, err := os.Stat(filepath.Join(dir, "pyproject.toml")); err == nil {
			return dir
		}
		if _, err := os.Stat(filepath.Join(dir, "go", "go.mod")); err == nil {
			return dir
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return wd
}

func (c Config) Addr() string {
	return c.Host + ":" + strconv.Itoa(c.Port)
}
