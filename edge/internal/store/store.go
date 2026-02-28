// Package store manages the local SQLite database for the edge agent.
//
// It stores conversations, messages, knowledge chunks (with FTS5 full-text
// search), and sync state. The database file lives at <data_dir>/edge.db.
package store

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"path/filepath"
	"time"

	_ "modernc.org/sqlite"
)

// Store wraps a SQLite connection.
type Store struct {
	db *sql.DB
}

// Stats holds high-level storage statistics.
type Stats struct {
	Conversations   int `json:"conversations"`
	Messages        int `json:"messages"`
	KnowledgeChunks int `json:"knowledge_chunks"`
}

// KnowledgeChunk is a single piece of cached knowledge.
type KnowledgeChunk struct {
	ID           string `json:"id"`
	CollectionID string `json:"collection_id"`
	Content      string `json:"content"`
	Metadata     string `json:"metadata,omitempty"`
	CreatedAt    string `json:"created_at"`
}

// Conversation stored locally.
type Conversation struct {
	ID        string `json:"id"`
	Title     string `json:"title"`
	CreatedAt string `json:"created_at"`
	UpdatedAt string `json:"updated_at"`
	Synced    bool   `json:"synced"`
}

// ConversationMessage stored locally.
type ConversationMessage struct {
	ID             string `json:"id"`
	ConversationID string `json:"conversation_id"`
	Role           string `json:"role"`
	Content        string `json:"content"`
	CreatedAt      string `json:"created_at"`
}

// Open creates or opens the SQLite database and runs migrations.
func Open(dataDir string) (*Store, error) {
	dbPath := filepath.Join(dataDir, "edge.db")
	db, err := sql.Open("sqlite", dbPath+"?_journal_mode=WAL&_busy_timeout=5000")
	if err != nil {
		return nil, fmt.Errorf("open sqlite %s: %w", dbPath, err)
	}

	// Enable WAL mode for concurrent reads
	if _, err := db.Exec("PRAGMA journal_mode=WAL"); err != nil {
		db.Close()
		return nil, fmt.Errorf("set WAL: %w", err)
	}

	s := &Store{db: db}
	if err := s.migrate(); err != nil {
		db.Close()
		return nil, fmt.Errorf("migrate: %w", err)
	}

	return s, nil
}

// Close shuts down the database.
func (s *Store) Close() error {
	return s.db.Close()
}

// ---------------------------------------------------------------------------
// Schema / migration
// ---------------------------------------------------------------------------

func (s *Store) migrate() error {
	schema := `
	CREATE TABLE IF NOT EXISTS conversations (
		id         TEXT PRIMARY KEY,
		title      TEXT NOT NULL DEFAULT '',
		created_at TEXT NOT NULL DEFAULT (datetime('now')),
		updated_at TEXT NOT NULL DEFAULT (datetime('now')),
		synced     INTEGER NOT NULL DEFAULT 0
	);

	CREATE TABLE IF NOT EXISTS messages (
		id              TEXT PRIMARY KEY,
		conversation_id TEXT NOT NULL REFERENCES conversations(id),
		role            TEXT NOT NULL,
		content         TEXT NOT NULL,
		created_at      TEXT NOT NULL DEFAULT (datetime('now'))
	);
	CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);

	CREATE TABLE IF NOT EXISTS knowledge_chunks (
		id            TEXT PRIMARY KEY,
		collection_id TEXT NOT NULL DEFAULT '',
		content       TEXT NOT NULL,
		metadata      TEXT DEFAULT '{}',
		created_at    TEXT NOT NULL DEFAULT (datetime('now'))
	);

	CREATE TABLE IF NOT EXISTS sync_log (
		id           INTEGER PRIMARY KEY AUTOINCREMENT,
		resource     TEXT NOT NULL,
		last_sync_at TEXT NOT NULL,
		items_count  INTEGER NOT NULL DEFAULT 0,
		direction    TEXT NOT NULL DEFAULT 'pull',
		status       TEXT NOT NULL DEFAULT 'success',
		error        TEXT DEFAULT ''
	);

	CREATE TABLE IF NOT EXISTS sync_state (
		resource     TEXT PRIMARY KEY,
		last_sync_at TEXT NOT NULL
	);
	`

	if _, err := s.db.Exec(schema); err != nil {
		return err
	}

	// Create FTS5 virtual table for knowledge search (idempotent)
	fts := `
	CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
		id UNINDEXED,
		content,
		content=knowledge_chunks,
		content_rowid=rowid
	);
	`
	_, _ = s.db.Exec(fts) // Ignore error if FTS5 not available

	// Triggers to keep FTS in sync
	triggers := []string{
		`CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge_chunks BEGIN
			INSERT INTO knowledge_fts(rowid, id, content)
			VALUES (new.rowid, new.id, new.content);
		END;`,
		`CREATE TRIGGER IF NOT EXISTS knowledge_ad AFTER DELETE ON knowledge_chunks BEGIN
			INSERT INTO knowledge_fts(knowledge_fts, rowid, id, content)
			VALUES ('delete', old.rowid, old.id, old.content);
		END;`,
	}
	for _, t := range triggers {
		_, _ = s.db.Exec(t)
	}

	return nil
}

