package protocol

import (
	"errors"
	"net"
	"sync"
	"time"
)

type SessionState int

const (
	SessionStateNew SessionState = iota
	SessionStateHandshaking
	SessionStateActive
	SessionStateClosed
)

type Session struct {
	ID         string
	AuthToken  string
	Cipher     *SessionCipher
	State      SessionState
	CreatedAt  time.Time
	LastActive time.Time
	ClientAddr net.Addr
	mu         sync.RWMutex
}

func NewSession(id string, clientAddr net.Addr) *Session {
	now := time.Now()
	return &Session{
		ID:         id,
		State:      SessionStateNew,
		CreatedAt:  now,
		LastActive: now,
		ClientAddr: clientAddr,
	}
}

func (s *Session) SetCipher(cipher *SessionCipher) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.Cipher = cipher
}

func (s *Session) SetState(state SessionState) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.State = state
}

func (s *Session) GetState() SessionState {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.State
}

func (s *Session) Touch() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.LastActive = time.Now()
}

func (s *Session) IsExpired(timeout time.Duration) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return time.Since(s.LastActive) > timeout
}

// SessionManager tracks all active sessions.
type SessionManager struct {
	sessions      map[string]*Session
	tokenSessions map[string][]*Session // auth_token -> sessions
	maxPerToken   int
	mu            sync.RWMutex
}

func NewSessionManager(maxPerToken int) *SessionManager {
	return &SessionManager{
		sessions:      make(map[string]*Session),
		tokenSessions: make(map[string][]*Session),
		maxPerToken:   maxPerToken,
	}
}

func (sm *SessionManager) Add(s *Session) error {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	if s.AuthToken != "" && sm.maxPerToken > 0 {
		existing := sm.tokenSessions[s.AuthToken]
		active := 0
		for _, es := range existing {
			if es.GetState() == SessionStateActive {
				active++
			}
		}
		if active >= sm.maxPerToken {
			return errors.New("max concurrent sessions exceeded for this token")
		}
	}

	sm.sessions[s.ID] = s
	if s.AuthToken != "" {
		sm.tokenSessions[s.AuthToken] = append(sm.tokenSessions[s.AuthToken], s)
	}
	return nil
}

func (sm *SessionManager) Remove(id string) {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	s, exists := sm.sessions[id]
	if !exists {
		return
	}

	delete(sm.sessions, id)

	if s.AuthToken != "" {
		sessions := sm.tokenSessions[s.AuthToken]
		filtered := make([]*Session, 0, len(sessions))
		for _, es := range sessions {
			if es.ID != id {
				filtered = append(filtered, es)
			}
		}
		if len(filtered) == 0 {
			delete(sm.tokenSessions, s.AuthToken)
		} else {
			sm.tokenSessions[s.AuthToken] = filtered
		}
	}
}

func (sm *SessionManager) Get(id string) (*Session, bool) {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	s, ok := sm.sessions[id]
	return s, ok
}

func (sm *SessionManager) CountByToken(token string) int {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	count := 0
	for _, s := range sm.tokenSessions[token] {
		if s.GetState() == SessionStateActive {
			count++
		}
	}
	return count
}

func (sm *SessionManager) TotalActive() int {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	count := 0
	for _, s := range sm.sessions {
		if s.GetState() == SessionStateActive {
			count++
		}
	}
	return count
}

// CleanExpired removes sessions that have been idle beyond the timeout.
func (sm *SessionManager) CleanExpired(timeout time.Duration) int {
	sm.mu.Lock()
	defer sm.mu.Unlock()

	var expired []string
	for id, s := range sm.sessions {
		if s.IsExpired(timeout) {
			expired = append(expired, id)
		}
	}

	for _, id := range expired {
		s := sm.sessions[id]
		s.SetState(SessionStateClosed)
		delete(sm.sessions, id)
		if s.AuthToken != "" {
			sessions := sm.tokenSessions[s.AuthToken]
			filtered := make([]*Session, 0, len(sessions))
			for _, es := range sessions {
				if es.ID != id {
					filtered = append(filtered, es)
				}
			}
			if len(filtered) == 0 {
				delete(sm.tokenSessions, s.AuthToken)
			} else {
				sm.tokenSessions[s.AuthToken] = filtered
			}
		}
	}

	return len(expired)
}

func (sm *SessionManager) AllSessions() []*Session {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	result := make([]*Session, 0, len(sm.sessions))
	for _, s := range sm.sessions {
		result = append(result, s)
	}
	return result
}
