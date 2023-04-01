import requests
import argparse
from threading import current_thread, Thread, Event

class StoppableThread(Thread):
    def __init__(self,  *args, **kwargs):
        super(StoppableThread, self).__init__(*args, **kwargs)
        self.stop_event = Event()

    def stop(self):
        self.stop_event.set()
        self.join(0.5)

    def stopped(self):
        return self.stop_event.is_set()

def run_client(server_host:str, server_port:int, socks_port:int = -1):
    url = f"https://{server_host}:{server_port}"
    socks5 = f"socks5://localhost:{socks_port}"
    
    with requests.Session() as s:
        s.verify = False # Ignore verification of server certificate
        if socks_port > 0:
            s.proxies = {"http": socks5, "https": socks5}

        thread = current_thread()
        if not isinstance(thread, StoppableThread):
            raise Exception("This function must be run in a StoppableThread")
        
        while not thread.stopped():
            response = s.get(url)
            print(response.content)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--server_host", "-svh", type=str, default="127.0.0.1")
    parser.add_argument("--server_port", "-svp", type=int, default=29999)
    parser.add_argument("--socks_port", "-sp", type=int, default=-1)
    args = parser.parse_args()
    run_client(args.server_host, args.server_port, args.socks_port)