package transport

import (
	"context"
	"fmt"
	"net"
	"net/http"

	"github.com/gorilla/websocket"
)

// CDNConfig holds configuration for CDN-based routing (e.g., Cloudflare).
// When using a CDN, the client connects to the CDN's IP but sets the Host
// header to the actual domain, so the CDN routes to the origin server.
type CDNConfig struct {
	Enabled    bool   `yaml:"enabled"`
	CDNAddress string `yaml:"cdn_address"` // e.g., "cdn-ip:443" or leave empty for DNS-based
	Domain     string `yaml:"domain"`      // actual domain pointed to CDN
	WSPath     string `yaml:"ws_path"`     // WebSocket endpoint path
}

// DialViaCDN connects through a CDN by setting the Host header to the
// configured domain while connecting to the CDN edge IP.
func DialViaCDN(ctx context.Context, cfg CDNConfig, insecure bool) (*WSConn, error) {
	targetAddr := cfg.CDNAddress
	if targetAddr == "" {
		targetAddr = cfg.Domain + ":443"
	}

	sni := cfg.Domain
	wsPath := cfg.WSPath
	if wsPath == "" {
		wsPath = "/ws"
	}

	var tlsConn net.Conn
	var err error
	if insecure {
		tlsConn, err = DialUTLSInsecure(targetAddr, sni)
	} else {
		tlsConn, err = DialUTLS(targetAddr, sni)
	}
	if err != nil {
		return nil, fmt.Errorf("CDN TLS dial failed: %w", err)
	}

	dialer := &websocket.Dialer{
		NetDialContext: func(ctx context.Context, network, addr string) (net.Conn, error) {
			return tlsConn, nil
		},
	}

	url := fmt.Sprintf("ws://%s%s", targetAddr, wsPath)

	headers := http.Header{}
	headers.Set("Host", cfg.Domain)
	headers.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
	headers.Set("Origin", fmt.Sprintf("https://%s", cfg.Domain))

	conn, _, err := dialer.DialContext(ctx, url, headers)
	if err != nil {
		return nil, fmt.Errorf("CDN websocket dial failed: %w", err)
	}

	conn.SetReadLimit(MaxMessageSize)
	return NewWSConn(conn), nil
}
