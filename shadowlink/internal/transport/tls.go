package transport

import (
	"crypto/tls"
	"errors"
	"net"

	utls "github.com/refraction-networking/utls"
)

type TLSMode int

const (
	TLSModeUTLS   TLSMode = iota // Client: use uTLS to mimic Chrome
	TLSModeNative                // Server: use standard Go TLS
)

// DialUTLS establishes a TLS connection mimicking a Chrome browser fingerprint.
func DialUTLS(addr, sni string) (net.Conn, error) {
	rawConn, err := net.Dial("tcp", addr)
	if err != nil {
		return nil, err
	}

	config := &utls.Config{
		ServerName:         sni,
		InsecureSkipVerify: false,
	}

	tlsConn := utls.UClient(rawConn, config, utls.HelloChrome_Auto)
	if err := tlsConn.Handshake(); err != nil {
		rawConn.Close()
		return nil, err
	}

	return tlsConn, nil
}

// DialUTLSInsecure is for testing / self-signed certificates.
func DialUTLSInsecure(addr, sni string) (net.Conn, error) {
	rawConn, err := net.Dial("tcp", addr)
	if err != nil {
		return nil, err
	}

	config := &utls.Config{
		ServerName:         sni,
		InsecureSkipVerify: true,
	}

	tlsConn := utls.UClient(rawConn, config, utls.HelloChrome_Auto)
	if err := tlsConn.Handshake(); err != nil {
		rawConn.Close()
		return nil, err
	}

	return tlsConn, nil
}

// NewTLSListener creates a standard TLS listener for the server side.
func NewTLSListener(addr, certFile, keyFile string) (net.Listener, error) {
	cert, err := tls.LoadX509KeyPair(certFile, keyFile)
	if err != nil {
		return nil, err
	}

	config := &tls.Config{
		Certificates: []tls.Certificate{cert},
		MinVersion:   tls.VersionTLS13,
		CipherSuites: []uint16{
			tls.TLS_AES_256_GCM_SHA384,
			tls.TLS_CHACHA20_POLY1305_SHA256,
			tls.TLS_AES_128_GCM_SHA256,
		},
	}

	return tls.Listen("tcp", addr, config)
}

// NewTLSConfig creates a TLS config from cert/key for use with HTTP servers.
func NewTLSConfig(certFile, keyFile string) (*tls.Config, error) {
	if certFile == "" || keyFile == "" {
		return nil, errors.New("cert and key files are required")
	}

	cert, err := tls.LoadX509KeyPair(certFile, keyFile)
	if err != nil {
		return nil, err
	}

	return &tls.Config{
		Certificates: []tls.Certificate{cert},
		MinVersion:   tls.VersionTLS13,
	}, nil
}
