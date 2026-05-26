package proxy

import (
	"context"
	"fmt"
	"io"
	"log"
	"net"
	"sync"
	"time"

	"github.com/things-go/go-socks5"

	"github.com/user/shadowlink/internal/obfuscation"
	"github.com/user/shadowlink/internal/protocol"
	"github.com/user/shadowlink/internal/transport"
)

// ClientConfig holds configuration for the ShadowLink client.
type ClientConfig struct {
	ListenAddr    string                        `yaml:"listen_addr"`
	ServerAddr    string                        `yaml:"server_addr"`
	ServerSNI     string                        `yaml:"server_sni"`
	WSPath        string                        `yaml:"ws_path"`
	AuthToken     string                        `yaml:"auth_token"`
	UseTLS        bool                          `yaml:"use_tls"`
	Insecure      bool                          `yaml:"insecure"`
	CDN           transport.CDNConfig           `yaml:"cdn"`
	Padding       obfuscation.PaddingConfig     `yaml:"padding"`
	Timing        obfuscation.TimingConfig      `yaml:"timing"`
	TrafficShape  obfuscation.TrafficShapeConfig `yaml:"traffic_shape"`
}

func DefaultClientConfig() ClientConfig {
	return ClientConfig{
		ListenAddr: "127.0.0.1:1080",
		WSPath:     "/ws",
		UseTLS:     true,
		Padding:    obfuscation.DefaultPaddingConfig(),
		Timing:     obfuscation.DefaultTimingConfig(),
		TrafficShape: obfuscation.DefaultTrafficShapeConfig(),
	}
}

// Client is the local SOCKS5 proxy that tunnels through ShadowLink.
type Client struct {
	config    ClientConfig
	wsConn    *transport.WSConn
	cipher    *protocol.SessionCipher
	sessions  map[uint32]*tunnelStream
	nextID    uint32
	mu        sync.Mutex
	shaper    *obfuscation.TrafficShaper
}

type tunnelStream struct {
	id     uint32
	reader *io.PipeReader
	writer *io.PipeWriter
}

func NewClient(cfg ClientConfig) *Client {
	return &Client{
		config:   cfg,
		sessions: make(map[uint32]*tunnelStream),
	}
}

// Connect establishes the WebSocket connection and performs the handshake.
func (c *Client) Connect(ctx context.Context) error {
	var wsConn *transport.WSConn
	var err error

	if c.config.CDN.Enabled {
		wsConn, err = transport.DialViaCDN(ctx, c.config.CDN, c.config.Insecure)
	} else {
		wsConn, err = transport.DialWS(ctx, c.config.ServerAddr, c.config.WSPath, c.config.ServerSNI, c.config.UseTLS, c.config.Insecure)
	}
	if err != nil {
		return fmt.Errorf("connection failed: %w", err)
	}
	c.wsConn = wsConn

	cipher, err := c.performHandshake()
	if err != nil {
		wsConn.Close()
		return fmt.Errorf("handshake failed: %w", err)
	}
	c.cipher = cipher

	if c.config.TrafficShape.Enabled {
		c.shaper = obfuscation.NewTrafficShaper(cipher, wsConn, c.config.TrafficShape)
		c.shaper.Start()
	}

	go c.readLoop()

	return nil
}

func (c *Client) performHandshake() (*protocol.SessionCipher, error) {
	kp, err := protocol.GenerateKeyPair()
	if err != nil {
		return nil, err
	}

	clientHello, err := protocol.BuildClientHello(kp)
	if err != nil {
		return nil, err
	}

	if _, err := c.wsConn.Write(clientHello); err != nil {
		return nil, fmt.Errorf("failed to send client hello: %w", err)
	}

	serverHelloBuf := make([]byte, 4096)
	n, err := c.wsConn.Read(serverHelloBuf)
	if err != nil {
		return nil, fmt.Errorf("failed to read server hello: %w", err)
	}

	ts := time.Now()
	_, _, sessionKey, err := protocol.ParseServerHello(serverHelloBuf[:n], kp.Private, ts)
	if err != nil {
		return nil, fmt.Errorf("failed to parse server hello: %w", err)
	}

	clientAuth, err := protocol.BuildClientAuth(serverHelloBuf[protocol.X25519KeySize:protocol.X25519KeySize+protocol.ChallengeSize], sessionKey, c.config.AuthToken)
	if err != nil {
		return nil, fmt.Errorf("failed to build client auth: %w", err)
	}

	if _, err := c.wsConn.Write(clientAuth); err != nil {
		return nil, fmt.Errorf("failed to send client auth: %w", err)
	}

	ackBuf := make([]byte, 1024)
	n, err = c.wsConn.Read(ackBuf)
	if err != nil {
		return nil, fmt.Errorf("failed to read server ack: %w", err)
	}
	_ = n

	cipher, err := protocol.NewSessionCipher(sessionKey, protocol.DetectBestCipher())
	if err != nil {
		return nil, err
	}

	return cipher, nil
}

