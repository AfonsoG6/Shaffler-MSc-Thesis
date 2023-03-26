import socket
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", "-p", type=int, default=-1)
    args = parser.parse_args()
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", args.port))
    sock.sendall(b"getinfo circuit-status\n")
    received = sock.recv(1024).decode("ascii")
    print(received.splitlines())
    
    sock.close()