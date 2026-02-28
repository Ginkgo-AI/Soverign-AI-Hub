# =============================================================================
# Sovereign Edge Agent — Multi-stage Docker build
# =============================================================================
# Build stage: compile a statically-linked Go binary
# Runtime stage: minimal Alpine image with just the binary
# =============================================================================

# -- Build stage --------------------------------------------------------------
FROM golang:1.22-alpine AS builder

RUN apk add --no-cache git

WORKDIR /src

# Cache dependencies
COPY go.mod go.sum ./
RUN go mod download

# Build
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build \
    -ldflags="-s -w -extldflags '-static'" \
    -o /sovereign-edge \
    .

# -- Runtime stage ------------------------------------------------------------
FROM alpine:3.19

RUN apk add --no-cache ca-certificates tzdata && \
    adduser -D -h /home/edge edge

COPY --from=builder /sovereign-edge /usr/local/bin/sovereign-edge

# Default config directory
RUN mkdir -p /home/edge/.sovereign-edge/data /home/edge/.sovereign-edge/models && \
    chown -R edge:edge /home/edge

USER edge
WORKDIR /home/edge

EXPOSE 8899

ENTRYPOINT ["sovereign-edge"]
CMD ["serve"]
