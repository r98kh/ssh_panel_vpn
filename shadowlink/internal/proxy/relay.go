package proxy

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"io"
	"log"
	"net"
	"strings"
	"sync"
	"time"

	"github.com/user/shadowlink/internal/obfuscation"
	"github.com/user/shadowlink/internal/protocol"
	"github.com/user/shadowlink/internal/transport"
)

// ServerRelay handles traffic relay on the server side.
type ServerRelay struct {
	sessions   *protocol.SessionManager
	streams    map[string]map[uint32]net.Conn // sessionID -> streamID -> upstream conn
	authFunc   func(token string) (bool, int) // returns (valid, maxConns)
	padConfig  obfuscation.PaddingConfig
	timingCfg  obfuscation.TimingConfig
	mu         sync.RWMutex
}

func NewServerRelay(authFunc func(string) (bool, int), padCfg obfuscation.PaddingConfig, timingCfg obfuscation.TimingConfig) *ServerRelay {
	return &ServerRelay{
		sessions:  protocol.NewSessionManager(0),
		streams:   make(map[string]map[uint32]net.Conn),
		authFunc:  authFunc,
		padConfig: padCfg,
		timingCfg: timingCfg,
	}
}

// HandleConnection processes a new incoming WebSocket connection.
func (sr *ServerRelay) HandleConnection(wsConn *transport.WSConn) {
	session := protocol.NewSession(generateSessionID(), wsConn.RemoteAddr())
	session.SetState(protocol.SessionStateHandshaking)

	cipher, authToken, err := sr.performServerHandshake(wsConn, session)
	if err != nil {
		log.Printf("[server] handshake failed from %s: %v", wsConn.RemoteAddr(), err)
		wsConn.Close()
		return
	}

	session.AuthToken = authToken
	session.SetCipher(cipher)
	session.SetState(protocol.SessionStateActive)

	sr.mu.Lock()
	sr.streams[session.ID] = make(map[uint32]net.Conn)
	sr.mu.Unlock()

	log.Printf("[server] session established: %s (token: %.8s...)", session.ID, authToken)

	sr.relayLoop(wsConn, session, cipher)

	sr.cleanupSession(session)
	log.Printf("[server] session closed: %s", session.ID)
}

func (sr *ServerRelay) performServerHandshake(wsConn *transport.WSConn, session *protocol.Session) (*protocol.SessionCipher, string, error) {
	helloBuf := make([]byte, 4096)
	n, err := wsConn.Read(helloBuf)
	if err != nil {
		return nil, "", fmt.Errorf("read client hello: %w", err)
	}

	timestamp, clientPub, err := protocol.ParseClientHello(helloBuf[:n])
	if err != nil {
		return nil, "", fmt.Errorf("parse client hello: %w", err)
	}

	serverKP, err := protocol.GenerateKeyPair()
	if err != nil {
		return nil, "", fmt.Errorf("generate server keypair: %w", err)
	}

	challenge, serverHello, err := protocol.BuildServerHello(serverKP, clientPub, timestamp)
	if err != nil {
		return nil, "", fmt.Errorf("build server hello: %w", err)
	}

	if _, err := wsConn.Write(serverHello); err != nil {
		return nil, "", fmt.Errorf("send server hello: %w", err)
	}

	authBuf := make([]byte, 4096)
	n, err = wsConn.Read(authBuf)
	if err != nil {
		return nil, "", fmt.Errorf("read client auth: %w", err)
	}

	sessionKey, err := protocol.DeriveServerSessionKey(serverKP.Private, clientPub, timestamp, challenge)
	if err != nil {
		return nil, "", fmt.Errorf("derive session key: %w", err)
	}

	authToken, err := protocol.ParseClientAuth(authBuf[:n], challenge, sessionKey)
	if err != nil {
		return nil, "", fmt.Errorf("parse client auth: %w", err)
	}

	// Validate token BEFORE sending OK
	if sr.authFunc != nil {
		valid, _ := sr.authFunc(authToken)
		if !valid {
			wsConn.Write([]byte("DENIED"))
			return nil, "", fmt.Errorf("auth denied for token: %s", authToken)
		}
	}

	ack := []byte("OK")
	if _, err := wsConn.Write(ack); err != nil {
		return nil, "", fmt.Errorf("send ack: %w", err)
	}

	cipher, err := protocol.NewSessionCipher(sessionKey, protocol.DetectBestCipher())
	if err != nil {
		return nil, "", err
	}

	return cipher, authToken, nil
}

func (sr *ServerRelay) relayLoop(wsConn *transport.WSConn, session *protocol.Session, cipher *protocol.SessionCipher) {
	for {
		frame, err := protocol.ReadFrameFrom(wsConn, cipher)
		if err != nil {
			return
		}

		session.Touch()

		switch frame.Type {
		case protocol.FrameData:
			sr.handleDataFrame(wsConn, session, cipher, frame)
		case protocol.FrameControl:
			sr.handleControlFrame(wsConn, session, cipher, frame)
		case protocol.FrameKeepalive:
			continue
		case protocol.FrameClose:
			if len(frame.Payload) >= 4 {
				streamID := decodeStreamID(frame.Payload[:4])
				sr.closeStream(session.ID, streamID)
			} else {
				return
			}
		}
	}
}

