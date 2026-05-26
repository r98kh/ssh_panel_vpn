package protocol

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"errors"
	"io"
	"math/big"
	"time"

	"golang.org/x/crypto/curve25519"
	"golang.org/x/crypto/hkdf"
)

const (
	HandshakeTimeout  = 10 * time.Second
	TimestampWindow   = 30 * time.Second
	X25519KeySize     = 32
	HMACSize          = 32
	ChallengeSize     = 32
	AuthTokenSize     = 36 // UUID string length
	MinHandshakePad   = 32
	MaxHandshakePad   = 256
)

type HandshakeResult struct {
	SessionKey  []byte
	CipherSuite CipherSuite
	AuthToken   string
}

type KeyPair struct {
	Private []byte
	Public  []byte
}

func GenerateKeyPair() (*KeyPair, error) {
	priv := make([]byte, X25519KeySize)
	if _, err := rand.Read(priv); err != nil {
		return nil, err
	}

	pub, err := curve25519.X25519(priv, curve25519.Basepoint)
	if err != nil {
		return nil, err
	}

	return &KeyPair{Private: priv, Public: pub}, nil
}

func computeSharedSecret(privateKey, peerPublicKey []byte) ([]byte, error) {
	return curve25519.X25519(privateKey, peerPublicKey)
}

func deriveSessionKey(sharedSecret []byte, salt []byte) ([]byte, error) {
	hkdfReader := hkdf.New(sha256.New, sharedSecret, salt, []byte("shadowlink-session-v1"))
	key := make([]byte, KeySize)
	if _, err := io.ReadFull(hkdfReader, key); err != nil {
		return nil, err
	}
	return key, nil
}

func computeHMAC(data, key []byte) []byte {
	mac := hmac.New(sha256.New, key)
	mac.Write(data)
	return mac.Sum(nil)
}

func verifyHMAC(data, expectedMAC, key []byte) bool {
	return hmac.Equal(computeHMAC(data, key), expectedMAC)
}

func randomPadding(min, max int) ([]byte, error) {
	diff := max - min
	if diff <= 0 {
		diff = 1
	}
	n, err := rand.Int(rand.Reader, big.NewInt(int64(diff)))
	if err != nil {
		return nil, err
	}
	size := min + int(n.Int64())
	pad := make([]byte, size)
	_, err = rand.Read(pad)
	return pad, err
}

// BuildClientHello builds the first handshake message from the client.
// Format: [8-byte timestamp][32-byte client pubkey][N-byte random padding]
func BuildClientHello(kp *KeyPair) ([]byte, error) {
	return BuildClientHelloWithTime(kp, time.Now())
}

// BuildClientHelloWithTime builds a client hello with a specific timestamp,
// so the caller can reuse the exact same value during ParseServerHello.
func BuildClientHelloWithTime(kp *KeyPair, ts time.Time) ([]byte, error) {
	pad, err := randomPadding(MinHandshakePad, MaxHandshakePad)
	if err != nil {
		return nil, err
	}

	msg := make([]byte, 8+X25519KeySize+len(pad))
	binary.BigEndian.PutUint64(msg[:8], uint64(ts.Unix()))
	copy(msg[8:8+X25519KeySize], kp.Public)
	copy(msg[8+X25519KeySize:], pad)
	return msg, nil
}

// ParseClientHello extracts timestamp and client public key from the hello message.
func ParseClientHello(data []byte) (timestamp time.Time, clientPub []byte, err error) {
	if len(data) < 8+X25519KeySize {
		return time.Time{}, nil, errors.New("client hello too short")
	}

	ts := binary.BigEndian.Uint64(data[:8])
	timestamp = time.Unix(int64(ts), 0)

	now := time.Now()
	if now.Sub(timestamp) > TimestampWindow || timestamp.Sub(now) > TimestampWindow {
		return time.Time{}, nil, errors.New("timestamp outside acceptable window (replay protection)")
	}

	clientPub = make([]byte, X25519KeySize)
	copy(clientPub, data[8:8+X25519KeySize])
	return timestamp, clientPub, nil
}

