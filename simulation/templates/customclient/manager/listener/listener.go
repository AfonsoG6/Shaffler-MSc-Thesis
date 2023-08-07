package listener

import (
	"errors"
	"net"
	"strconv"
	"sync"
	"time"

	mHandler "rendezmix/manager/handler"

	pt "git.torproject.org/pluggable-transports/goptlib.git"
	slog "golang.org/x/exp/slog"
)

const (
	label = "LISTENER"
)

type Listener struct {
	Id            string
	tag           string
	network       string
	laddr         string
	socksListener *pt.SocksListener
	timeout       time.Duration
}

func NewListener(id string, network string, addr string, timeout time.Duration) (*Listener, error) {
	socksLn, err := pt.ListenSocks(network, addr)
	ln := &Listener{
		Id:            id,
		tag:           "[ " + label + " " + id + " ]",
		network:       network,
		laddr:         addr,
		socksListener: socksLn,
		timeout:       timeout,
	}

	return ln, err
}
func (listener *Listener) Close() {
	defer listener.socksListener.Close()

	who := listener.tag
	slog.Debug(who + " closing socks listener")
}

func (listener *Listener) Listen() {
	who := listener.tag
	ln := listener.socksListener
	id := listener.Id
	timeout := listener.timeout

	var nConns int

	// Wait group for handler goroutines
	var myWg sync.WaitGroup

	defer func() {
		slog.Debug(who + " waiting for handlers to finish")
		myWg.Wait()
		slog.Debug(who + " terminating")
		ln.Close()
	}()

	slog.Info(who + " started")

	// Accept loop
	for {
		// Listen for connections, create them and launch handler goroutine
		conn, err := ln.AcceptSocks()
		if err != nil {
			if e, ok := err.(net.Error); ok && errors.Is(e, net.ErrClosed) {
				slog.Debug(who + " listener was closed, terminating")
			} else {
				slog.Error(who + " fatal error accepting connection: " + err.Error())
			}
			return
		}
		slog.Debug(who + " opened new socks connection to " + conn.RemoteAddr().String())
		nConns++
		slog.Debug(who + " total connections since launch: " + strconv.Itoa(nConns))

		handler := mHandler.NewHandler(id+"."+strconv.Itoa(nConns), timeout, conn)

		myWg.Add(1)
		go func(handler *mHandler.Handler, wg *sync.WaitGroup) {
			defer func() {
				slog.Info(who + " handler " + handler.Id + " terminated")
				wg.Done()
			}()
			slog.Debug(who + " starting handler " + handler.Id)
			handler.Handle()
		}(handler, &myWg)
	}
}
