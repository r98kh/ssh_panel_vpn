package obfuscation

import (
	"crypto/rand"
	"math/big"
	"time"
)

// TimingConfig controls the jitter added between packet sends.
type TimingConfig struct {
	Enabled    bool          `yaml:"enabled"`
	MinDelay   time.Duration `yaml:"min_delay"`
	MaxDelay   time.Duration `yaml:"max_delay"`
}

func DefaultTimingConfig() TimingConfig {
	return TimingConfig{
		Enabled:  true,
		MinDelay: 0,
		MaxDelay: 50 * time.Millisecond,
	}
}

// Jitter returns a random duration between MinDelay and MaxDelay.
func Jitter(cfg TimingConfig) time.Duration {
	if !cfg.Enabled {
		return 0
	}
	diff := cfg.MaxDelay - cfg.MinDelay
	if diff <= 0 {
		return cfg.MinDelay
	}
	n, err := rand.Int(rand.Reader, big.NewInt(int64(diff)))
	if err != nil {
		return cfg.MinDelay
	}
	return cfg.MinDelay + time.Duration(n.Int64())
}

// Sleep pauses for a jittered duration.
func Sleep(cfg TimingConfig) {
	d := Jitter(cfg)
	if d > 0 {
		time.Sleep(d)
	}
}
