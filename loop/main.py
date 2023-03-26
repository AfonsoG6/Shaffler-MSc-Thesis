from client import run_client
from server import run_server
from threading import Thread
import argparse

SERVER_PORT = 29999
SOCKS_PORT = 9090

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--server_host", "-svh", type=str, default="127.0.0.1")
    parser.add_argument("--server_port", "-svp", type=int, default=29999)
    parser.add_argument("--socks_port", "-sp", type=int, default=-1)
    args = parser.parse_args()
    
    server_thread = Thread(target=run_server, args=[args.server_host, args.server_port])
    server_thread.daemon = True
    server_thread.start()
    print(f"Server started on port {args.server_port}")
    run_client(args.server_host, args.server_port, args.socks_port)
    print("Client finished")
    print("Server closing")