// ---------------------------------------------------------------------------
// Conversations
// ---------------------------------------------------------------------------

// msgAdapter is used to decode messages passed as interface{} from the LLM layer.
type msgAdapter struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// SaveConversationExchange persists a user/assistant exchange.
// The messages parameter accepts any JSON-serialisable slice with Role/Content fields.
func (s *Store) SaveConversationExchange(messages interface{}, assistantReply string) error {
	data, err := json.Marshal(messages)
	if err != nil {
		return err
	}
	var msgs []msgAdapter
	if err := json.Unmarshal(data, &msgs); err != nil {
		return err
	}

	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	convID := generateID()
	now := time.Now().UTC().Format(time.RFC3339)

	title := "Untitled"
	for _, m := range msgs {
		if m.Role == "user" {
			title = truncate(m.Content, 80)
			break
		}
	}

	_, err = tx.Exec(
		"INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
		convID, title, now, now,
	)
	if err != nil {
		return err
	}

	for _, m := range msgs {
		_, err = tx.Exec(
			"INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
			generateID(), convID, m.Role, m.Content, now,
		)
		if err != nil {
			return err
		}
	}

	_, err = tx.Exec(
		"INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
		generateID(), convID, "assistant", assistantReply, now,
	)
	if err != nil {
		return err
	}

	return tx.Commit()
}

