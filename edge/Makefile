# =============================================================================
# Sovereign Edge Agent — Build targets
# =============================================================================

BINARY := sovereign-edge
VERSION := 0.1.0
LDFLAGS := -ldflags="-s -w"

.PHONY: build build-all docker clean test

# Build for current platform
build:
	go build $(LDFLAGS) -o bin/$(BINARY) .

# Cross-compile for all supported platforms
build-all:
	@mkdir -p bin
	GOOS=linux   GOARCH=amd64 CGO_ENABLED=0 go build $(LDFLAGS) -o bin/$(BINARY)-linux-amd64 .
	GOOS=linux   GOARCH=arm64 CGO_ENABLED=0 go build $(LDFLAGS) -o bin/$(BINARY)-linux-arm64 .
	GOOS=darwin  GOARCH=amd64 CGO_ENABLED=0 go build $(LDFLAGS) -o bin/$(BINARY)-darwin-amd64 .
	GOOS=darwin  GOARCH=arm64 CGO_ENABLED=0 go build $(LDFLAGS) -o bin/$(BINARY)-darwin-arm64 .
	@echo "Built binaries in bin/"
	@ls -lh bin/

# Build Docker image
docker:
	docker build -t sovereign-edge:$(VERSION) -t sovereign-edge:latest .

# Run tests
test:
	go test ./... -v -race

# Clean build artifacts
clean:
	rm -rf bin/
	go clean
