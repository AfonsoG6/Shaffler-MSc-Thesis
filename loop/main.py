from client import run_client
from server import run_server
import control
from threading import Thread
import argparse

def update_torclient(ctrl_port1:int, ctrl_port2:int):
    exit_node = control.get_exit_node(ctrl_port1)
    if exit_node == None:
        print("No exit node found")
        exit(1)
    control.set_exit_nodes(ctrl_port2, [exit_node])

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--server_host", "-svh", type=str, default="127.0.0.1")
    parser.add_argument("--server_port", "-svp", type=int, default=29999)
    parser.add_argument("--ctrl_port1", "-cp1", type=int, default=-1)
    parser.add_argument("--ctrl_port2", "-cp2", type=int, default=-1)
    parser.add_argument("--socks_port2", "-sp2", type=int, default=-1)
    args = parser.parse_args()
    
    update_torclient(args.ctrl_port1, args.ctrl_port2)
    
    server_thread = Thread(target=run_server, args=[args.server_host, args.server_port])
    server_thread.daemon = True
    server_thread.start()
    print(f"Server started on port {args.server_port}")
    
    run_client(args.server_host, args.server_port, args.socks_port2)
    print("Client finished")
    
    print("Server closing")
