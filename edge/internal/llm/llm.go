// Package llm provides the LLM inference client for the edge agent.
//
// Two backends are supported:
//
//   - Embedded: shells out to the llama-cli binary with a local GGUF model file.
//   - Remote:   makes HTTP requests to a locally running llama.cpp server.
//
// Both backends produce OpenAI-compatible response structures.
package llm

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/sovereign-ai/edge/internal/config"
)

// Message represents a single chat message (OpenAI format).
type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// CompletionOpts holds optional parameters for a completion request.
type CompletionOpts struct {
	Model       string
	Temperature *float64
	MaxTokens   int
}

// ChatCompletionResponse mirrors the OpenAI chat completion response.
type ChatCompletionResponse struct {
	ID      string   `json:"id"`
	Object  string   `json:"object"`
	Created int64    `json:"created"`
	Model   string   `json:"model"`
	Choices []Choice `json:"choices"`
	Usage   *Usage   `json:"usage,omitempty"`
}

// Choice is a single completion choice.
type Choice struct {
	Index        int     `json:"index"`
	Message      Message `json:"message"`
	FinishReason string  `json:"finish_reason"`
}

// Usage reports token counts.
type Usage struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

// ModelInfo describes a locally available model.
type ModelInfo struct {
	Name    string    `json:"name"`
	Path    string    `json:"path"`
	Size    string    `json:"size"`
	ModTime time.Time `json:"modified"`
}

// Client is the edge LLM client.
type Client struct {
	cfg *config.Config
}

// New creates a new LLM Client.
func New(cfg *config.Config) *Client {
	return &Client{cfg: cfg}
}

// ChatCompletion performs a non-streaming chat completion.
func (c *Client) ChatCompletion(ctx context.Context, messages []Message, opts CompletionOpts) (*ChatCompletionResponse, error) {
	if c.cfg.LLMBackend == "remote" {
		return c.remoteCompletion(ctx, messages, opts)
	}
	return c.embeddedCompletion(ctx, messages, opts)
}

// ChatCompletionStream performs a streaming chat completion.
// Returns a channel of tokens and a channel for the final error.
func (c *Client) ChatCompletionStream(ctx context.Context, messages []Message, opts CompletionOpts) (<-chan string, <-chan error) {
	tokenCh := make(chan string, 64)
	errCh := make(chan error, 1)

	go func() {
		defer close(tokenCh)
		defer close(errCh)

		if c.cfg.LLMBackend == "remote" {
			errCh <- c.remoteStream(ctx, messages, opts, tokenCh)
		} else {
			errCh <- c.embeddedStream(ctx, messages, opts, tokenCh)
		}
	}()

	return tokenCh, errCh
}

// ListModels returns all GGUF models found in the model directory.
func (c *Client) ListModels() ([]ModelInfo, error) {
	var models []ModelInfo

	err := filepath.Walk(c.cfg.ModelPath, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return nil // skip errors
		}
		if info.IsDir() {
			return nil
		}
		if strings.HasSuffix(strings.ToLower(info.Name()), ".gguf") {
			models = append(models, ModelInfo{
				Name:    info.Name(),
				Path:    path,
				Size:    humanSize(info.Size()),
				ModTime: info.ModTime(),
			})
		}
		return nil
	})

	return models, err
}

// ResolveModelPath returns the full path to the requested model or the default.
func (c *Client) ResolveModelPath(modelName string) (string, error) {
	// If a specific model is requested, look for it
	if modelName != "" {
		models, _ := c.ListModels()
		for _, m := range models {
			if m.Name == modelName || strings.TrimSuffix(m.Name, ".gguf") == modelName {
				return m.Path, nil
			}
		}
	}

	// Try explicit default
	if c.cfg.DefaultModelFile != "" {
		path := c.cfg.DefaultModelFile
		if !filepath.IsAbs(path) {
			path = filepath.Join(c.cfg.ModelPath, path)
		}
		if _, err := os.Stat(path); err == nil {
			return path, nil
		}
	}

	// Fall back to first GGUF found
	models, _ := c.ListModels()
	if len(models) > 0 {
		return models[0].Path, nil
	}

	return "", fmt.Errorf("no model files found in %s", c.cfg.ModelPath)
}

// ---------------------------------------------------------------------------
// Embedded backend — shell out to llama-cli
// ---------------------------------------------------------------------------

