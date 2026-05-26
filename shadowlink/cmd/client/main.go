package main

import (
	"context"
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"

	"gopkg.in/yaml.v3"

	"github.com/user/shadowlink/internal/obfuscation"
	"github.com/user/shadowlink/internal/proxy"
	"github.com/user/shadowlink/internal/transport"
)

type ClientConfig struct {
	Client struct {
		ListenAddr string `yaml:"listen_addr"`
		ServerAddr string `yaml:"server_addr"`
		ServerSNI  string `yaml:"server_sni"`
		WSPath     string `yaml:"ws_path"`
		AuthToken  string `yaml:"auth_token"`
		UseTLS     bool   `yaml:"use_tls"`
		Insecure   bool   `yaml:"insecure"`
	} `yaml:"client"`
	CDN          transport.CDNConfig            `yaml:"cdn"`
	Obfuscation  struct {
		Padding      obfuscation.PaddingConfig       `yaml:"padding"`
		Timing       obfuscation.TimingConfig         `yaml:"timing"`
		TrafficShape obfuscation.TrafficShapeConfig   `yaml:"traffic_shape"`
	} `yaml:"obfuscation"`
}

func main() {
	configPath := flag.String("config", "config/client.yaml", "path to client config file")
	flag.Parse()

	cfg, err := loadConfig(*configPath)
	if err != nil {
		log.Fatalf("failed to load config: %v", err)
	}

	clientCfg := proxy.ClientConfig{
		ListenAddr:   cfg.Client.ListenAddr,
		ServerAddr:   cfg.Client.ServerAddr,
		ServerSNI:    cfg.Client.ServerSNI,
		WSPath:       cfg.Client.WSPath,
		AuthToken:    cfg.Client.AuthToken,
		UseTLS:       cfg.Client.UseTLS,
		Insecure:     cfg.Client.Insecure,
		CDN:          cfg.CDN,
		Padding:      cfg.Obfuscation.Padding,
		Timing:       cfg.Obfuscation.Timing,
		TrafficShape: cfg.Obfuscation.TrafficShape,
	}

	client := proxy.NewClient(clientCfg)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	log.Println("[shadowlink] connecting to server...")
	if err := client.Connect(ctx); err != nil {
		log.Fatalf("connection failed: %v", err)
	}
	log.Println("[shadowlink] connected successfully")

	go func() {
		if err := client.RunSOCKS5(ctx); err != nil {
			log.Fatalf("SOCKS5 proxy error: %v", err)
		}
	}()

	log.Printf("[shadowlink] SOCKS5 proxy listening on %s", cfg.Client.ListenAddr)
	log.Println("[shadowlink] configure your browser/system to use SOCKS5 proxy at", cfg.Client.ListenAddr)

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	<-sigCh

	log.Println("[shadowlink] shutting down...")
	client.Close()
	log.Println("[shadowlink] client stopped")
}

func loadConfig(path string) (*ClientConfig, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	cfg := &ClientConfig{}
	if err := yaml.Unmarshal(data, cfg); err != nil {
		return nil, err
	}

	if cfg.Client.ListenAddr == "" {
		cfg.Client.ListenAddr = "127.0.0.1:1080"
	}
	if cfg.Client.WSPath == "" {
		cfg.Client.WSPath = "/ws"
	}

	return cfg, nil
}
