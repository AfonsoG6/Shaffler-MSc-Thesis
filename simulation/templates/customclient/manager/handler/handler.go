package handler

import (
	"io"
	"net"
	"strconv"
	"sync"
	"time"

	myUtils "rendezmix/manager/utils"

	pt "git.torproject.org/pluggable-transports/goptlib.git"
	slog "golang.org/x/exp/slog"
)

const (
	label = "HANDLER"
)

type Handler struct {
	Id      string
	tag     string
	timeout time.Duration
	conn    *pt.SocksConn
}

func NewHandler(id string, timeout time.Duration, conn *pt.SocksConn) *Handler {
	handler := &Handler{
		Id:      id,
		tag:     "[ " + label + " " + id + " ]",
		timeout: timeout,
		conn:    conn,
	}
	return handler
}

func (handler *Handler) exchange(timeout time.Duration, a, b net.Conn) {
	who := handler.tag
	var wg sync.WaitGroup
	wg.Add(2)

	err := myUtils.SetDeadlines(timeout, a, b)
	if err != nil {
		slog.Error(who + " error setting the initial deadlines: " + err.Error())
	}

	// Start goroutine to copy from "a" to "b"
	go func(wg *sync.WaitGroup) {
		defer wg.Done()
		n, err := myUtils.CopyWithTimeout(timeout, b, a)
		if err != nil {
			if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
				slog.Debug(who + " reading timeout occurred, terminating copy:")
			} else if err == io.EOF {
				slog.Debug(who + " EOF reached, terminating copy:")
			} else {
				slog.Error(who+" error performing copy operation: ", err.Error())
			}
		} else {
			slog.Error(who + " NEVER HAPPENS")
		}
		slog.Debug(who + " " + a.RemoteAddr().String() + " --- " + strconv.FormatInt(n, 10) + " ---> " + b.RemoteAddr().String())
	}(&wg)

	// Start goroutine to copy from "b" to "a"
	go func(wg *sync.WaitGroup) {
		defer wg.Done()
		n, err := myUtils.CopyWithTimeout(timeout, a, b)
		if err != nil {
			if netErr, ok := err.(net.Error); ok && netErr.Timeout() {
				slog.Debug(who + " reading timeout occurred, terminating copy:")
			} else if err == io.EOF {
				slog.Debug(who + " EOF reached, terminating copy:")
			} else {
				slog.Error(who+" error performing copy operation: ", err.Error())
			}
		} else {
			slog.Error(who + " NEVER HAPPENS")
		}
		slog.Debug(who + " " + b.RemoteAddr().String() + " --- " + strconv.FormatInt(n, 10) + " ---> " + a.RemoteAddr().String())
	}(&wg)

	wg.Wait()
}

func (handler *Handler) Handle() {
	who := handler.tag
	conn := handler.conn

	defer func() {
		slog.Debug(who + " terminating")
	}()

	defer func() {
		slog.Debug(who + " closing client (" + conn.RemoteAddr().String() + ") connection")
		conn.Close()
	}()

	slog.Info(who + " started")

	remote, err := net.Dial("tcp", conn.Req.Target)
	if err != nil {
		conn.Reject()
		slog.Error(who + " connection to remote (" + conn.Req.Target + ") failed: " + err.Error())
		return
	}

	defer func() {
		slog.Debug(who + " closing remote connection to " + remote.RemoteAddr().String())
		remote.Close()
	}()

	slog.Debug(who + " successfully connected to remote (" + remote.RemoteAddr().String() + ")")

	err = conn.Grant(remote.RemoteAddr().(*net.TCPAddr))
	if err != nil {
		return
	}

	slog.Debug(who + " exchanging data between " + conn.RemoteAddr().String() + " and " + remote.RemoteAddr().String())
	handler.exchange(handler.timeout, conn.Conn, remote)

	return
}
