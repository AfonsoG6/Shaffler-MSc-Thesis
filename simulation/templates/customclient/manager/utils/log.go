package utils

import (
	"log"
	"os"
	myConfig "rendezmix/manager/config"

	"golang.org/x/exp/slog"
)

func SetupLog(config myConfig.LogConfig) error {
	logLevel := new(slog.LevelVar)
	var level slog.Level
	switch config.LogLevel {
	case "Debug":
		level = slog.LevelDebug
	case "Error":
		level = slog.LevelError
	case "Info":
		level = slog.LevelInfo
	case "Warn":
		level = slog.LevelWarn
	default:
		log.Fatal("Log level not recognized")
	}

	flag := os.O_CREATE | os.O_WRONLY
	if config.TruncateFile {
		flag = flag | os.O_TRUNC
	} else {
		flag = flag | os.O_APPEND
	}

	logFile, err := os.OpenFile(config.LogFile, flag, 0600)
	if err == nil {
		h := slog.NewTextHandler(logFile, &slog.HandlerOptions{Level: logLevel})
		slog.SetDefault(slog.New(h))
		logLevel.Set(level)
	}
	return err
}
