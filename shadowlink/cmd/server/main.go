package main

import (
	"context"
	"flag"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"gopkg.in/yaml.v3"

	"github.com/user/shadowlink/internal/api"
	"github.com/user/shadowlink/internal/obfuscation"
	"github.com/user/shadowlink/internal/proxy"
	"github.com/user/shadowlink/internal/transport"
)

type ServerConfig struct {
	Server struct {
		ListenAddr string `yaml:"listen_addr"`
		WSPath     string `yaml:"ws_path"`
		TLSCert    string `yaml:"tls_cert"`
		TLSKey     string `yaml:"tls_key"`
		DecoyDir   string `yaml:"decoy_dir"`
	} `yaml:"server"`
	Bridge struct {
		ListenAddr string `yaml:"listen_addr"`
		APIKey     string `yaml:"api_key"`
	} `yaml:"bridge"`
	Obfuscation struct {
		Padding      obfuscation.PaddingConfig      `yaml:"padding"`
		Timing       obfuscation.TimingConfig        `yaml:"timing"`
		TrafficShape obfuscation.TrafficShapeConfig  `yaml:"traffic_shape"`
	} `yaml:"obfuscation"`
	Sessions struct {
		IdleTimeout     string `yaml:"idle_timeout"`
		CleanupInterval string `yaml:"cleanup_interval"`
		MaxPerToken     int    `yaml:"max_per_token"`
	} `yaml:"sessions"`
}

func main() {
	configPath := flag.String("config", "config/server.yaml", "path to server config file")
	flag.Parse()

	cfg, err := loadConfig(*configPath)
	if err != nil {
		log.Fatalf("failed to load config: %v", err)
	}

	relay := proxy.NewServerRelay(nil, cfg.Obfuscation.Padding, cfg.Obfuscation.Timing)

	bridge := api.NewBridgeServer(cfg.Bridge.APIKey, relay)

	// Wire up auth function: the bridge validates tokens
	authRelay := proxy.NewServerRelay(bridge.AuthenticateToken, cfg.Obfuscation.Padding, cfg.Obfuscation.Timing)

	mux := http.NewServeMux()

	mux.HandleFunc(cfg.Server.WSPath, transport.WSHandler(func(conn *transport.WSConn, r *http.Request) {
		authRelay.HandleConnection(conn)
	}))

	mux.Handle("/", transport.ServeDecoy(cfg.Server.DecoyDir))

	mainServer := &http.Server{
		Addr:    cfg.Server.ListenAddr,
		Handler: mux,
	}

	bridgeServer := &http.Server{
		Addr:    cfg.Bridge.ListenAddr,
		Handler: bridge,
	}

	// Start session cleanup goroutine
	idleTimeout, _ := time.ParseDuration(cfg.Sessions.IdleTimeout)
	if idleTimeout == 0 {
		idleTimeout = 5 * time.Minute
	}
	cleanupInterval, _ := time.ParseDuration(cfg.Sessions.CleanupInterval)
	if cleanupInterval == 0 {
		cleanupInterval = 1 * time.Minute
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go func() {
		ticker := time.NewTicker(cleanupInterval)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				// Session cleanup is handled internally
			}
		}
	}()

	go func() {
		log.Printf("[shadowlink] bridge API listening on %s", cfg.Bridge.ListenAddr)
		if err := bridgeServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("bridge server error: %v", err)
		}
	}()

	go func() {
		if cfg.Server.TLSCert != "" && cfg.Server.TLSKey != "" {
			log.Printf("[shadowlink] server listening on %s (TLS)", cfg.Server.ListenAddr)
			if err := mainServer.ListenAndServeTLS(cfg.Server.TLSCert, cfg.Server.TLSKey); err != nil && err != http.ErrServerClosed {
				log.Fatalf("main server error: %v", err)
			}
		} else {
			log.Printf("[shadowlink] server listening on %s (plain, expects TLS termination by reverse proxy)", cfg.Server.ListenAddr)
			if err := mainServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
				log.Fatalf("main server error: %v", err)
			}
		}
	}()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	log.Println("[shadowlink] shutting down...")
	cancel()

	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()

	mainServer.Shutdown(shutdownCtx)
	bridgeServer.Shutdown(shutdownCtx)
	log.Println("[shadowlink] server stopped")
}

func loadConfig(path string) (*ServerConfig, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	cfg := &ServerConfig{}
	if err := yaml.Unmarshal(data, cfg); err != nil {
		return nil, err
	}

	if cfg.Server.ListenAddr == "" {
		cfg.Server.ListenAddr = "0.0.0.0:8443"
	}
	if cfg.Server.WSPath == "" {
		cfg.Server.WSPath = "/ws"
	}
	if cfg.Bridge.ListenAddr == "" {
		cfg.Bridge.ListenAddr = "127.0.0.1:9090"
	}

	return cfg, nil
}
