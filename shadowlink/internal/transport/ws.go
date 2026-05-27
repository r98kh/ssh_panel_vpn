package transport

import (
	"context"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

const (
	WriteWait      = 10 * time.Second
	PongWait       = 60 * time.Second
	PingPeriod     = (PongWait * 9) / 10
	MaxMessageSize = 128 * 1024 // 128KB
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  MaxMessageSize,
	WriteBufferSize: MaxMessageSize,
	CheckOrigin:     func(r *http.Request) bool { return true },
}

// WSConn wraps a gorilla/websocket.Conn to implement io.ReadWriteCloser
// so it can be used transparently by the protocol layer.
type WSConn struct {
	conn      *websocket.Conn
	readBuf   []byte
	readMu    sync.Mutex
	writeMu   sync.Mutex
}

func NewWSConn(conn *websocket.Conn) *WSConn {
	return &WSConn{conn: conn}
}

func (w *WSConn) Read(p []byte) (int, error) {
	w.readMu.Lock()
	defer w.readMu.Unlock()

	if len(w.readBuf) > 0 {
		n := copy(p, w.readBuf)
		w.readBuf = w.readBuf[n:]
		return n, nil
	}

	_, msg, err := w.conn.ReadMessage()
	if err != nil {
		return 0, err
	}

	n := copy(p, msg)
	if n < len(msg) {
		w.readBuf = msg[n:]
	}
	return n, nil
}

func (w *WSConn) Write(p []byte) (int, error) {
	w.writeMu.Lock()
	defer w.writeMu.Unlock()

	err := w.conn.WriteMessage(websocket.BinaryMessage, p)
	if err != nil {
		return 0, err
	}
	return len(p), nil
}

func (w *WSConn) Close() error {
	return w.conn.Close()
}

func (w *WSConn) LocalAddr() net.Addr {
	return w.conn.LocalAddr()
}

func (w *WSConn) RemoteAddr() net.Addr {
	return w.conn.RemoteAddr()
}

// DialWS connects to a WebSocket server, optionally through uTLS.
func DialWS(ctx context.Context, serverAddr, wsPath, sni string, useTLS bool, insecure bool) (*WSConn, error) {
	scheme := "ws"
	if useTLS {
		scheme = "wss"
	}

	wsURL := fmt.Sprintf("%s://%s%s", scheme, serverAddr, wsPath)

	var dialer *websocket.Dialer
	if useTLS {
		var tlsConn net.Conn
		var err error
		if insecure {
			tlsConn, err = DialUTLSInsecure(serverAddr, sni)
		} else {
			tlsConn, err = DialUTLS(serverAddr, sni)
		}
		if err != nil {
			return nil, fmt.Errorf("TLS dial failed: %w", err)
		}

		dialer = &websocket.Dialer{
			NetDialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
				return tlsConn, nil
			},
		}
		wsURL = fmt.Sprintf("ws://%s%s", serverAddr, wsPath)
	} else {
		dialer = &websocket.Dialer{
			HandshakeTimeout: 10 * time.Second,
		}
	}

	headers := http.Header{}
	headers.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
	if sni != "" {
		headers.Set("Origin", fmt.Sprintf("https://%s", sni))
	}
	headers.Set("Accept-Language", "en-US,en;q=0.9")

	var conn *websocket.Conn
	var err error
	for attempt := 0; attempt < 3; attempt++ {
		conn, _, err = dialer.DialContext(ctx, wsURL, headers)
		if err == nil {
			break
		}
		log.Printf("[transport] websocket dial attempt %d failed: %v", attempt+1, err)
		time.Sleep(time.Duration(attempt+1) * 500 * time.Millisecond)
	}
	if err != nil {
		return nil, fmt.Errorf("websocket dial failed: %w", err)
	}

	conn.SetReadLimit(MaxMessageSize)
	return NewWSConn(conn), nil
}

// WSHandler returns an http.HandlerFunc that upgrades HTTP connections to WebSocket
// and passes them to the provided callback.
func WSHandler(onConnect func(conn *WSConn, r *http.Request)) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		wsConn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		onConnect(NewWSConn(wsConn), r)
	}
}

// ServeDecoy serves a decoy HTML page for non-WebSocket requests (anti-probe).
func ServeDecoy(decoyDir string) http.Handler {
	if decoyDir != "" {
		return http.FileServer(http.Dir(decoyDir))
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Header().Set("Server", "nginx/1.24.0")
		fmt.Fprint(w, defaultDecoyPage)
	})
}

var defaultDecoyPage = `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Welcome</title>
<style>body{font-family:system-ui,-apple-system,sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:#f5f5f5;color:#333}
.container{text-align:center;padding:2rem}.container h1{font-size:2rem;margin-bottom:0.5rem}.container p{color:#666;font-size:1.1rem}</style>
</head>
<body><div class="container"><h1>Welcome</h1><p>This server is running normally.</p></div></body>
</html>`

// io.ReadWriteCloser assertion
var _ io.ReadWriteCloser = (*WSConn)(nil)
