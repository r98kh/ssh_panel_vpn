package protocol

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/binary"
	"errors"
	"sync"
	"sync/atomic"

	"golang.org/x/crypto/chacha20poly1305"
)

const (
	NonceSize     = 12
	KeySize       = 32
	AEADOverhead  = 16 // Poly1305 / GCM tag size
	MaxFrameSize  = 65535
)

type CipherSuite byte

const (
	CipherChaCha20Poly1305 CipherSuite = 0x01
	CipherAES256GCM        CipherSuite = 0x02
)

type SessionCipher struct {
	aead       cipher.AEAD
	sendNonce  atomic.Uint64
	recvNonce  atomic.Uint64
	suite      CipherSuite
	mu         sync.Mutex
	WriteMu    sync.Mutex // Serializes encrypt+write to preserve nonce ordering
}

func NewSessionCipher(key []byte, suite CipherSuite) (*SessionCipher, error) {
	if len(key) != KeySize {
		return nil, errors.New("key must be 32 bytes")
	}

	var aead cipher.AEAD
	var err error

	switch suite {
	case CipherChaCha20Poly1305:
		aead, err = chacha20poly1305.New(key)
	case CipherAES256GCM:
		block, berr := aes.NewCipher(key)
		if berr != nil {
			return nil, berr
		}
		aead, err = cipher.NewGCM(block)
	default:
		return nil, errors.New("unsupported cipher suite")
	}

	if err != nil {
		return nil, err
	}

	return &SessionCipher{
		aead:  aead,
		suite: suite,
	}, nil
}

func (sc *SessionCipher) Encrypt(plaintext []byte) ([]byte, error) {
	nonce := sc.nextSendNonce()
	ciphertext := sc.aead.Seal(nil, nonce, plaintext, nil)
	result := make([]byte, NonceSize+len(ciphertext))
	copy(result[:NonceSize], nonce)
	copy(result[NonceSize:], ciphertext)
	return result, nil
}

func (sc *SessionCipher) Decrypt(data []byte) ([]byte, error) {
	if len(data) < NonceSize+AEADOverhead {
		return nil, errors.New("ciphertext too short")
	}
	nonce := data[:NonceSize]
	ciphertext := data[NonceSize:]

	recvSeq := binary.LittleEndian.Uint64(nonce[:8])
	expected := sc.recvNonce.Load()
	if recvSeq < expected {
		return nil, errors.New("nonce replay detected")
	}
	sc.recvNonce.Store(recvSeq + 1)

	return sc.aead.Open(nil, nonce, ciphertext, nil)
}

func (sc *SessionCipher) nextSendNonce() []byte {
	seq := sc.sendNonce.Add(1) - 1
	nonce := make([]byte, NonceSize)
	binary.LittleEndian.PutUint64(nonce, seq)
	return nonce
}

func GenerateKey() ([]byte, error) {
	key := make([]byte, KeySize)
	_, err := rand.Read(key)
	return key, err
}

func DetectBestCipher() CipherSuite {
	// ChaCha20 is consistently fast across all platforms
	// AES-GCM is faster on CPUs with AES-NI but we default to ChaCha20
	// for broader compatibility (mobile, ARM devices)
	return CipherChaCha20Poly1305
}
