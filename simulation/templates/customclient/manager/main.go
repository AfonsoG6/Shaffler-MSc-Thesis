package main

import (
	"fmt"
	"os"
	"os/signal"
	myConfig "rendezmix/manager/config"
	myListener "rendezmix/manager/listener"
	myUtils "rendezmix/manager/utils"
	"strconv"
	"sync"
	"syscall"
	"time"

	slog "golang.org/x/exp/slog"
)

const (
	TOR_OK uint8 = 1 << iota
	GUNICORN_OK
	NGINX_OK
	CC_OK
	TBB_OK

	OS_OK    = TOR_OK | GUNICORN_OK | NGINX_OK
	COVER_OK = OS_OK | CC_OK
	ALL_OK   = COVER_OK | TBB_OK

	tag = "[ MAIN ]"
)

var (
	STATE          uint8
	torStatus      int8
	gunicornStatus int8
	nginxStatus    int8
	ccStatus       int8
	tbStatus       int8
)

func createListener(nListener int, config myConfig.ListenerConfig) *myListener.Listener {
	network := config.Network
	laddr := config.Address + ":" + config.Port
	copyTimeout := config.HandlerTimeout * time.Millisecond
	slog.Info(tag + " creating socks listener on " + laddr)

	listener, err := myListener.NewListener(strconv.Itoa(nListener), network, laddr, copyTimeout)
	if err != nil {
		slog.Error(tag + " error creating listener: " + err.Error())
	} else {
		slog.Debug(tag + " created listener " + listener.Id)
	}
	return listener
}

func deployListener(listener *myListener.Listener, wg *sync.WaitGroup) {
	defer func() {
		slog.Info(tag + " listener " + listener.Id + " terminated")
		wg.Done()
	}()
	slog.Debug(tag + " starting listener " + listener.Id)
	listener.Listen()
}

func terminate() {
	// slog.Debug(tag + " closing socks listeners")
	// for _, ln := range listeners {
	// 	ln.Close()
	// 	slog.Debug(tag + " socks listener terminated")
	// }
}

func main() {
	// Read configuration
	config, err := myConfig.ReadConfig()
	if err != nil {
		fmt.Println("Fatal error reading configuration: " + err.Error())
		return
	}

	// Config logs
	err = myUtils.SetupLog(config.LogsCfg)
	if err != nil {
		fmt.Println("Fatal error setting up the log: " + err.Error())
		return
	}

	// Create a signal channel that listens to SIGTERM, SIGINT and SIGHUP
	// to terminate the program signals
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGTERM, syscall.SIGINT, syscall.SIGHUP)

	slog.Info(tag + " manager started")
	defer slog.Info(tag + " manager terminated")

	var listenerWg sync.WaitGroup
	// defer listenerWg.Wait()
	var listeners []*myListener.Listener

	// Create SOCKS listeners and deploy them
	for i, listenerCfg := range config.ListenerCfgs {
		listener := createListener(i+1, listenerCfg)
		listeners = append(listeners, listener)
		listenerWg.Add(1)
		go deployListener(listener, &listenerWg)
	}

	// Launch system components
	var launcherWg sync.WaitGroup
	// defer launcherWg.Wait()
	exitChannel := make(chan struct{})
	launcherWg.Add(1)
	var nLaunchers int

	browserLauncher := myUtils.NewLauncher("BROWSER", &config.LauncherCfg, exitChannel)
	go browserLauncher.LaunchTorBrowser(&launcherWg)
	nLaunchers++
	// nginxLauncher := myUtils.NewLauncher("NGINX", &config.LauncherCfg, exitChannel)
	// go nginxLauncher.LaunchNginx(&launcherWg)
	// if <-nginxLauncher.StatusChannel == 1 { //launcher started
	// 	if <-nginxLauncher.StatusChannel == 0 { // and started nginx successfully
	// 		launcherWg.Add(1)
	// 		go nginxLauncher.NginxHealthCheck(&launcherWg)
	// 		nLaunchers++
	// 	}
	// } else {
	// 	return
	// }

	for {
		select {
		case status := <-browserLauncher.StatusChannel:
			slog.Info(tag + " STATUS: " + strconv.FormatInt(int64(status), 10))
			if status == -1 {
				return
			}
			if status == 0 {
				nLaunchers--
			}
		case <-sigChan:
			slog.Info(tag + " signal received, terminating")
			close(exitChannel)
		default:
			if nLaunchers == 0 {
				launcherWg.Wait()
				return
			}
		}
	}
	// torLauncher := myUtils.NewLauncher("TOR", &config.LauncherCfg, exitChannel)
	// gunicornLauncher := myUtils.NewLauncher("GUNICORN", &config.LauncherCfg, exitChannel)
	// nginxLauncher := myUtils.NewLauncher("NGINX", &config.LauncherCfg, exitChannel)
	// coverClientLauncher := myUtils.NewLauncher("COVER_CLIENT", &config.LauncherCfg, exitChannel)
	// browserLauncher := myUtils.NewLauncher("BROWSER", &config.LauncherCfg, exitChannel)

	// // The OS can run without Tor (although not really useful)
	// // so we can launch them simultaneously
	// launcherWg.Add(3)
	// go torLauncher.LaunchTor(&launcherWg)
	// go gunicornLauncher.LaunchGunicorn(&launcherWg)
	// go nginxLauncher.LaunchNginx(&launcherWg)

	// // Initial status update
	// torStatus = <-torLauncher.StatusChannel
	// gunicornStatus = <-gunicornLauncher.StatusChannel
	// nginxStatus = <-nginxLauncher.StatusChannel
	// if torStatus == -1 || gunicornStatus == -1 || nginxStatus == -1 {
	// 	slog.Error("FATAL ERROR") // change this behavior
	// 	return
	// } else { // It can only be 1s
	// 	STATE = uint8((torStatus << 0) | (gunicornStatus << 1) | (nginxStatus << 2))
	// }

	// // When Tor and the OS are both running, we can launch the cover client
	// if STATE == OS_OK {
	// 	launcherWg.Add(1)
	// 	go coverClientLauncher.LaunchCClient(&launcherWg)

	// 	// Initial status update
	// 	ccStatus = <-coverClientLauncher.StatusChannel
	// 	if ccStatus == -1 {
	// 		slog.Error("FATAL ERROR") // change this behavior
	// 		return
	// 	} else { // Can only be 1
	// 		STATE = STATE | uint8(tbStatus<<3)
	// 	}
	// }

	// // Finally, when the cover infrastructure is running we can launch the
	// // Tor Browser for the user to interact with
	// if STATE == COVER_OK {
	// 	launcherWg.Add(1)
	// 	go browserLauncher.LaunchTorBrowser(&launcherWg)
	// 	// Initial status update
	// 	tbStatus = <-browserLauncher.StatusChannel
	// 	if tbStatus == -1 {
	// 		slog.Error("FATAL ERROR") // change this behavior
	// 		return
	// 	} else { // Can only be 1
	// 		STATE = STATE | uint8(tbStatus<<3)
	// 	}
	// }

	// // Once everything is running, loop through every channel until
	// // signaled to stop or until an error occurs
	// for STATE == ALL_OK {
	// 	select {
	// 	case <-sigChan:
	// 		slog.Info(tag + " signal received, terminating")
	// 		terminate()
	// 	}
	// }
}
