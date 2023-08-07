package utils

import (
	"errors"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	myConfig "rendezmix/manager/config"
	"sync"
	"time"

	"golang.org/x/exp/slog"
)

const (
	label = "LAUNCHER"
)

type Launcher struct {
	tag           string
	exitChannel   <-chan struct{}
	StatusChannel chan int8
	configs       myConfig.LauncherConfig
}

func NewLauncher(role string, configs *myConfig.LauncherConfig, exitChannel <-chan struct{}) *Launcher {
	launcher := &Launcher{
		tag:           "[ " + label + " - " + role + " ]",
		exitChannel:   exitChannel,
		StatusChannel: make(chan int8),
		configs:       *configs,
	}

	return launcher
}

func (launcher *Launcher) LaunchTor(wg *sync.WaitGroup) {
	who := launcher.tag
	service := "Tor"
	var myWg sync.WaitGroup // for process monitor

	defer func() {
		myWg.Wait()
		wg.Done() // main's wait group
	}()

	torPath := launcher.configs.TorPath
	torrcPath := launcher.configs.TorrcPath
	cmd := exec.Command(torPath, "-f", torrcPath)

	launchProcess(who, service, &myWg, cmd, launcher.exitChannel, launcher.StatusChannel)
}

func (launcher *Launcher) LaunchGunicorn(wg *sync.WaitGroup) {
	who := launcher.tag
	service := "Gunicorn"
	var myWg sync.WaitGroup // for process monitor

	defer func() {
		myWg.Wait()
		wg.Done() // main's wait group
	}()

	gunicornExecPath := launcher.configs.GunicornCfg.ExecPath
	gunicornAddress := launcher.configs.GunicornCfg.BindAddress
	gunicornLogFile := launcher.configs.GunicornCfg.LogFile
	gunicornAppPath := launcher.configs.GunicornCfg.AppPath
	cmd := exec.Command(gunicornExecPath, "-b", gunicornAddress, "--log-file", gunicornLogFile, "--access-logfile", gunicornLogFile, "--chdir", gunicornAppPath, "app:app")

	launchProcess(who, service, &myWg, cmd, launcher.exitChannel, launcher.StatusChannel)
}

func (launcher *Launcher) LaunchNginx(wg *sync.WaitGroup) {
	who := launcher.tag
	service := "Nginx Launcher"
	var myWg sync.WaitGroup // for process monitor

	defer func() {
		myWg.Wait()
		wg.Done() // main's wait group
	}()

	nginxPath := launcher.configs.NginxCfg.ExecPath
	cmd := exec.Command(nginxPath)

	launchProcess(who, service, &myWg, cmd, launcher.exitChannel, launcher.StatusChannel)
}

func (launcher *Launcher) NginxHealthCheck(wg *sync.WaitGroup) {
	who := launcher.tag
	service := "Nginx Health Check"
	period := launcher.configs.NginxCfg.CheckPeriod
	address := launcher.configs.NginxCfg.StatusAddress
	nginxPath := launcher.configs.NginxCfg.ExecPath
	exitChannel := launcher.exitChannel
	statusChannel := launcher.StatusChannel

	defer func() {
		wg.Done()
	}()

	slog.Info(who + " " + service + " started")
	statusChannel <- 1

	ticker := time.NewTicker(period * time.Millisecond)
	for {
		select {
		case <-ticker.C:
			resp, err := http.Get(address)
			if err != nil {
				slog.Error(who + " Nginx health check error: " + err.Error())
				statusChannel <- 0
				return
			}

			if resp.StatusCode == 200 {
				continue
			} else {
				slog.Error(who + " Unexpected Nginx response code: " + resp.Status)
			}

		case _, ok := <-exitChannel:
			if !ok { // if general purpose exit channel is closed
				slog.Debug(who + " Exit channel closed, stopping " + service)
				launcher.closeNginx(nginxPath)
				statusChannel <- 0
				return
			} else { // Shouldn't happen - main is not supposed to write to the exit channel
				slog.Error(who + " Received message on the exit channel")
				statusChannel <- -1
				return
			}
		case <-statusChannel: // status channel for main (only RECEIVES exit signals)
			slog.Debug(who + " Exit signal received, stopping " + service)
			launcher.closeNginx(nginxPath)
			statusChannel <- 0
			return
		}
	}
}

