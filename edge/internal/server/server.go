// Package server implements the lightweight HTTP API for the edge agent.
//
// It exposes OpenAI-compatible endpoints alongside management routes so that
// existing client libraries (e.g. the OpenAI Python SDK) work out of the box.
package server

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/sovereign-ai/edge/internal/config"
	"github.com/sovereign-ai/edge/internal/llm"
	"github.com/sovereign-ai/edge/internal/store"
	"github.com/sovereign-ai/edge/internal/sync"
)

// Server wraps the standard library HTTP server.
type Server struct {
	cfg     *config.Config
	db      *store.Store
	llm     *llm.Client
	syncMgr *sync.Manager
	srv     *http.Server
}

// New creates a Server wired to the provided dependencies.
func New(cfg *config.Config, db *store.Store, llmClient *llm.Client, syncMgr *sync.Manager) *Server {
	s := &Server{
		cfg:     cfg,
		db:      db,
		llm:     llmClient,
		syncMgr: syncMgr,
	}

	mux := http.NewServeMux()

	// OpenAI-compatible
	mux.HandleFunc("POST /v1/chat/completions", s.withAuth(s.handleChatCompletions))
	mux.HandleFunc("GET /v1/models", s.withAuth(s.handleListModels))

	// Management
	mux.HandleFunc("POST /api/search", s.withAuth(s.handleSearch))
	mux.HandleFunc("GET /api/status", s.withAuth(s.handleStatus))
	mux.HandleFunc("POST /api/sync", s.withAuth(s.handleSync))

	// Health (no auth)
	mux.HandleFunc("GET /health", s.handleHealth)

	handler := s.corsMiddleware(mux)

	s.srv = &http.Server{
		Addr:         cfg.ListenAddr,
		Handler:      handler,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 120 * time.Second,
		IdleTimeout:  60 * time.Second,
	}
	return s
}

// ListenAndServe starts serving HTTP traffic.
func (s *Server) ListenAndServe() error {
	err := s.srv.ListenAndServe()
	if err == http.ErrServerClosed {
		return nil
	}
	return err
}

// Shutdown gracefully stops the server.
func (s *Server) Shutdown() {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	s.srv.Shutdown(ctx)
}

// ---------------------------------------------------------------------------
// Middleware
// ---------------------------------------------------------------------------

func (s *Server) withAuth(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if s.cfg.APIKey == "" {
			next(w, r)
			return
		}
		auth := r.Header.Get("Authorization")
		token := strings.TrimPrefix(auth, "Bearer ")
		if token == "" || token != s.cfg.APIKey {
			writeJSON(w, http.StatusUnauthorized, map[string]string{"error": "unauthorized"})
			return
		}
		next(w, r)
	}
}

func (s *Server) corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

// ChatCompletionRequest mirrors the relevant parts of the OpenAI request.
type ChatCompletionRequest struct {
	Model       string        `json:"model"`
	Messages    []llm.Message `json:"messages"`
	Temperature *float64      `json:"temperature,omitempty"`
	MaxTokens   int           `json:"max_tokens,omitempty"`
	Stream      bool          `json:"stream,omitempty"`
}

func (s *Server) handleChatCompletions(w http.ResponseWriter, r *http.Request) {
	var req ChatCompletionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid JSON: " + err.Error()})
		return
	}

	if len(req.Messages) == 0 {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "messages must not be empty"})
		return
	}

	opts := llm.CompletionOpts{
		Model:       req.Model,
		Temperature: req.Temperature,
		MaxTokens:   req.MaxTokens,
	}

	if req.Stream {
		s.handleStreamingCompletion(w, req.Messages, opts)
		return
	}

	resp, err := s.llm.ChatCompletion(r.Context(), req.Messages, opts)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}

	// Store the conversation
	go s.storeConversation(req.Messages, resp)

	writeJSON(w, http.StatusOK, resp)
}