// GetUnsyncedConversations returns conversations not yet synced to the hub.
func (s *Store) GetUnsyncedConversations() ([]Conversation, error) {
	rows, err := s.db.Query(
		"SELECT id, title, created_at, updated_at, synced FROM conversations WHERE synced = 0 ORDER BY created_at",
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var convs []Conversation
	for rows.Next() {
		var c Conversation
		var synced int
		if err := rows.Scan(&c.ID, &c.Title, &c.CreatedAt, &c.UpdatedAt, &synced); err != nil {
			return nil, err
		}
		c.Synced = synced != 0
		convs = append(convs, c)
	}
	return convs, rows.Err()
}

// GetConversationMessages returns all messages for a conversation.
func (s *Store) GetConversationMessages(convID string) ([]ConversationMessage, error) {
	rows, err := s.db.Query(
		"SELECT id, conversation_id, role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at",
		convID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var msgs []ConversationMessage
	for rows.Next() {
		var m ConversationMessage
		if err := rows.Scan(&m.ID, &m.ConversationID, &m.Role, &m.Content, &m.CreatedAt); err != nil {
			return nil, err
		}
		msgs = append(msgs, m)
	}
	return msgs, rows.Err()
}

// MarkConversationSynced marks a conversation as uploaded to the hub.
func (s *Store) MarkConversationSynced(convID string) error {
	_, err := s.db.Exec("UPDATE conversations SET synced = 1 WHERE id = ?", convID)
	return err
}

// SaveConversation inserts a conversation downloaded from the hub.
func (s *Store) SaveConversation(conv Conversation) error {
	_, err := s.db.Exec(
		"INSERT OR IGNORE INTO conversations (id, title, created_at, updated_at, synced) VALUES (?, ?, ?, ?, 1)",
		conv.ID, conv.Title, conv.CreatedAt, conv.UpdatedAt,
	)
	return err
}

// SaveMessage inserts a message downloaded from the hub.
func (s *Store) SaveMessage(msg ConversationMessage) error {
	_, err := s.db.Exec(
		"INSERT OR IGNORE INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
		msg.ID, msg.ConversationID, msg.Role, msg.Content, msg.CreatedAt,
	)
	return err
}

// ---------------------------------------------------------------------------
// Knowledge
// ---------------------------------------------------------------------------

// UpsertKnowledgeChunk inserts or replaces a knowledge chunk.
func (s *Store) UpsertKnowledgeChunk(chunk KnowledgeChunk) error {
	_, err := s.db.Exec(
		`INSERT OR REPLACE INTO knowledge_chunks (id, collection_id, content, metadata, created_at)
		 VALUES (?, ?, ?, ?, ?)`,
		chunk.ID, chunk.CollectionID, chunk.Content, chunk.Metadata, chunk.CreatedAt,
	)
	return err
}

// SearchKnowledge performs a full-text search on cached knowledge chunks.
func (s *Store) SearchKnowledge(query string, limit int) ([]KnowledgeChunk, error) {
	// Try FTS5 first
	rows, err := s.db.Query(
		`SELECT kc.id, kc.collection_id, kc.content, kc.metadata, kc.created_at
		 FROM knowledge_fts fts
		 JOIN knowledge_chunks kc ON kc.id = fts.id
		 WHERE knowledge_fts MATCH ?
		 ORDER BY rank
		 LIMIT ?`,
		query, limit,
	)
	if err != nil {
		// Fallback to LIKE search if FTS5 is not available
		rows, err = s.db.Query(
			`SELECT id, collection_id, content, metadata, created_at
			 FROM knowledge_chunks
			 WHERE content LIKE ?
			 ORDER BY created_at DESC
			 LIMIT ?`,
			"%"+query+"%", limit,
		)
		if err != nil {
			return nil, err
		}
	}
	defer rows.Close()

	var chunks []KnowledgeChunk
	for rows.Next() {
		var c KnowledgeChunk
		if err := rows.Scan(&c.ID, &c.CollectionID, &c.Content, &c.Metadata, &c.CreatedAt); err != nil {
			return nil, err
		}
		chunks = append(chunks, c)
	}
	return chunks, rows.Err()
}

// GetKnowledgeCount returns the total number of knowledge chunks.
func (s *Store) GetKnowledgeCount() (int, error) {
	var count int
	err := s.db.QueryRow("SELECT COUNT(*) FROM knowledge_chunks").Scan(&count)
	return count, err
}

// ---------------------------------------------------------------------------
// Sync state
// ---------------------------------------------------------------------------

// SetSyncTimestamp records the last sync time for a resource type.
func (s *Store) SetSyncTimestamp(resource string, ts time.Time) error {
	_, err := s.db.Exec(
		`INSERT OR REPLACE INTO sync_state (resource, last_sync_at) VALUES (?, ?)`,
		resource, ts.UTC().Format(time.RFC3339),
	)
	return err
}

// GetSyncTimestamp returns the last sync time for a resource type.
func (s *Store) GetSyncTimestamp(resource string) (time.Time, error) {
	var ts string
	err := s.db.QueryRow("SELECT last_sync_at FROM sync_state WHERE resource = ?", resource).Scan(&ts)
	if err != nil {
		return time.Time{}, err
	}
	return time.Parse(time.RFC3339, ts)
}

// GetSyncState returns all sync timestamps.
func (s *Store) GetSyncState() (map[string]string, error) {
	rows, err := s.db.Query("SELECT resource, last_sync_at FROM sync_state")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	state := make(map[string]string)
	for rows.Next() {
		var resource, ts string
		if err := rows.Scan(&resource, &ts); err != nil {
			return nil, err
		}
		state[resource] = ts
	}
	return state, rows.Err()
}

// LogSync records a sync event.
func (s *Store) LogSync(resource, direction, status string, count int, syncErr string) error {
	_, err := s.db.Exec(
		`INSERT INTO sync_log (resource, last_sync_at, items_count, direction, status, error)
		 VALUES (?, datetime('now'), ?, ?, ?, ?)`,
		resource, count, direction, status, syncErr,
	)
	return err
}

// ---------------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------------

// GetStats returns storage statistics.
func (s *Store) GetStats() (Stats, error) {
	var stats Stats

	s.db.QueryRow("SELECT COUNT(*) FROM conversations").Scan(&stats.Conversations)
	s.db.QueryRow("SELECT COUNT(*) FROM messages").Scan(&stats.Messages)
	s.db.QueryRow("SELECT COUNT(*) FROM knowledge_chunks").Scan(&stats.KnowledgeChunks)

	return stats, nil
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func generateID() string {
	return fmt.Sprintf("%d-%d", time.Now().UnixNano(), time.Now().UnixNano()%1000000)
}

func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen-3] + "..."
}