func (launcher *Launcher) closeNginx(nginxPath string) {
	who := launcher.tag
	slog.Debug(who + " Stopping Nginx")
	cmd := exec.Command(nginxPath, "-s", "stop")
	cmd.Run()
	slog.Debug(who + " Nginx stopped")
}

func (launcher *Launcher) LaunchCClient(wg *sync.WaitGroup) {
	who := launcher.tag
	service := "Cover Client"
	var myWg sync.WaitGroup // for process monitor

	defer func() {
		myWg.Wait()
		wg.Done() // main's wait group
	}()

	pythonPath := launcher.configs.CClientCfg.PythonPath
	ccPath := launcher.configs.CClientCfg.CClientPath
	cmd := exec.Command(pythonPath, ccPath)

	launchProcess(who, service, &myWg, cmd, launcher.exitChannel, launcher.StatusChannel)
}

func (launcher *Launcher) LaunchTorBrowser(wg *sync.WaitGroup) {
	who := launcher.tag
	service := "Tor Browser"
	var myWg sync.WaitGroup // for process monitor

	defer func() {
		myWg.Wait()
		wg.Done() // main's wait group
	}()

	tbbExecPath := launcher.configs.TbbPath
	fmt.Println(tbbExecPath)
	cmd := exec.Command(tbbExecPath)

	launchProcess(who, service, &myWg, cmd, launcher.exitChannel, launcher.StatusChannel)
}

func stop(cmd *exec.Cmd) error {
	err := cmd.Process.Kill()
	if err != nil && !os.IsNotExist(err) && err != os.ErrProcessDone {
		return err
	}
	return nil
}

func launchProcess(who string, service string, wg *sync.WaitGroup, cmd *exec.Cmd, exitChannel <-chan struct{}, statusChannel chan int8) {
	slog.Debug(who + " Launching " + service)
	cmd.Stdout = os.Stdout
	err := cmd.Start()
	if err != nil {
		slog.Error(who + " Error launching " + service + ": " + err.Error())
		statusChannel <- -1
		return
	} else {
		process := cmd.Process
		monitorChannel := make(chan error) // to communicate with the monitor

		wg.Add(1)
		go func() {
			defer wg.Done()

			state, err := process.Wait()
			if err == nil && !state.Success() {
				monitorChannel <- errors.New(state.String())
			} else {
				monitorChannel <- err
			}
			return
		}()

		slog.Info(who + " " + service + " started")
		statusChannel <- 1

		for {
			select {
			case _, ok := <-exitChannel:
				if !ok { // if general purpose exit channel is closed
					slog.Debug(who + " Exit channel closed, stopping " + service)
					err := stop(cmd)
					if err != nil {
						slog.Error(who + " Error stopping " + service + ": " + err.Error())
						statusChannel <- -1 // when error occurs
						wg.Done()           // don't wait for monitoring goroutine to be done
						return
					} else {
						err = <-monitorChannel // only listen to monitor channel, ignore the others
						if err != nil {
							slog.Debug(who + " " + service + " process monitor channel returned: " + err.Error())
							statusChannel <- -1
						} else {
							slog.Debug(who + " " + service + " process monitor channel returned successfully")
							statusChannel <- 0
						}
						close(monitorChannel)
						return
					}
				} else { // Shouldn't happen - main is not supposed to write to the exit channel
					slog.Error(who + " Received message on the exit channel")
				}
			case <-statusChannel: // status channel for main (only RECEIVES exit signals)
				slog.Debug(who + " Exit signal received, stopping " + service)
				err := stop(cmd)
				if err != nil {
					slog.Error(who + " Error stopping " + service + ": " + err.Error())
					statusChannel <- -1
					wg.Done()
					return
				} else {
					err = <-monitorChannel // only listen to monitor channel, ignore the others
					if err != nil {
						slog.Debug(who + " " + service + " process monitor channel returned: " + err.Error())
						statusChannel <- -1
					} else {
						slog.Debug(who + " " + service + " process monitor channel returned successfully")
						statusChannel <- 0
					}
					close(monitorChannel)
					return
				}
			case err = <-monitorChannel: // process monitor channel
				if err != nil {
					slog.Debug(who + " " + service + " process monitor channel returned: " + err.Error())
					statusChannel <- -1
				} else {
					slog.Debug(who + " " + service + " process monitor channel returned successfully")
					statusChannel <- 0
				}
				close(monitorChannel)
				return
			}
		}
	}
}
