// Package chat provides an interactive terminal-based chat interface for the
// edge agent. It reads from stdin, streams tokens to stdout, and supports
// built-in slash commands.
package chat

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"strings"

	"github.com/sovereign-ai/edge/internal/config"
	"github.com/sovereign-ai/edge/internal/llm"
	"github.com/sovereign-ai/edge/internal/store"
	syncclient "github.com/sovereign-ai/edge/internal/sync"
)

// Chat manages the interactive CLI session.
type Chat struct {
	cfg     *config.Config
	db      *store.Store
	llm     *llm.Client
	syncMgr *syncclient.Manager
	history []llm.Message
	model   string
}

// New creates a new Chat instance.
func New(cfg *config.Config, db *store.Store, llmClient *llm.Client, syncMgr *syncclient.Manager) *Chat {
	return &Chat{
		cfg:     cfg,
		db:      db,
		llm:     llmClient,
		syncMgr: syncMgr,
	}
}

// Run starts the interactive chat loop. It blocks until the user quits.
func (c *Chat) Run() {
	fmt.Println("Sovereign Edge Agent — Interactive Chat")
	fmt.Println("Type /help for commands, /quit to exit.")
	fmt.Println()

	// Try to identify the current model
	if models, err := c.llm.ListModels(); err == nil && len(models) > 0 {
		c.model = models[0].Name
		fmt.Printf("Model: %s\n\n", c.model)
	}

	scanner := bufio.NewScanner(os.Stdin)
	for {
		fmt.Print("you> ")
		if !scanner.Scan() {
			break
		}

		input := strings.TrimSpace(scanner.Text())
		if input == "" {
			continue
		}

		// Handle commands
		if strings.HasPrefix(input, "/") {
			if c.handleCommand(input) {
				break // /quit
			}
			continue
		}

		// Add user message
		c.history = append(c.history, llm.Message{Role: "user", Content: input})

		// Stream completion
		fmt.Print("assistant> ")
		ctx := context.Background()
		opts := llm.CompletionOpts{Model: c.model}
		tokenCh, errCh := c.llm.ChatCompletionStream(ctx, c.history, opts)

		var fullReply strings.Builder

		streaming := true
		for streaming {
			select {
			case token, ok := <-tokenCh:
				if !ok {
					streaming = false
					break
				}
				fmt.Print(token)
				fullReply.WriteString(token)
			case err := <-errCh:
				if err != nil {
					fmt.Printf("\n[error: %v]\n", err)
				}
				streaming = false
			}
		}
		fmt.Println()
		fmt.Println()

		// Add assistant reply to history
		reply := strings.TrimSpace(fullReply.String())
		if reply != "" {
			c.history = append(c.history, llm.Message{Role: "assistant", Content: reply})

			// Persist conversation
			go c.db.SaveConversationExchange(c.history, reply)
		}
	}
}

// handleCommand processes a slash command. Returns true if the session should end.
func (c *Chat) handleCommand(cmd string) bool {
	parts := strings.Fields(cmd)
	switch parts[0] {
	case "/quit", "/exit", "/q":
		fmt.Println("Goodbye.")
		return true

	case "/clear":
		c.history = nil
		fmt.Println("[conversation cleared]")

	case "/status":
		stats, _ := c.db.GetStats()
		syncState, _ := c.db.GetSyncState()
		fmt.Printf("Agent:          %s (%s)\n", c.cfg.AgentName, c.cfg.AgentID)
		fmt.Printf("Model:          %s\n", c.model)
		fmt.Printf("Conversations:  %d local\n", stats.Conversations)
		fmt.Printf("Messages:       %d local\n", stats.Messages)
		fmt.Printf("Knowledge:      %d chunks\n", stats.KnowledgeChunks)
		fmt.Printf("History:        %d messages in current session\n", len(c.history))
		if len(syncState) > 0 {
			fmt.Println("Sync state:")
			for r, ts := range syncState {
				fmt.Printf("  %-16s %s\n", r+":", ts)
			}
		}

	case "/sync":
		fmt.Print("Syncing with hub... ")
		result, err := c.syncMgr.SyncAll(context.Background())
		if err != nil {
			fmt.Printf("error: %v\n", err)
		} else {
			fmt.Printf("done (%d up, %d knowledge chunks)\n",
				result.ConversationsUploaded, result.KnowledgeChunksDownloaded)
		}

	case "/model":
		if len(parts) > 1 {
			c.model = parts[1]
			fmt.Printf("[model set to %s]\n", c.model)
		} else {
			models, err := c.llm.ListModels()
			if err != nil {
				fmt.Printf("[error listing models: %v]\n", err)
			} else if len(models) == 0 {
				fmt.Println("[no models available]")
			} else {
				fmt.Println("Available models:")
				for _, m := range models {
					marker := " "
					if m.Name == c.model {
						marker = "*"
					}
					fmt.Printf("  %s %s (%s)\n", marker, m.Name, m.Size)
				}
			}
		}

	case "/help":
		fmt.Println("Commands:")
		fmt.Println("  /quit    — exit chat")
		fmt.Println("  /clear   — clear conversation history")
		fmt.Println("  /status  — show agent status")
		fmt.Println("  /sync    — trigger hub sync")
		fmt.Println("  /model   — list models or set active model (/model <name>)")
		fmt.Println("  /help    — show this help")

	default:
		fmt.Printf("[unknown command: %s — type /help]\n", parts[0])
	}

	return false
}
