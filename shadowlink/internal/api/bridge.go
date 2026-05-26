package api

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sync"

	"github.com/user/shadowlink/internal/proxy"
)

// BridgeServer provides an HTTP API for Django integration.
// It runs on localhost only and handles user registration/deregistration.
type BridgeServer struct {
	tokens     map[string]*TokenInfo // auth_token -> info
	relay      *proxy.ServerRelay
	apiKey     string
	storePath  string
	mu         sync.RWMutex
}

type TokenInfo struct {
	Token    string `json:"token"`
	MaxConns int    `json:"max_conns"`
	Active   bool   `json:"active"`
}

func NewBridgeServer(apiKey string, relay *proxy.ServerRelay) *BridgeServer {
	bs := &BridgeServer{
		tokens:    make(map[string]*TokenInfo),
		relay:     relay,
		apiKey:    apiKey,
		storePath: "/opt/shadowlink/tokens.json",
	}
	bs.loadTokens()
	return bs
}

func (bs *BridgeServer) loadTokens() {
	data, err := os.ReadFile(bs.storePath)
	if err != nil {
		return
	}
	var tokens []*TokenInfo
	if err := json.Unmarshal(data, &tokens); err != nil {
		log.Printf("[bridge] failed to load tokens: %v", err)
		return
	}
	for _, t := range tokens {
		bs.tokens[t.Token] = t
	}
	log.Printf("[bridge] loaded %d tokens from disk", len(tokens))
}

func (bs *BridgeServer) saveTokens() {
	tokens := make([]*TokenInfo, 0, len(bs.tokens))
	for _, t := range bs.tokens {
		tokens = append(tokens, t)
	}
	data, err := json.MarshalIndent(tokens, "", "  ")
	if err != nil {
		log.Printf("[bridge] failed to marshal tokens: %v", err)
		return
	}
	os.MkdirAll(filepath.Dir(bs.storePath), 0755)
	if err := os.WriteFile(bs.storePath, data, 0600); err != nil {
		log.Printf("[bridge] failed to save tokens: %v", err)
	}
}

func (bs *BridgeServer) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if bs.apiKey != "" && r.Header.Get("X-API-Key") != bs.apiKey {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}

	switch r.URL.Path {
	case "/api/tokens":
		switch r.Method {
		case http.MethodPost:
			bs.registerToken(w, r)
		case http.MethodGet:
			bs.listTokens(w, r)
		default:
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	case "/api/tokens/delete":
		if r.Method == http.MethodPost {
			bs.deregisterToken(w, r)
		} else {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	case "/api/tokens/suspend":
		if r.Method == http.MethodPost {
			bs.suspendToken(w, r)
		} else {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	case "/api/tokens/activate":
		if r.Method == http.MethodPost {
			bs.activateToken(w, r)
		} else {
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	case "/api/status":
		bs.serverStatus(w, r)
	case "/api/sessions":
		bs.activeSessions(w, r)
	case "/api/health":
		bs.healthCheck(w, r)
	default:
		http.NotFound(w, r)
	}
}

func (bs *BridgeServer) registerToken(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Token    string `json:"token"`
		MaxConns int    `json:"max_conns"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid request body", http.StatusBadRequest)
		return
	}

	bs.mu.Lock()
	bs.tokens[req.Token] = &TokenInfo{
		Token:    req.Token,
		MaxConns: req.MaxConns,
		Active:   true,
	}
	bs.saveTokens()
	bs.mu.Unlock()

	log.Printf("[bridge] registered token: %.8s... (max_conns: %d)", req.Token, req.MaxConns)
	writeJSON(w, map[string]string{"status": "registered"})
}

func (bs *BridgeServer) deregisterToken(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Token string `json:"token"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid request body", http.StatusBadRequest)
		return
	}

	bs.mu.Lock()
	delete(bs.tokens, req.Token)
	bs.saveTokens()
	bs.mu.Unlock()

	log.Printf("[bridge] deregistered token: %.8s...", req.Token)
	writeJSON(w, map[string]string{"status": "deregistered"})
}

func (bs *BridgeServer) suspendToken(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Token string `json:"token"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid request body", http.StatusBadRequest)
		return
	}

	bs.mu.Lock()
	if info, ok := bs.tokens[req.Token]; ok {
		info.Active = false
		bs.saveTokens()
	}
	bs.mu.Unlock()

	writeJSON(w, map[string]string{"status": "suspended"})
}

func (bs *BridgeServer) activateToken(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Token string `json:"token"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "invalid request body", http.StatusBadRequest)
		return
	}

	bs.mu.Lock()
	if info, ok := bs.tokens[req.Token]; ok {
		info.Active = true
		bs.saveTokens()
	}
	bs.mu.Unlock()

	writeJSON(w, map[string]string{"status": "activated"})
}

func (bs *BridgeServer) listTokens(w http.ResponseWriter, r *http.Request) {
	bs.mu.RLock()
	tokens := make([]*TokenInfo, 0, len(bs.tokens))
	for _, t := range bs.tokens {
		tokens = append(tokens, t)
	}
	bs.mu.RUnlock()

	writeJSON(w, tokens)
}

func (bs *BridgeServer) serverStatus(w http.ResponseWriter, r *http.Request) {
	bs.mu.RLock()
	totalTokens := len(bs.tokens)
	activeTokens := 0
	for _, t := range bs.tokens {
		if t.Active {
			activeTokens++
		}
	}
	bs.mu.RUnlock()

	status := map[string]interface{}{
		"total_tokens":    totalTokens,
		"active_tokens":   activeTokens,
		"active_sessions": bs.relay.GetActiveSessions(),
	}
	writeJSON(w, status)
}

func (bs *BridgeServer) activeSessions(w http.ResponseWriter, r *http.Request) {
	sessions := bs.relay.GetActiveSessions()
	writeJSON(w, sessions)
}

func (bs *BridgeServer) healthCheck(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]string{"status": "ok"})
}

// AuthenticateToken is used by the relay to validate incoming connections.
func (bs *BridgeServer) AuthenticateToken(token string) (bool, int) {
	bs.mu.RLock()
	defer bs.mu.RUnlock()

	info, ok := bs.tokens[token]
	if !ok || !info.Active {
		return false, 0
	}
	return true, info.MaxConns
}

func writeJSON(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(data)
}
