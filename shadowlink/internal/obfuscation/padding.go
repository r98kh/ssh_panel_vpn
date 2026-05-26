package obfuscation

import (
	"crypto/rand"
	"math/big"
)

// PaddingConfig controls how random padding is applied to frames.
type PaddingConfig struct {
	MinBytes int `yaml:"min_bytes"`
	MaxBytes int `yaml:"max_bytes"`
	Enabled  bool `yaml:"enabled"`
}

func DefaultPaddingConfig() PaddingConfig {
	return PaddingConfig{
		MinBytes: 16,
		MaxBytes: 128,
		Enabled:  true,
	}
}

// RandomPaddingSize returns a random size between min and max.
func RandomPaddingSize(cfg PaddingConfig) (int, error) {
	if !cfg.Enabled {
		return 0, nil
	}
	diff := cfg.MaxBytes - cfg.MinBytes
	if diff <= 0 {
		return cfg.MinBytes, nil
	}
	n, err := rand.Int(rand.Reader, big.NewInt(int64(diff)))
	if err != nil {
		return 0, err
	}
	return cfg.MinBytes + int(n.Int64()), nil
}

// GeneratePadding creates random bytes of the given size.
func GeneratePadding(size int) ([]byte, error) {
	if size <= 0 {
		return nil, nil
	}
	buf := make([]byte, size)
	_, err := rand.Read(buf)
	return buf, err
}