func (c *Client) readLoop() {
	for {
		frame, err := protocol.ReadFrameFrom(c.wsConn, c.cipher)
		if err != nil {
			log.Printf("[client] read error: %v", err)
			return
		}

		switch frame.Type {
		case protocol.FrameData:
			if len(frame.Payload) < 4 {
				continue
			}
			streamID := uint32(frame.Payload[0])<<24 | uint32(frame.Payload[1])<<16 | uint32(frame.Payload[2])<<8 | uint32(frame.Payload[3])
			c.mu.Lock()
			stream, ok := c.sessions[streamID]
			c.mu.Unlock()
			if ok {
				stream.writer.Write(frame.Payload[4:])
			}
		case protocol.FrameKeepalive:
			// Ignore keepalive frames (traffic shaping)
		case protocol.FrameClose:
			return
		}
	}
}

// RunSOCKS5 starts the local SOCKS5 proxy server.
func (c *Client) RunSOCKS5(ctx context.Context) error {
	server := socks5.NewServer(
		socks5.WithDial(c.dialThroughTunnel),
	)

	log.Printf("[client] SOCKS5 proxy listening on %s", c.config.ListenAddr)
	return server.ListenAndServe("tcp", c.config.ListenAddr)
}

func (c *Client) dialThroughTunnel(ctx context.Context, network, addr string) (net.Conn, error) {
	c.mu.Lock()
	id := c.nextID
	c.nextID++

	pr, pw := io.Pipe()
	stream := &tunnelStream{id: id, reader: pr, writer: pw}
	c.sessions[id] = stream
	c.mu.Unlock()

	connectPayload := []byte(fmt.Sprintf("%s|%s", network, addr))
	frame := &protocol.Frame{
		Type:    protocol.FrameControl,
		Payload: append(encodeStreamID(id), connectPayload...),
	}

	obfuscation.Sleep(c.config.Timing)
	if err := protocol.WriteFrameTo(c.wsConn, frame, c.cipher, c.config.Padding.MinBytes, c.config.Padding.MaxBytes); err != nil {
		return nil, err
	}

	return &tunnelConn{
		streamID: id,
		reader:   pr,
		client:   c,
	}, nil
}

func encodeStreamID(id uint32) []byte {
	return []byte{byte(id >> 24), byte(id >> 16), byte(id >> 8), byte(id)}
}

// tunnelConn wraps a tunnel stream as a net.Conn for the SOCKS5 server.
type tunnelConn struct {
	streamID uint32
	reader   *io.PipeReader
	client   *Client
}

func (tc *tunnelConn) Read(p []byte) (int, error) {
	return tc.reader.Read(p)
}

func (tc *tunnelConn) Write(p []byte) (int, error) {
	payload := append(encodeStreamID(tc.streamID), p...)
	frame := protocol.NewDataFrame(payload)

	obfuscation.Sleep(tc.client.config.Timing)
	if err := protocol.WriteFrameTo(tc.client.wsConn, frame, tc.client.cipher, tc.client.config.Padding.MinBytes, tc.client.config.Padding.MaxBytes); err != nil {
		return 0, err
	}
	if tc.client.shaper != nil {
		tc.client.shaper.NotifyActivity()
	}
	return len(p), nil
}

func (tc *tunnelConn) Close() error {
	tc.client.mu.Lock()
	delete(tc.client.sessions, tc.streamID)
	tc.client.mu.Unlock()

	frame := &protocol.Frame{
		Type:    protocol.FrameClose,
		Payload: encodeStreamID(tc.streamID),
	}
	_ = protocol.WriteFrameTo(tc.client.wsConn, frame, tc.client.cipher, 0, 16)
	return tc.reader.Close()
}

func (tc *tunnelConn) LocalAddr() net.Addr  { return &net.TCPAddr{} }
func (tc *tunnelConn) RemoteAddr() net.Addr { return &net.TCPAddr{} }
func (tc *tunnelConn) SetDeadline(t time.Time) error      { return nil }
func (tc *tunnelConn) SetReadDeadline(t time.Time) error   { return nil }
func (tc *tunnelConn) SetWriteDeadline(t time.Time) error  { return nil }

// Close shuts down the client.
func (c *Client) Close() {
	if c.shaper != nil {
		c.shaper.Stop()
	}
	if c.wsConn != nil {
		frame := protocol.NewCloseFrame()
		_ = protocol.WriteFrameTo(c.wsConn, frame, c.cipher, 0, 16)
		c.wsConn.Close()
	}
}
