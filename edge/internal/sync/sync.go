// Package sync manages bidirectional data synchronisation between the edge
// agent and the central Sovereign AI Hub.
//
// The sync protocol is designed to be idempotent and tolerant of intermittent
// connectivity. When the hub is unreachable the agent continues to operate
// normally; sync will resume automatically on the next successful connection.
package sync

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"strings"
	"time"

	"github.com/sovereign-ai/edge/internal/config"
	"github.com/sovereign-ai/edge/internal/store"
)

// SyncResult summarises what happened during a full sync cycle.
type SyncResult struct {
	ConversationsUploaded    int  `json:"conversations_uploaded"`
	ConversationsDownloaded  int  `json:"conversations_downloaded"`
	KnowledgeChunksDownloaded int `json:"knowledge_chunks_downloaded"`
	ConfigUpdated            bool `json:"config_updated"`
	Error                    string `json:"error,omitempty"`
}

// Manager coordinates all sync operations.
type Manager struct {
	cfg    *config.Config
	db     *store.Store
	client *http.Client
}

// NewManager creates a sync manager.
func NewManager(cfg *config.Config, db *store.Store) *Manager {
	return &Manager{
		cfg: cfg,
		db:  db,
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// StartPeriodicSync runs sync on a timer until the context is cancelled.
func (m *Manager) StartPeriodicSync(ctx context.Context) {
	if m.cfg.SyncInterval <= 0 || m.cfg.HubURL == "" {
		return
	}
	ticker := time.NewTicker(m.cfg.SyncInterval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if _, err := m.SyncAll(ctx); err != nil {
				// Log but do not crash — sync is best-effort.
				fmt.Printf("[sync] error: %v\n", err)
			}
		}
	}
}

// SyncAll performs a full bidirectional sync cycle.
func (m *Manager) SyncAll(ctx context.Context) (*SyncResult, error) {
	if m.cfg.HubURL == "" {
		return &SyncResult{Error: "hub_url not configured"}, nil
	}

	result := &SyncResult{}

	// 1. Upload conversations
	uploaded, err := m.SyncConversationsUp(ctx)
	if err != nil {
		result.Error = fmt.Sprintf("conversations up: %v", err)
	}
	result.ConversationsUploaded = uploaded

	// 2. Download knowledge deltas
	chunks, err := m.SyncKnowledge(ctx)
	if err != nil && result.Error == "" {
		result.Error = fmt.Sprintf("knowledge: %v", err)
	}
	result.KnowledgeChunksDownloaded = chunks

	// 3. Pull config/policy
	updated, err := m.SyncConfig(ctx)
	if err != nil && result.Error == "" {
		result.Error = fmt.Sprintf("config: %v", err)
	}
	result.ConfigUpdated = updated

	// 4. Check for model updates (metadata only)
	_ = m.SyncModels(ctx)

	return result, nil
}

// ---------------------------------------------------------------------------
// Conversations: upload local to hub
// ---------------------------------------------------------------------------

// SyncConversationsUp uploads un-synced conversations to the hub.
func (m *Manager) SyncConversationsUp(ctx context.Context) (int, error) {
	convs, err := m.db.GetUnsyncedConversations()
	if err != nil {
		return 0, fmt.Errorf("get unsynced: %w", err)
	}

	if len(convs) == 0 {
		return 0, nil
	}

	uploaded := 0
	for _, conv := range convs {
		msgs, err := m.db.GetConversationMessages(conv.ID)
		if err != nil {
			continue
		}

		payload := map[string]interface{}{
			"agent_id":     m.cfg.AgentID,
			"conversation": conv,
			"messages":     msgs,
		}

		err = m.hubPost(ctx, "/api/edge/sync/conversations", payload)
		if err != nil {
			m.db.LogSync("conversations", "push", "error", 0, err.Error())
			return uploaded, fmt.Errorf("upload conversation %s: %w", conv.ID, err)
		}

		m.db.MarkConversationSynced(conv.ID)
		uploaded++
	}

	now := time.Now()
	m.db.SetSyncTimestamp("conversations_up", now)
	m.db.LogSync("conversations", "push", "success", uploaded, "")

	return uploaded, nil
}

// ---------------------------------------------------------------------------
// Knowledge: download deltas from hub
// ---------------------------------------------------------------------------

// SyncKnowledge downloads new knowledge chunks from the hub since last sync.
func (m *Manager) SyncKnowledge(ctx context.Context) (int, error) {
	since, _ := m.db.GetSyncTimestamp("knowledge")
	sinceStr := ""
	if !since.IsZero() {
		sinceStr = since.UTC().Format(time.RFC3339)
	}

	url := fmt.Sprintf("/api/edge/sync/knowledge?agent_id=%s&since=%s", m.cfg.AgentID, sinceStr)

	body, err := m.hubGet(ctx, url)
	if err != nil {
		m.db.LogSync("knowledge", "pull", "error", 0, err.Error())
		return 0, err
	}

	var resp struct {
		Chunks []store.KnowledgeChunk `json:"chunks"`
	}
	if err := json.Unmarshal(body, &resp); err != nil {
		return 0, fmt.Errorf("decode knowledge response: %w", err)
	}

	for _, chunk := range resp.Chunks {
		if err := m.db.UpsertKnowledgeChunk(chunk); err != nil {
			continue
		}
	}

	now := time.Now()
	m.db.SetSyncTimestamp("knowledge", now)
	m.db.LogSync("knowledge", "pull", "success", len(resp.Chunks), "")

	return len(resp.Chunks), nil
}

// ---------------------------------------------------------------------------
// Config: pull policy updates
// ---------------------------------------------------------------------------

// SyncConfig pulls the latest configuration/policy from the hub.
func (m *Manager) SyncConfig(ctx context.Context) (bool, error) {
	url := fmt.Sprintf("/api/edge/sync/config?agent_id=%s", m.cfg.AgentID)
	body, err := m.hubGet(ctx, url)
	if err != nil {
		return false, err
	}

	var resp struct {
		Version string `json:"config_version"`
		// Additional policy fields would be parsed here
	}
	if err := json.Unmarshal(body, &resp); err != nil {
		return false, fmt.Errorf("decode config response: %w", err)
	}

	m.db.SetSyncTimestamp("config", time.Now())
	m.db.LogSync("config", "pull", "success", 0, "")

	return resp.Version != "", nil
}

// ---------------------------------------------------------------------------
// Models: check for updates (metadata only)
// ---------------------------------------------------------------------------

// SyncModels checks for available model updates on the hub.
func (m *Manager) SyncModels(ctx context.Context) error {
	url := fmt.Sprintf("/api/edge/sync/models?agent_id=%s", m.cfg.AgentID)
	_, err := m.hubGet(ctx, url)
	if err != nil {
		return err
	}

	m.db.SetSyncTimestamp("models", time.Now())
	return nil
}

// ---------------------------------------------------------------------------
// HTTP helpers with retry + backoff
// ---------------------------------------------------------------------------

func (m *Manager) hubPost(ctx context.Context, path string, payload interface{}) error {
	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	var lastErr error
	for attempt := 0; attempt < 3; attempt++ {
		if attempt > 0 {
			backoff := time.Duration(math.Pow(2, float64(attempt))) * time.Second
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-time.After(backoff):
			}
		}

		url := strings.TrimRight(m.cfg.HubURL, "/") + path
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(data))
		if err != nil {
			return err
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-Edge-Agent-ID", m.cfg.AgentID)
		if m.cfg.APIKey != "" {
			req.Header.Set("Authorization", "Bearer "+m.cfg.APIKey)
		}

		resp, err := m.client.Do(req)
		if err != nil {
			lastErr = err
			continue
		}
		resp.Body.Close()

		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			return nil
		}
		lastErr = fmt.Errorf("hub returned %d", resp.StatusCode)
	}

	return fmt.Errorf("after retries: %w", lastErr)
}

func (m *Manager) hubGet(ctx context.Context, path string) ([]byte, error) {
	var lastErr error
	for attempt := 0; attempt < 3; attempt++ {
		if attempt > 0 {
			backoff := time.Duration(math.Pow(2, float64(attempt))) * time.Second
			select {
			case <-ctx.Done():
				return nil, ctx.Err()
			case <-time.After(backoff):
			}
		}

		url := strings.TrimRight(m.cfg.HubURL, "/") + path
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
		if err != nil {
			return nil, err
		}
		req.Header.Set("X-Edge-Agent-ID", m.cfg.AgentID)
		if m.cfg.APIKey != "" {
			req.Header.Set("Authorization", "Bearer "+m.cfg.APIKey)
		}

		resp, err := m.client.Do(req)
		if err != nil {
			lastErr = err
			continue
		}
		defer resp.Body.Close()

		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			return io.ReadAll(resp.Body)
		}
		lastErr = fmt.Errorf("hub returned %d", resp.StatusCode)
	}

	return nil, fmt.Errorf("after retries: %w", lastErr)
}
