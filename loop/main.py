from client import run_client
from utils import StoppableThread, sleep, log
from server import run_server
from tortypes import Node
import control

from threading import Thread
import argparse

UPDATE_INTERVAL = 1 # in seconds

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--server_host", "-svh", type=str, default="127.0.0.1")
    parser.add_argument("--server_port", "-svp", type=int, default=29999)
    parser.add_argument("--ctrl_port1", "-cp1", type=int, default=-1)
    parser.add_argument("--ctrl_port2", "-cp2", type=int, default=-1)
    parser.add_argument("--socks_port2", "-sp2", type=int, default=-1)
    args = parser.parse_args()
    
    server_thread = Thread(target=run_server, args=[args.server_host, args.server_port])
    server_thread.daemon = True
    server_thread.start()
    log("THREADS", f"Server started on port {args.server_port}")
    
    prev_exit_nodes: list[Node] = []
    client_threads: dict[str, StoppableThread] = {}
    while True:
        exit_nodes: list[Node] = control.get_exit_nodes(args.ctrl_port1)
        if exit_nodes != prev_exit_nodes:
            prev_exit_nodes = exit_nodes
            control.set_exit_nodes(args.ctrl_port2, exit_nodes)
            new_threads: dict[str, StoppableThread] = {}
            for node in exit_nodes:
                if node.fingerprint in client_threads.keys():
                    log("THREADS", f"Reusing client for exit node {node.fingerprint}~{node.name}")
                    new_threads[node.fingerprint] = client_threads[node.fingerprint]
                    client_threads.pop(node.fingerprint)
                else:
                    log("THREADS", f"Launching new client for exit node {node.fingerprint}~{node.name}")
                    new_threads[node.fingerprint] = StoppableThread(target=run_client, args=[args.server_host, args.server_port, args.socks_port2])
                    new_threads[node.fingerprint].daemon = True
                    new_threads[node.fingerprint].start()
            # Stop old threads
            for thread in client_threads.values():
                thread.stop()
            client_threads = new_threads
        sleep(UPDATE_INTERVAL)
