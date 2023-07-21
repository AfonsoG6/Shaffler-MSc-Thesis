package config

import (
	"encoding/json"
	"os"
	"time"
)

type Config struct {
	LauncherCfg  LauncherConfig   `json:"launcher"`
	LogsCfg      LogConfig        `json:"logs"`
	ListenerCfgs []ListenerConfig `json:"listeners"`
}

type LauncherConfig struct {
	TbbPath     string         `json:"tbb_exec_path"`
	TorPath     string         `json:"tor_exec_path"`
	TorrcPath   string         `json:"torrc_path"`
	CClientCfg  CClientConfig  `json:"cclient"`
	NginxCfg    NginxConfig    `json:"nginx"`
	GunicornCfg GunicornConfig `json:"gunicorn"`
}

type CClientConfig struct {
	PythonPath  string `json:"python_exec_path"`
	CClientPath string `json:"cclient_exec_path"`
}

type NginxConfig struct {
	ExecPath      string        `json:"exec_path"`
	StatusAddress string        `json:"status_address"`
	CheckPeriod   time.Duration `json:"check_period"`
}

type GunicornConfig struct {
	ExecPath    string `json:"exec_path"`
	BindAddress string `json:"bind_address"`
	LogFile     string `json:"log_file"`
	AppPath     string `json:"app_path"`
}

type LogConfig struct {
	LogFile      string `json:"log_file"`
	TruncateFile bool   `json:"truncate_file"`
	LogLevel     string `json:"log_level"`
}

type ListenerConfig struct {
	Network        string        `json:"network"`
	Address        string        `json:"address"`
	Port           string        `json:"port"`
	HandlerTimeout time.Duration `json:"handler_timeout"`
}

const (
	configFile = "config.json"
)

func ReadConfig() (Config, error) {
	var config Config
	file, err := os.Open(configFile)
	defer file.Close()
	if err != nil {
		return config, err
	}

	parser := json.NewDecoder(file)
	parser.Decode(&config)

	return config, nil
}
