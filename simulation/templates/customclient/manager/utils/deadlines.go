package utils

import (
	"net"
	"time"
)

func SetDeadlines(timeout time.Duration, r net.Conn, w net.Conn) error {
	deadline := time.Now().Add(timeout)

	err := r.SetReadDeadline(deadline)
	if err != nil {
		return err
	}

	err = w.SetWriteDeadline(deadline)
	if err != nil {
		return err
	}

	return nil
}
