from client import run_client
from utils import StoppableThread, sleep, log
from server import run_server
from tortypes import Node
import control

from threading import Thread
import argparse

UPDATE_INTERVAL = 1 # in seconds

class Loop:
    id: int
    exit: Node
    client_thread: StoppableThread
    server_thread: StoppableThread
    
    def __init__(self, id: int, exit: Node, server_host: str, server_port: int, ctrl_port2: int, socks_port: int):
        self.id = id
        self.exit = exit
        control.map_address(ctrl_port2, f"{server_host}:{server_port}", node)
        self.client_thread = StoppableThread(target=run_client, args=[server_host, server_port+id, socks_port])
        self.server_thread = StoppableThread(target=run_server, args=[server_host, server_port+id])
        self.client_thread.daemon = True
        self.server_thread.daemon = True
        self.server_thread.start()
        log("THREADS", f"Server started on port {server_port}")
        self.client_thread.start()
        log("THREADS", f"Launching new client for exit node {exit.fingerprint}~{exit.name}")

    def stop(self):
        self.client_thread.stop()
        self.server_thread.stop()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--server_host", "-svh", type=str, default="127.0.0.1")
    parser.add_argument("--server_port", "-svp", type=int, default=29999)
    parser.add_argument("--ctrl_port1", "-cp1", type=int, default=-1)
    parser.add_argument("--ctrl_port2", "-cp2", type=int, default=-1)
    parser.add_argument("--socks_port2", "-sp2", type=int, default=-1)
    args = parser.parse_args()
    
    loops: dict[Node, Loop] = {}
    id_counter: int = 0
    while True:
        exit_nodes: list[Node] = control.get_exit_nodes(args.ctrl_port1)
        if set(exit_nodes) != set(loops.keys()):
            # Stop old and unnecessary loops
            for node in loops.keys():
                if node not in exit_nodes:
                    loops[node].stop()
                    loops.pop(node)
            # Start new and necessary loops
            for node in exit_nodes:
                if node not in loops:
                    loops[node] = Loop(id_counter, node, args.server_host, args.server_port, args.ctrl_port2, args.socks_port2)
                    id_counter += 1
        sleep(UPDATE_INTERVAL)