func (c *Client) embeddedCompletion(ctx context.Context, messages []Message, opts CompletionOpts) (*ChatCompletionResponse, error) {
	modelPath, err := c.ResolveModelPath(opts.Model)
	if err != nil {
		return nil, err
	}

	prompt := buildPrompt(messages)

	args := []string{
		"-m", modelPath,
		"-p", prompt,
		"-n", fmt.Sprintf("%d", maxTokens(opts.MaxTokens, 512)),
		"--ctx-size", fmt.Sprintf("%d", c.cfg.LLMContextSize),
		"--threads", fmt.Sprintf("%d", c.cfg.LLMThreads),
		"--log-disable",
		"--no-display-prompt",
	}
	if c.cfg.LLMGPULayers > 0 {
		args = append(args, "--n-gpu-layers", fmt.Sprintf("%d", c.cfg.LLMGPULayers))
	}
	if opts.Temperature != nil {
		args = append(args, "--temp", fmt.Sprintf("%.2f", *opts.Temperature))
	}

	cmd := exec.CommandContext(ctx, "llama-cli", args...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	if err := cmd.Run(); err != nil {
		return nil, fmt.Errorf("llama-cli: %w — %s", err, stderr.String())
	}

	content := strings.TrimSpace(stdout.String())

	return &ChatCompletionResponse{
		ID:      fmt.Sprintf("chatcmpl-%d", time.Now().UnixNano()),
		Object:  "chat.completion",
		Created: time.Now().Unix(),
		Model:   filepath.Base(modelPath),
		Choices: []Choice{
			{
				Index:        0,
				Message:      Message{Role: "assistant", Content: content},
				FinishReason: "stop",
			},
		},
	}, nil
}

func (c *Client) embeddedStream(ctx context.Context, messages []Message, opts CompletionOpts, tokenCh chan<- string) error {
	modelPath, err := c.ResolveModelPath(opts.Model)
	if err != nil {
		return err
	}

	prompt := buildPrompt(messages)

	args := []string{
		"-m", modelPath,
		"-p", prompt,
		"-n", fmt.Sprintf("%d", maxTokens(opts.MaxTokens, 512)),
		"--ctx-size", fmt.Sprintf("%d", c.cfg.LLMContextSize),
		"--threads", fmt.Sprintf("%d", c.cfg.LLMThreads),
		"--log-disable",
		"--no-display-prompt",
	}
	if c.cfg.LLMGPULayers > 0 {
		args = append(args, "--n-gpu-layers", fmt.Sprintf("%d", c.cfg.LLMGPULayers))
	}
	if opts.Temperature != nil {
		args = append(args, "--temp", fmt.Sprintf("%.2f", *opts.Temperature))
	}

	cmd := exec.CommandContext(ctx, "llama-cli", args...)
	pipe, err := cmd.StdoutPipe()
	if err != nil {
		return fmt.Errorf("stdout pipe: %w", err)
	}
	cmd.Stderr = io.Discard

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("start llama-cli: %w", err)
	}

	scanner := bufio.NewScanner(pipe)
	scanner.Split(bufio.ScanRunes)
	for scanner.Scan() {
		tokenCh <- scanner.Text()
	}

	return cmd.Wait()
}

// ---------------------------------------------------------------------------
// Remote backend — HTTP to llama.cpp server
// ---------------------------------------------------------------------------

func (c *Client) remoteCompletion(ctx context.Context, messages []Message, opts CompletionOpts) (*ChatCompletionResponse, error) {
	body := map[string]interface{}{
		"model":    opts.Model,
		"messages": messages,
		"stream":   false,
	}
	if opts.Temperature != nil {
		body["temperature"] = *opts.Temperature
	}
	if opts.MaxTokens > 0 {
		body["max_tokens"] = opts.MaxTokens
	}

	data, _ := json.Marshal(body)

	url := strings.TrimRight(c.cfg.LLMRemoteURL, "/") + "/v1/chat/completions"
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(data))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("remote LLM request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		b, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("remote LLM returned %d: %s", resp.StatusCode, string(b))
	}

	var result ChatCompletionResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}
	return &result, nil
}

func (c *Client) remoteStream(ctx context.Context, messages []Message, opts CompletionOpts, tokenCh chan<- string) error {
	body := map[string]interface{}{
		"model":    opts.Model,
		"messages": messages,
		"stream":   true,
	}
	if opts.Temperature != nil {
		body["temperature"] = *opts.Temperature
	}
	if opts.MaxTokens > 0 {
		body["max_tokens"] = opts.MaxTokens
	}

	data, _ := json.Marshal(body)

	url := strings.TrimRight(c.cfg.LLMRemoteURL, "/") + "/v1/chat/completions"
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(data))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fmt.Errorf("remote LLM stream: %w", err)
	}
	defer resp.Body.Close()

	scanner := bufio.NewScanner(resp.Body)
	for scanner.Scan() {
		line := scanner.Text()
		if !strings.HasPrefix(line, "data: ") {
			continue
		}
		payload := strings.TrimPrefix(line, "data: ")
		if payload == "[DONE]" {
			break
		}

		var chunk struct {
			Choices []struct {
				Delta struct {
					Content string `json:"content"`
				} `json:"delta"`
			} `json:"choices"`
		}
		if err := json.Unmarshal([]byte(payload), &chunk); err != nil {
			continue
		}
		if len(chunk.Choices) > 0 && chunk.Choices[0].Delta.Content != "" {
			tokenCh <- chunk.Choices[0].Delta.Content
		}
	}

	return scanner.Err()
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func buildPrompt(messages []Message) string {
	var sb strings.Builder
	for _, m := range messages {
		switch m.Role {
		case "system":
			sb.WriteString(fmt.Sprintf("<|system|>\n%s\n", m.Content))
		case "user":
			sb.WriteString(fmt.Sprintf("<|user|>\n%s\n", m.Content))
		case "assistant":
			sb.WriteString(fmt.Sprintf("<|assistant|>\n%s\n", m.Content))
		}
	}
	sb.WriteString("<|assistant|>\n")
	return sb.String()
}

func maxTokens(requested, fallback int) int {
	if requested > 0 {
		return requested
	}
	return fallback
}

func humanSize(bytes int64) string {
	const (
		KB = 1024
		MB = KB * 1024
		GB = MB * 1024
	)
	switch {
	case bytes >= GB:
		return fmt.Sprintf("%.1f GB", float64(bytes)/float64(GB))
	case bytes >= MB:
		return fmt.Sprintf("%.1f MB", float64(bytes)/float64(MB))
	case bytes >= KB:
		return fmt.Sprintf("%.1f KB", float64(bytes)/float64(KB))
	default:
		return fmt.Sprintf("%d B", bytes)
	}
}