// BuildServerHello builds the server's response with its public key and an encrypted challenge.
// Format: [32-byte server pubkey][32-byte challenge][N-byte random padding]
// The challenge and padding are encrypted with a temporary key derived from the partial handshake.
func BuildServerHello(serverKP *KeyPair, clientPub []byte, timestamp time.Time) (challenge []byte, msg []byte, err error) {
	challenge = make([]byte, ChallengeSize)
	if _, err = rand.Read(challenge); err != nil {
		return nil, nil, err
	}

	pad, err := randomPadding(MinHandshakePad, MaxHandshakePad)
	if err != nil {
		return nil, nil, err
	}

	sharedSecret, err := computeSharedSecret(serverKP.Private, clientPub)
	if err != nil {
		return nil, nil, err
	}

	salt := make([]byte, 8)
	binary.BigEndian.PutUint64(salt, uint64(timestamp.Unix()))
	tempKey, err := deriveSessionKey(sharedSecret, salt)
	if err != nil {
		return nil, nil, err
	}

	tempCipher, err := NewSessionCipher(tempKey, CipherChaCha20Poly1305)
	if err != nil {
		return nil, nil, err
	}

	payload := append(challenge, pad...)
	encPayload, err := tempCipher.Encrypt(payload)
	if err != nil {
		return nil, nil, err
	}

	msg = make([]byte, X25519KeySize+len(encPayload))
	copy(msg[:X25519KeySize], serverKP.Public)
	copy(msg[X25519KeySize:], encPayload)

	return challenge, msg, nil
}

// ParseServerHello extracts server public key and decrypts the challenge.
func ParseServerHello(data []byte, clientPriv []byte, timestamp time.Time) (serverPub, challenge []byte, sessionKey []byte, err error) {
	if len(data) < X25519KeySize+NonceSize+AEADOverhead {
		return nil, nil, nil, errors.New("server hello too short")
	}

	serverPub = make([]byte, X25519KeySize)
	copy(serverPub, data[:X25519KeySize])

	sharedSecret, err := computeSharedSecret(clientPriv, serverPub)
	if err != nil {
		return nil, nil, nil, err
	}

	salt := make([]byte, 8)
	binary.BigEndian.PutUint64(salt, uint64(timestamp.Unix()))
	tempKey, err := deriveSessionKey(sharedSecret, salt)
	if err != nil {
		return nil, nil, nil, err
	}

	tempCipher, err := NewSessionCipher(tempKey, CipherChaCha20Poly1305)
	if err != nil {
		return nil, nil, nil, err
	}

	payload, err := tempCipher.Decrypt(data[X25519KeySize:])
	if err != nil {
		return nil, nil, nil, err
	}

	if len(payload) < ChallengeSize {
		return nil, nil, nil, errors.New("decrypted payload too short for challenge")
	}

	challenge = payload[:ChallengeSize]

	sessionSalt := append(salt, challenge...)
	sessionKey, err = deriveSessionKey(sharedSecret, sessionSalt)
	if err != nil {
		return nil, nil, nil, err
	}

	return serverPub, challenge, sessionKey, nil
}

// BuildClientAuth builds the client's authentication response.
// Format: [32-byte HMAC of challenge][auth-token-bytes][padding]
func BuildClientAuth(challenge, sessionKey []byte, authToken string) ([]byte, error) {
	mac := computeHMAC(challenge, sessionKey)
	tokenBytes := []byte(authToken)

	pad, err := randomPadding(MinHandshakePad, MaxHandshakePad)
	if err != nil {
		return nil, err
	}

	msg := make([]byte, HMACSize+1+len(tokenBytes)+len(pad))
	copy(msg[:HMACSize], mac)
	msg[HMACSize] = byte(len(tokenBytes))
	copy(msg[HMACSize+1:HMACSize+1+len(tokenBytes)], tokenBytes)
	copy(msg[HMACSize+1+len(tokenBytes):], pad)
	return msg, nil
}

// ParseClientAuth extracts and verifies the HMAC and auth token.
func ParseClientAuth(data []byte, challenge, sessionKey []byte) (authToken string, err error) {
	if len(data) < HMACSize+1 {
		return "", errors.New("client auth too short")
	}

	mac := data[:HMACSize]
	if !verifyHMAC(challenge, mac, sessionKey) {
		return "", errors.New("HMAC verification failed")
	}

	tokenLen := int(data[HMACSize])
	if len(data) < HMACSize+1+tokenLen {
		return "", errors.New("auth token truncated")
	}

	authToken = string(data[HMACSize+1 : HMACSize+1+tokenLen])
	return authToken, nil
}

// DeriveServerSessionKey derives the same session key on the server side.
func DeriveServerSessionKey(serverPriv, clientPub []byte, timestamp time.Time, challenge []byte) ([]byte, error) {
	sharedSecret, err := computeSharedSecret(serverPriv, clientPub)
	if err != nil {
		return nil, err
	}

	salt := make([]byte, 8)
	binary.BigEndian.PutUint64(salt, uint64(timestamp.Unix()))

	sessionSalt := append(salt, challenge...)
	return deriveSessionKey(sharedSecret, sessionSalt)
}