func (s *Server) handleStreamingCompletion(w http.ResponseWriter, messages []llm.Message, opts llm.CompletionOpts) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "streaming not supported"})
		return
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	ctx := context.Background()
	tokenCh, errCh := s.llm.ChatCompletionStream(ctx, messages, opts)

	var fullContent strings.Builder

	for {
		select {
		case token, ok := <-tokenCh:
			if !ok {
				// Stream ended
				fmt.Fprintf(w, "data: [DONE]\n\n")
				flusher.Flush()

				// Store conversation with accumulated content
				go func() {
					resp := &llm.ChatCompletionResponse{
						ID:      fmt.Sprintf("chatcmpl-%d", time.Now().UnixNano()),
						Object:  "chat.completion",
						Created: time.Now().Unix(),
						Model:   opts.Model,
						Choices: []llm.Choice{
							{
								Index:        0,
								Message:      llm.Message{Role: "assistant", Content: fullContent.String()},
								FinishReason: "stop",
							},
						},
					}
					s.storeConversation(messages, resp)
				}()
				return
			}
			fullContent.WriteString(token)
			chunk := map[string]interface{}{
				"id":      fmt.Sprintf("chatcmpl-%d", time.Now().UnixNano()),
				"object":  "chat.completion.chunk",
				"created": time.Now().Unix(),
				"model":   opts.Model,
				"choices": []map[string]interface{}{
					{
						"index": 0,
						"delta": map[string]string{"content": token},
					},
				},
			}
			data, _ := json.Marshal(chunk)
			fmt.Fprintf(w, "data: %s\n\n", data)
			flusher.Flush()

		case err := <-errCh:
			if err != nil {
				errChunk := map[string]string{"error": err.Error()}
				data, _ := json.Marshal(errChunk)
				fmt.Fprintf(w, "data: %s\n\n", data)
				flusher.Flush()
			}
			return
		}
	}
}

func (s *Server) handleListModels(w http.ResponseWriter, r *http.Request) {
	models, err := s.llm.ListModels()
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}

	type modelEntry struct {
		ID      string `json:"id"`
		Object  string `json:"object"`
		Created int64  `json:"created"`
		OwnedBy string `json:"owned_by"`
	}

	entries := make([]modelEntry, len(models))
	for i, m := range models {
		entries[i] = modelEntry{
			ID:      m.Name,
			Object:  "model",
			Created: m.ModTime.Unix(),
			OwnedBy: "local",
		}
	}

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"object": "list",
		"data":   entries,
	})
}

func (s *Server) handleSearch(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Query string `json:"query"`
		Limit int    `json:"limit,omitempty"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid JSON"})
		return
	}
	if req.Query == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "query is required"})
		return
	}
	if req.Limit <= 0 {
		req.Limit = 10
	}

	results, err := s.db.SearchKnowledge(req.Query, req.Limit)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"query":   req.Query,
		"results": results,
	})
}

func (s *Server) handleStatus(w http.ResponseWriter, r *http.Request) {
	models, _ := s.llm.ListModels()
	stats, _ := s.db.GetStats()
	syncState, _ := s.db.GetSyncState()

	writeJSON(w, http.StatusOK, map[string]interface{}{
		"agent_id":   s.cfg.AgentID,
		"agent_name": s.cfg.AgentName,
		"version":    "0.1.0",
		"models":     models,
		"storage":    stats,
		"sync_state": syncState,
		"hub_url":    s.cfg.HubURL,
	})
}

func (s *Server) handleSync(w http.ResponseWriter, r *http.Request) {
	result, err := s.syncMgr.SyncAll(r.Context())
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, result)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func (s *Server) storeConversation(messages []llm.Message, resp *llm.ChatCompletionResponse) {
	if resp == nil || len(resp.Choices) == 0 {
		return
	}
	// Fire-and-forget persistence for the exchange
	_ = s.db.SaveConversationExchange(messages, resp.Choices[0].Message.Content)
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}
