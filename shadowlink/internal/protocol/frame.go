package protocol

import (
	"crypto/rand"
	"encoding/binary"
	"errors"
	"io"
	"math/big"
)

type FrameType byte

const (
	FrameData      FrameType = 0x01
	FrameKeepalive FrameType = 0x02
	FrameControl   FrameType = 0x03
	FrameClose     FrameType = 0x04
)

const (
	FrameHeaderSize = 4 // type(1) + padLen(1) + dataLen(2)
	MaxPaddingSize  = 255
	MaxPayloadSize  = 65535
)

// Frame represents a single protocol frame before encryption.
type Frame struct {
	Type    FrameType
	Payload []byte
}

// EncodeFrame serializes a frame with random padding, then encrypts it.
// Wire format: [12-byte nonce][encrypted(type + padLen + dataLen + padding + payload) + 16-byte tag]
func EncodeFrame(f *Frame, cipher *SessionCipher, minPad, maxPad int) ([]byte, error) {
	if len(f.Payload) > MaxPayloadSize {
		return nil, errors.New("payload exceeds maximum size")
	}

	padSize, err := randInt(minPad, maxPad)
	if err != nil {
		return nil, err
	}
	padding := make([]byte, padSize)
	if _, err := rand.Read(padding); err != nil {
		return nil, err
	}

	plaintext := make([]byte, FrameHeaderSize+padSize+len(f.Payload))
	plaintext[0] = byte(f.Type)
	plaintext[1] = byte(padSize)
	binary.LittleEndian.PutUint16(plaintext[2:4], uint16(len(f.Payload)))
	copy(plaintext[FrameHeaderSize:FrameHeaderSize+padSize], padding)
	copy(plaintext[FrameHeaderSize+padSize:], f.Payload)

	return cipher.Encrypt(plaintext)
}

// DecodeFrame decrypts and deserializes a frame from wire data.
func DecodeFrame(data []byte, cipher *SessionCipher) (*Frame, error) {
	plaintext, err := cipher.Decrypt(data)
	if err != nil {
		return nil, err
	}

	if len(plaintext) < FrameHeaderSize {
		return nil, errors.New("decrypted frame too short")
	}

	frameType := FrameType(plaintext[0])
	padLen := int(plaintext[1])
	dataLen := int(binary.LittleEndian.Uint16(plaintext[2:4]))

	if len(plaintext) < FrameHeaderSize+padLen+dataLen {
		return nil, errors.New("frame data truncated")
	}

	payload := make([]byte, dataLen)
	copy(payload, plaintext[FrameHeaderSize+padLen:FrameHeaderSize+padLen+dataLen])

	return &Frame{
		Type:    frameType,
		Payload: payload,
	}, nil
}

// ReadFrameFrom reads a length-prefixed encrypted frame from a reader.
// Wire format: [4-byte LE frame length][frame data]
func ReadFrameFrom(r io.Reader, cipher *SessionCipher) (*Frame, error) {
	lenBuf := make([]byte, 4)
	if _, err := io.ReadFull(r, lenBuf); err != nil {
		return nil, err
	}

	frameLen := binary.LittleEndian.Uint32(lenBuf)
	if frameLen > MaxPayloadSize+MaxPaddingSize+FrameHeaderSize+NonceSize+AEADOverhead+256 {
		return nil, errors.New("frame length exceeds maximum")
	}

	frameBuf := make([]byte, frameLen)
	if _, err := io.ReadFull(r, frameBuf); err != nil {
		return nil, err
	}

	return DecodeFrame(frameBuf, cipher)
}

// WriteFrameTo writes a length-prefixed encrypted frame to a writer.
// It holds the cipher's write lock to prevent nonce ordering issues
// when multiple goroutines write concurrently.
func WriteFrameTo(w io.Writer, f *Frame, cipher *SessionCipher, minPad, maxPad int) error {
	cipher.WriteMu.Lock()
	defer cipher.WriteMu.Unlock()

	data, err := EncodeFrame(f, cipher, minPad, maxPad)
	if err != nil {
		return err
	}

	lenBuf := make([]byte, 4)
	binary.LittleEndian.PutUint32(lenBuf, uint32(len(data)))

	buf := append(lenBuf, data...)
	_, err = w.Write(buf)
	return err
}

func NewDataFrame(payload []byte) *Frame {
	return &Frame{Type: FrameData, Payload: payload}
}

func NewKeepaliveFrame() *Frame {
	return &Frame{Type: FrameKeepalive, Payload: nil}
}

func NewCloseFrame() *Frame {
	return &Frame{Type: FrameClose, Payload: nil}
}

func NewControlFrame(payload []byte) *Frame {
	return &Frame{Type: FrameControl, Payload: payload}
}

func randInt(min, max int) (int, error) {
	if min >= max {
		return min, nil
	}
	n, err := rand.Int(rand.Reader, big.NewInt(int64(max-min)))
	if err != nil {
		return 0, err
	}
	return min + int(n.Int64()), nil
}
