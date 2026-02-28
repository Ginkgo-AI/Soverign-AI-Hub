// Sovereign AI Hub — Edge Agent
//
// A lightweight, self-contained agent for disconnected and resource-constrained
// environments. Provides local LLM inference, knowledge caching, and
// opportunistic synchronisation with the central hub.
package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"strings"
	"syscall"

	"github.com/sovereign-ai/edge/internal/chat"
	"github.com/sovereign-ai/edge/internal/config"
	"github.com/sovereign-ai/edge/internal/llm"
	"github.com/sovereign-ai/edge/internal/server"
	"github.com/sovereign-ai/edge/internal/store"
	"github.com/sovereign-ai/edge/internal/sync"
)

const version = "0.1.0"

func main() {
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(1)
	}

	cmd := os.Args[1]
	switch cmd {
	case "serve":
		runServe()
	case "sync":
		runSync()
	case "chat":
		runChat()
	case "status":
		runStatus()
	case "config":
		runConfig()
	case "version":
		fmt.Printf("sovereign-edge %s\n", version)
	case "help", "--help", "-h":
		printUsage()
	default:
		fmt.Fprintf(os.Stderr, "Unknown command: %s\n\n", cmd)
		printUsage()
		os.Exit(1)
	}
}

func printUsage() {
	fmt.Println(`Sovereign AI Hub — Edge Agent

Usage:
  sovereign-edge <command> [flags]

Commands:
  serve    Start the local HTTP API server
  sync     Manually trigger synchronisation with the hub
  chat     Interactive CLI chat mode
  status   Show agent status (model, sync state, storage)
  config   Show or set configuration values
  version  Print version
  help     Show this help

Use "sovereign-edge <command> --help" for more information about a command.`)
}

// ---------------------------------------------------------------------------
// serve
// ---------------------------------------------------------------------------

func runServe() {
	cfg, err := config.Load()
	if err != nil {
		fatal("load config: %v", err)
	}

	db, err := store.Open(cfg.DataDir)
	if err != nil {
		fatal("open store: %v", err)
	}
	defer db.Close()

	llmClient := llm.New(cfg)

	syncMgr := sync.NewManager(cfg, db)

	// Start periodic sync in background
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	go syncMgr.StartPeriodicSync(ctx)

	srv := server.New(cfg, db, llmClient, syncMgr)

	// Graceful shutdown
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-sigCh
		fmt.Println("\nShutting down...")
		cancel()
		srv.Shutdown()
	}()

	fmt.Printf("Sovereign Edge Agent v%s — listening on %s\n", version, cfg.ListenAddr)
	if err := srv.ListenAndServe(); err != nil {
		fatal("server: %v", err)
	}
}

// ---------------------------------------------------------------------------
// sync
// ---------------------------------------------------------------------------

func runSync() {
	cfg, err := config.Load()
	if err != nil {
		fatal("load config: %v", err)
	}

	db, err := store.Open(cfg.DataDir)
	if err != nil {
		fatal("open store: %v", err)
	}
	defer db.Close()

	mgr := sync.NewManager(cfg, db)
	fmt.Println("Starting synchronisation with hub...")
	result, err := mgr.SyncAll(context.Background())
	if err != nil {
		fatal("sync: %v", err)
	}

	fmt.Printf("Sync complete:\n")
	fmt.Printf("  Conversations: %d uploaded, %d downloaded\n",
		result.ConversationsUploaded, result.ConversationsDownloaded)
	fmt.Printf("  Knowledge:     %d chunks downloaded\n", result.KnowledgeChunksDownloaded)
	fmt.Printf("  Config:        %s\n", boolLabel(result.ConfigUpdated, "updated", "unchanged"))
}

// ---------------------------------------------------------------------------
// chat
// ---------------------------------------------------------------------------

func runChat() {
	cfg, err := config.Load()
	if err != nil {
		fatal("load config: %v", err)
	}

	db, err := store.Open(cfg.DataDir)
	if err != nil {
		fatal("open store: %v", err)
	}
	defer db.Close()

	llmClient := llm.New(cfg)
	syncMgr := sync.NewManager(cfg, db)

	c := chat.New(cfg, db, llmClient, syncMgr)
	c.Run()
}

// ---------------------------------------------------------------------------
// status
// ---------------------------------------------------------------------------

func runStatus() {
	cfg, err := config.Load()
	if err != nil {
		fatal("load config: %v", err)
	}

	db, err := store.Open(cfg.DataDir)
	if err != nil {
		fatal("open store: %v", err)
	}
	defer db.Close()

	llmClient := llm.New(cfg)

	fmt.Printf("Sovereign Edge Agent v%s\n", version)
	fmt.Printf("Agent ID:    %s\n", cfg.AgentID)
	fmt.Printf("Agent Name:  %s\n", cfg.AgentName)
	fmt.Printf("Hub URL:     %s\n", valueOrDefault(cfg.HubURL, "(not configured)"))
	fmt.Printf("Listen:      %s\n", cfg.ListenAddr)
	fmt.Printf("Data Dir:    %s\n", cfg.DataDir)
	fmt.Printf("Model Path:  %s\n", cfg.ModelPath)
	fmt.Println()

	// Model status
	models, _ := llmClient.ListModels()
	if len(models) > 0 {
		fmt.Printf("Models available: %d\n", len(models))
		for _, m := range models {
			fmt.Printf("  - %s (%s)\n", m.Name, m.Size)
		}
	} else {
		fmt.Println("Models available: none")
	}
	fmt.Println()

	// Sync state
	syncState, err := db.GetSyncState()
	if err == nil && syncState != nil {
		fmt.Printf("Last sync:\n")
		for resource, ts := range syncState {
			fmt.Printf("  %-16s %s\n", resource+":", ts)
		}
	} else {
		fmt.Println("Last sync: never")
	}
	fmt.Println()

	// Storage stats
	stats, _ := db.GetStats()
	fmt.Printf("Storage:\n")
	fmt.Printf("  Conversations:    %d\n", stats.Conversations)
	fmt.Printf("  Messages:         %d\n", stats.Messages)
	fmt.Printf("  Knowledge Chunks: %d\n", stats.KnowledgeChunks)
}

// ---------------------------------------------------------------------------
// config
// ---------------------------------------------------------------------------

func runConfig() {
	cfg, err := config.Load()
	if err != nil {
		fatal("load config: %v", err)
	}

	args := os.Args[2:]
	if len(args) == 0 {
		// Print all config
		fmt.Println(cfg.String())
		return
	}

	if len(args) == 1 {
		// Get single key
		val, ok := cfg.Get(args[0])
		if !ok {
			fatal("unknown config key: %s", args[0])
		}
		fmt.Println(val)
		return
	}

	if len(args) == 2 {
		// Set key=value
		key := args[0]
		value := args[1]
		if err := cfg.Set(key, value); err != nil {
			fatal("set config: %v", err)
		}
		if err := cfg.Save(); err != nil {
			fatal("save config: %v", err)
		}
		fmt.Printf("%s = %s\n", key, value)
		return
	}

	fmt.Fprintln(os.Stderr, "Usage: sovereign-edge config [key] [value]")
	os.Exit(1)
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

func fatal(format string, args ...interface{}) {
	fmt.Fprintf(os.Stderr, "Error: "+format+"\n", args...)
	os.Exit(1)
}

func boolLabel(b bool, trueLabel, falseLabel string) string {
	if b {
		return trueLabel
	}
	return falseLabel
}

func valueOrDefault(s, def string) string {
	if strings.TrimSpace(s) == "" {
		return def
	}
	return s
}
