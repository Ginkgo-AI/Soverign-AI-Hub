// Package config handles loading and persisting the edge agent configuration.
//
// Configuration is resolved in the following priority order (highest wins):
//
//  1. Environment variables (prefixed SOVEREIGN_EDGE_)
//  2. YAML config file (~/.sovereign-edge/config.yaml)
//  3. Compiled-in defaults
package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

// Config holds all edge agent settings.
type Config struct {
	HubURL       string        `yaml:"hub_url"`
	AgentID      string        `yaml:"agent_id"`
	AgentName    string        `yaml:"agent_name"`
	APIKey       string        `yaml:"api_key"`
	ModelPath    string        `yaml:"model_path"`
	DataDir      string        `yaml:"data_dir"`
	ListenAddr   string        `yaml:"listen_addr"`
	SyncInterval time.Duration `yaml:"sync_interval"`

	// LLM backend: "embedded" (shell out to llama-cli) or "remote" (HTTP to llama.cpp server)
	LLMBackend       string `yaml:"llm_backend"`
	LLMRemoteURL     string `yaml:"llm_remote_url"`
	LLMContextSize   int    `yaml:"llm_context_size"`
	LLMThreads       int    `yaml:"llm_threads"`
	LLMGPULayers     int    `yaml:"llm_gpu_layers"`
	DefaultModelFile string `yaml:"default_model_file"`

	// configPath is the file this config was loaded from.
	configPath string `yaml:"-"`
}

// DefaultConfigDir returns ~/.sovereign-edge.
func DefaultConfigDir() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ".sovereign-edge"
	}
	return filepath.Join(home, ".sovereign-edge")
}

// DefaultConfigPath returns ~/.sovereign-edge/config.yaml.
func DefaultConfigPath() string {
	return filepath.Join(DefaultConfigDir(), "config.yaml")
}

// defaults returns a Config populated with sensible standalone defaults.
func defaults() *Config {
	return &Config{
		HubURL:           "",
		AgentID:          "",
		AgentName:        "edge-agent",
		APIKey:           "",
		ModelPath:        filepath.Join(DefaultConfigDir(), "models"),
		DataDir:          filepath.Join(DefaultConfigDir(), "data"),
		ListenAddr:       "0.0.0.0:8899",
		SyncInterval:     5 * time.Minute,
		LLMBackend:       "embedded",
		LLMRemoteURL:     "http://127.0.0.1:8080",
		LLMContextSize:   4096,
		LLMThreads:       4,
		LLMGPULayers:     0,
		DefaultModelFile: "",
		configPath:       DefaultConfigPath(),
	}
}

// Load reads configuration from disk and environment.
func Load() (*Config, error) {
	cfg := defaults()

	// Try config file
	path := DefaultConfigPath()
	if envPath := os.Getenv("SOVEREIGN_EDGE_CONFIG"); envPath != "" {
		path = envPath
	}

	data, err := os.ReadFile(path)
	if err == nil {
		if err := yaml.Unmarshal(data, cfg); err != nil {
			return nil, fmt.Errorf("parse config %s: %w", path, err)
		}
		cfg.configPath = path
	}
	// Missing file is not an error — we use defaults.

	// Environment overrides
	applyEnv(cfg)

	// Ensure directories exist
	os.MkdirAll(cfg.DataDir, 0700)
	os.MkdirAll(cfg.ModelPath, 0700)

	return cfg, nil
}

// Save writes the current configuration to the YAML file it was loaded from.
func (c *Config) Save() error {
	dir := filepath.Dir(c.configPath)
	if err := os.MkdirAll(dir, 0700); err != nil {
		return fmt.Errorf("create config dir: %w", err)
	}
	data, err := yaml.Marshal(c)
	if err != nil {
		return fmt.Errorf("marshal config: %w", err)
	}
	return os.WriteFile(c.configPath, data, 0600)
}

// String returns a human-readable dump of all configuration keys.
func (c *Config) String() string {
	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("hub_url:            %s\n", c.HubURL))
	sb.WriteString(fmt.Sprintf("agent_id:           %s\n", c.AgentID))
	sb.WriteString(fmt.Sprintf("agent_name:         %s\n", c.AgentName))
	sb.WriteString(fmt.Sprintf("api_key:            %s\n", mask(c.APIKey)))
	sb.WriteString(fmt.Sprintf("model_path:         %s\n", c.ModelPath))
	sb.WriteString(fmt.Sprintf("data_dir:           %s\n", c.DataDir))
	sb.WriteString(fmt.Sprintf("listen_addr:        %s\n", c.ListenAddr))
	sb.WriteString(fmt.Sprintf("sync_interval:      %s\n", c.SyncInterval))
	sb.WriteString(fmt.Sprintf("llm_backend:        %s\n", c.LLMBackend))
	sb.WriteString(fmt.Sprintf("llm_remote_url:     %s\n", c.LLMRemoteURL))
	sb.WriteString(fmt.Sprintf("llm_context_size:   %d\n", c.LLMContextSize))
	sb.WriteString(fmt.Sprintf("llm_threads:        %d\n", c.LLMThreads))
	sb.WriteString(fmt.Sprintf("llm_gpu_layers:     %d\n", c.LLMGPULayers))
	sb.WriteString(fmt.Sprintf("default_model_file: %s\n", c.DefaultModelFile))
	return sb.String()
}

