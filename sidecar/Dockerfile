# syntax=docker/dockerfile:1.7
# Multi-stage build for the AgentBreeder sidecar binary.
#
# Stage 1 builds a static Go binary; stage 2 ships it on distroless.
# Final image is < 20 MB and supports linux/amd64 + linux/arm64.

ARG GO_VERSION=1.22

# --- builder ----------------------------------------------------------------
FROM --platform=$BUILDPLATFORM golang:${GO_VERSION}-alpine AS builder

ARG TARGETOS
ARG TARGETARCH
ARG VERSION=dev

WORKDIR /src

# Copy go.mod / go.sum first for better layer caching.
COPY go.mod go.sum ./
RUN go mod download

COPY . .

# Build a fully-static binary.
RUN CGO_ENABLED=0 GOOS=${TARGETOS:-linux} GOARCH=${TARGETARCH:-amd64} \
    go build \
        -trimpath \
        -ldflags="-s -w -X main.version=${VERSION}" \
        -o /out/sidecar \
        ./cmd/sidecar

# --- runtime ----------------------------------------------------------------
FROM gcr.io/distroless/static-debian12:nonroot

LABEL org.opencontainers.image.title="agentbreeder-sidecar"
LABEL org.opencontainers.image.source="https://github.com/agentbreeder/agentbreeder"
LABEL org.opencontainers.image.description="AgentBreeder cross-cutting concerns sidecar (tracing, cost, A2A, MCP, guardrails)"
LABEL org.opencontainers.image.licenses="Apache-2.0"

COPY --from=builder /out/sidecar /sidecar

# Public ingress (proxy → agent on :8081)
EXPOSE 8080
# Local helper endpoints (a2a + mcp + cost on the same port by default)
EXPOSE 9090

USER nonroot:nonroot

ENTRYPOINT ["/sidecar"]