func (sr *ServerRelay) handleControlFrame(wsConn *transport.WSConn, session *protocol.Session, cipher *protocol.SessionCipher, frame *protocol.Frame) {
	if len(frame.Payload) < 4 {
		return
	}

	streamID := decodeStreamID(frame.Payload[:4])
	connectInfo := string(frame.Payload[4:])

	parts := strings.SplitN(connectInfo, "|", 2)
	if len(parts) != 2 {
		return
	}
	network, addr := parts[0], parts[1]

	conn, err := net.DialTimeout(network, addr, 10*time.Second)
	if err != nil {
		log.Printf("[server] failed to connect to %s: %v", addr, err)
		return
	}

	sr.mu.Lock()
	if sr.streams[session.ID] == nil {
		sr.streams[session.ID] = make(map[uint32]net.Conn)
	}
	sr.streams[session.ID][streamID] = conn
	sr.mu.Unlock()

	go sr.relayUpstream(wsConn, cipher, session.ID, streamID, conn)
}

func (sr *ServerRelay) handleDataFrame(wsConn *transport.WSConn, session *protocol.Session, cipher *protocol.SessionCipher, frame *protocol.Frame) {
	if len(frame.Payload) < 4 {
		return
	}

	streamID := decodeStreamID(frame.Payload[:4])

	sr.mu.RLock()
	conn, ok := sr.streams[session.ID][streamID]
	sr.mu.RUnlock()

	if !ok {
		return
	}

	_, _ = conn.Write(frame.Payload[4:])
}

func (sr *ServerRelay) relayUpstream(wsConn *transport.WSConn, cipher *protocol.SessionCipher, sessionID string, streamID uint32, upstream net.Conn) {
	defer sr.closeStream(sessionID, streamID)

	buf := make([]byte, 32*1024)
	for {
		n, err := upstream.Read(buf)
		if n > 0 {
			payload := append(encodeStreamID(streamID), buf[:n]...)
			frame := protocol.NewDataFrame(payload)

			obfuscation.Sleep(sr.timingCfg)
			if writeErr := protocol.WriteFrameTo(wsConn, frame, cipher, sr.padConfig.MinBytes, sr.padConfig.MaxBytes); writeErr != nil {
				return
			}
		}
		if err != nil {
			if err != io.EOF {
				log.Printf("[server] upstream read error (stream %d): %v", streamID, err)
			}
			return
		}
	}
}

func (sr *ServerRelay) closeStream(sessionID string, streamID uint32) {
	sr.mu.Lock()
	defer sr.mu.Unlock()

	if streams, ok := sr.streams[sessionID]; ok {
		if conn, ok := streams[streamID]; ok {
			conn.Close()
			delete(streams, streamID)
		}
	}
}

func (sr *ServerRelay) cleanupSession(session *protocol.Session) {
	sr.mu.Lock()
	defer sr.mu.Unlock()

	if streams, ok := sr.streams[session.ID]; ok {
		for _, conn := range streams {
			conn.Close()
		}
		delete(sr.streams, session.ID)
	}

	session.SetState(protocol.SessionStateClosed)
	sr.sessions.Remove(session.ID)
}

// GetActiveSessions returns info about all active relay sessions.
func (sr *ServerRelay) GetActiveSessions() []SessionInfo {
	sessions := sr.sessions.AllSessions()
	infos := make([]SessionInfo, 0, len(sessions))
	for _, s := range sessions {
		sr.mu.RLock()
		streamCount := len(sr.streams[s.ID])
		sr.mu.RUnlock()
		infos = append(infos, SessionInfo{
			ID:          s.ID,
			AuthToken:   s.AuthToken,
			ClientAddr:  s.ClientAddr.String(),
			State:       int(s.GetState()),
			CreatedAt:   s.CreatedAt,
			LastActive:  s.LastActive,
			StreamCount: streamCount,
		})
	}
	return infos
}

type SessionInfo struct {
	ID          string    `json:"id"`
	AuthToken   string    `json:"auth_token"`
	ClientAddr  string    `json:"client_addr"`
	State       int       `json:"state"`
	CreatedAt   time.Time `json:"created_at"`
	LastActive  time.Time `json:"last_active"`
	StreamCount int       `json:"stream_count"`
}

func decodeStreamID(b []byte) uint32 {
	return uint32(b[0])<<24 | uint32(b[1])<<16 | uint32(b[2])<<8 | uint32(b[3])
}

func generateSessionID() string {
	buf := make([]byte, 16)
	_, _ = rand.Read(buf)
	return hex.EncodeToString(buf)
}