// Get returns a single config value by key name.
func (c *Config) Get(key string) (string, bool) {
	switch key {
	case "hub_url":
		return c.HubURL, true
	case "agent_id":
		return c.AgentID, true
	case "agent_name":
		return c.AgentName, true
	case "api_key":
		return mask(c.APIKey), true
	case "model_path":
		return c.ModelPath, true
	case "data_dir":
		return c.DataDir, true
	case "listen_addr":
		return c.ListenAddr, true
	case "sync_interval":
		return c.SyncInterval.String(), true
	case "llm_backend":
		return c.LLMBackend, true
	case "llm_remote_url":
		return c.LLMRemoteURL, true
	case "llm_context_size":
		return fmt.Sprintf("%d", c.LLMContextSize), true
	case "llm_threads":
		return fmt.Sprintf("%d", c.LLMThreads), true
	case "llm_gpu_layers":
		return fmt.Sprintf("%d", c.LLMGPULayers), true
	case "default_model_file":
		return c.DefaultModelFile, true
	default:
		return "", false
	}
}

// Set sets a single config value by key name.
func (c *Config) Set(key, value string) error {
	switch key {
	case "hub_url":
		c.HubURL = value
	case "agent_id":
		c.AgentID = value
	case "agent_name":
		c.AgentName = value
	case "api_key":
		c.APIKey = value
	case "model_path":
		c.ModelPath = value
	case "data_dir":
		c.DataDir = value
	case "listen_addr":
		c.ListenAddr = value
	case "sync_interval":
		d, err := time.ParseDuration(value)
		if err != nil {
			return fmt.Errorf("invalid duration: %w", err)
		}
		c.SyncInterval = d
	case "llm_backend":
		c.LLMBackend = value
	case "llm_remote_url":
		c.LLMRemoteURL = value
	case "llm_context_size":
		var n int
		if _, err := fmt.Sscanf(value, "%d", &n); err != nil {
			return fmt.Errorf("invalid integer: %w", err)
		}
		c.LLMContextSize = n
	case "llm_threads":
		var n int
		if _, err := fmt.Sscanf(value, "%d", &n); err != nil {
			return fmt.Errorf("invalid integer: %w", err)
		}
		c.LLMThreads = n
	case "llm_gpu_layers":
		var n int
		if _, err := fmt.Sscanf(value, "%d", &n); err != nil {
			return fmt.Errorf("invalid integer: %w", err)
		}
		c.LLMGPULayers = n
	case "default_model_file":
		c.DefaultModelFile = value
	default:
		return fmt.Errorf("unknown config key: %s", key)
	}
	return nil
}

// ---------------------------------------------------------------------------
// internal helpers
// ---------------------------------------------------------------------------

func applyEnv(cfg *Config) {
	envMap := map[string]*string{
		"SOVEREIGN_EDGE_HUB_URL":            &cfg.HubURL,
		"SOVEREIGN_EDGE_AGENT_ID":           &cfg.AgentID,
		"SOVEREIGN_EDGE_AGENT_NAME":         &cfg.AgentName,
		"SOVEREIGN_EDGE_API_KEY":            &cfg.APIKey,
		"SOVEREIGN_EDGE_MODEL_PATH":         &cfg.ModelPath,
		"SOVEREIGN_EDGE_DATA_DIR":           &cfg.DataDir,
		"SOVEREIGN_EDGE_LISTEN_ADDR":        &cfg.ListenAddr,
		"SOVEREIGN_EDGE_LLM_BACKEND":        &cfg.LLMBackend,
		"SOVEREIGN_EDGE_LLM_REMOTE_URL":     &cfg.LLMRemoteURL,
		"SOVEREIGN_EDGE_DEFAULT_MODEL_FILE": &cfg.DefaultModelFile,
	}
	for env, ptr := range envMap {
		if v := os.Getenv(env); v != "" {
			*ptr = v
		}
	}
	if v := os.Getenv("SOVEREIGN_EDGE_SYNC_INTERVAL"); v != "" {
		if d, err := time.ParseDuration(v); err == nil {
			cfg.SyncInterval = d
		}
	}
}

func mask(s string) string {
	if len(s) <= 8 {
		if s == "" {
			return "(not set)"
		}
		return "****"
	}
	return s[:4] + "****" + s[len(s)-4:]
}
