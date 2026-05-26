package obfuscation

import (
	"io"
	"sync"
	"time"

	"github.com/user/shadowlink/internal/protocol"
)

// TrafficShaper sends fake keepalive frames during idle periods
// to prevent traffic analysis based on activity patterns.
type TrafficShaper struct {
	cipher     *protocol.SessionCipher
	writer     io.Writer
	interval   time.Duration
	padConfig  PaddingConfig
	stopCh     chan struct{}
	stopped    bool
	mu         sync.Mutex
}

type TrafficShapeConfig struct {
	Enabled       bool          `yaml:"enabled"`
	IdleInterval  time.Duration `yaml:"idle_interval"`
	PaddingConfig PaddingConfig `yaml:"padding"`
}

func DefaultTrafficShapeConfig() TrafficShapeConfig {
	return TrafficShapeConfig{
		Enabled:      true,
		IdleInterval: 5 * time.Second,
		PaddingConfig: PaddingConfig{
			MinBytes: 64,
			MaxBytes: 512,
			Enabled:  true,
		},
	}
}

func NewTrafficShaper(cipher *protocol.SessionCipher, writer io.Writer, cfg TrafficShapeConfig) *TrafficShaper {
	interval := cfg.IdleInterval
	if interval == 0 {
		interval = 5 * time.Second
	}
	return &TrafficShaper{
		cipher:    cipher,
		writer:    writer,
		interval:  interval,
		padConfig: cfg.PaddingConfig,
		stopCh:    make(chan struct{}),
	}
}

// Start begins sending fake traffic in the background.
func (ts *TrafficShaper) Start() {
	go ts.run()
}

func (ts *TrafficShaper) run() {
	ticker := time.NewTicker(ts.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ts.stopCh:
			return
		case <-ticker.C:
			ts.sendFakeFrame()
		}
	}
}

func (ts *TrafficShaper) sendFakeFrame() {
	ts.mu.Lock()
	defer ts.mu.Unlock()

	if ts.stopped {
		return
	}

	padSize, err := RandomPaddingSize(ts.padConfig)
	if err != nil {
		return
	}

	padding, err := GeneratePadding(padSize)
	if err != nil {
		return
	}

	frame := &protocol.Frame{
		Type:    protocol.FrameKeepalive,
		Payload: padding,
	}

	_ = protocol.WriteFrameTo(ts.writer, frame, ts.cipher, ts.padConfig.MinBytes, ts.padConfig.MaxBytes)
}

// Stop terminates the traffic shaper.
func (ts *TrafficShaper) Stop() {
	ts.mu.Lock()
	defer ts.mu.Unlock()
	if !ts.stopped {
		ts.stopped = true
		close(ts.stopCh)
	}
}

// NotifyActivity should be called when real traffic is sent/received
// to reset the idle timer (future enhancement: adaptive intervals).
func (ts *TrafficShaper) NotifyActivity() {
	// Placeholder for adaptive shaping
}
