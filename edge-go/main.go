package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"io"
	"log"
	"net/http"
	"os"
	"time"
)

const contractVersion = "v1"

type proxyConfig struct {
	client         *http.Client
	upstream       string
	shadowEnabled  bool
	shadowUpstream string
}

func main() {
	addr := env("EDGE_ADDR", ":8081")
	upstreamPrimary := env("EDGE_UPSTREAM_PRIMARY", "http://localhost:8000")
	upstreamShadow := os.Getenv("EDGE_UPSTREAM_SHADOW")
	shadowEnabled := os.Getenv("EDGE_SHADOW_ENABLED") == "true"

	client := &http.Client{
		Timeout: 120 * time.Second,
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("x-contract-version", contractVersion)
		_, _ = w.Write([]byte(`{"status":"ok","contract_version":"v1"}`))
	})
	cfg := proxyConfig{
		client:         client,
		upstream:       upstreamPrimary,
		shadowEnabled:  shadowEnabled,
		shadowUpstream: upstreamShadow,
	}
	mux.HandleFunc("/", cfg.dispatch)

	log.Printf("edge server listening on %s primary=%s shadow=%t", addr, upstreamPrimary, shadowEnabled)
	if err := http.ListenAndServe(addr, withMiddleware(mux)); err != nil {
		log.Fatal(err)
	}
}

func withMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestID := r.Header.Get("x-request-id")
		if requestID == "" {
			requestID = generateRequestID()
		}
		w.Header().Set("x-request-id", requestID)
		w.Header().Set("x-contract-version", contractVersion)
		next.ServeHTTP(w, r.WithContext(r.Context()))
	})
}

func (cfg proxyConfig) dispatch(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/chat/stream" {
		cfg.proxyStream(w, r)
		return
	}
	if !isAllowedPath(r.URL.Path) {
		http.NotFound(w, r)
		return
	}
	cfg.proxyHTTP(w, r)
}

func isAllowedPath(path string) bool {
	switch {
	case path == "/status", path == "/chat", path == "/contracts/version", path == "/features":
		return true
	case path == "/docs", path == "/redoc", path == "/openapi.json", path == "/docs/oauth2-redirect":
		return true
	case len(path) >= len("/spaces/") && path[:len("/spaces/")] == "/spaces/":
		return true
	case len(path) >= len("/threads/") && path[:len("/threads/")] == "/threads/":
		return true
	case len(path) >= len("/settings/") && path[:len("/settings/")] == "/settings/":
		return true
	case len(path) >= len("/workflow/") && path[:len("/workflow/")] == "/workflow/":
		return true
	case path == "/obsidian/context/session", path == "/obsidian/context/events", path == "/obsidian/context/heartbeat":
		return true
	case len(path) >= len("/obsidian/") && path[:len("/obsidian/")] == "/obsidian/":
		return true
	case len(path) >= len("/mem0/") && path[:len("/mem0/")] == "/mem0/":
		return true
	case len(path) >= len("/internal/boundary/") && path[:len("/internal/boundary/")] == "/internal/boundary/":
		return true
	default:
		return false
	}
}

func (cfg proxyConfig) proxyHTTP(w http.ResponseWriter, r *http.Request) {
	targetURL := cfg.upstream + r.URL.Path
	if r.URL.RawQuery != "" {
		targetURL += "?" + r.URL.RawQuery
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "failed to read request body", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	if cfg.shadowEnabled && cfg.shadowUpstream != "" {
		shadowURL := cfg.shadowUpstream + r.URL.Path
		if r.URL.RawQuery != "" {
			shadowURL += "?" + r.URL.RawQuery
		}
		go fireShadowRequest(cfg.client, r.Context(), r.Header, r.Method, shadowURL, body)
	}

	req, err := http.NewRequestWithContext(r.Context(), r.Method, targetURL, bytes.NewReader(body))
	if err != nil {
		http.Error(w, "failed to build upstream request", http.StatusInternalServerError)
		return
	}
	copyHeaders(req.Header, r.Header)
	resp, err := cfg.client.Do(req)
	if err != nil {
		http.Error(w, "upstream request failed", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	copyHeaders(w.Header(), resp.Header)
	w.Header().Set("x-contract-version", contractVersion)
	w.WriteHeader(resp.StatusCode)
	_, _ = io.Copy(w, resp.Body)
}

func (cfg proxyConfig) proxyStream(w http.ResponseWriter, r *http.Request) {
	targetURL := cfg.upstream + r.URL.Path
	if r.URL.RawQuery != "" {
		targetURL += "?" + r.URL.RawQuery
	}
	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "failed to read request body", http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	req, err := http.NewRequestWithContext(r.Context(), r.Method, targetURL, bytes.NewReader(body))
	if err != nil {
		http.Error(w, "failed to build upstream request", http.StatusInternalServerError)
		return
	}
	copyHeaders(req.Header, r.Header)
	resp, err := cfg.client.Do(req)
	if err != nil {
		http.Error(w, "upstream request failed", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	copyHeaders(w.Header(), resp.Header)
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("x-contract-version", contractVersion)
	w.WriteHeader(resp.StatusCode)
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming unsupported", http.StatusInternalServerError)
		return
	}
	buf := make([]byte, 4096)
	for {
		n, readErr := resp.Body.Read(buf)
		if n > 0 {
			_, _ = w.Write(buf[:n])
			flusher.Flush()
		}
		if readErr != nil {
			if readErr == io.EOF {
				return
			}
			http.Error(w, "stream interrupted", http.StatusBadGateway)
			return
		}
	}
}

func fireShadowRequest(client *http.Client, ctx context.Context, headers http.Header, method string, shadowURL string, body []byte) {
	req, err := http.NewRequestWithContext(ctx, method, shadowURL, bytes.NewReader(body))
	if err != nil {
		log.Printf("shadow request build failed: %v", err)
		return
	}
	copyHeaders(req.Header, headers)
	req.Header.Set("x-shadow-request", "true")
	req.Header.Set("x-shadow-request-id", generateRequestID())
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("shadow request failed: %v", err)
		return
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, resp.Body)
	log.Printf("shadow request %s status=%d", shadowURL, resp.StatusCode)
}

func copyHeaders(dst, src http.Header) {
	for key, values := range src {
		for _, value := range values {
			dst.Add(key, value)
		}
	}
}

func env(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func generateRequestID() string {
	raw := make([]byte, 8)
	if _, err := rand.Read(raw); err != nil {
		return "edge-fallback-id"
	}
	return hex.EncodeToString(raw)
}
