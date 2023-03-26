from client import run_client
from server import run_server
from threading import Thread

SERVER_PORT = 29999
SOCKS_PORT = 9090

if __name__ == '__main__':
    server_thread = Thread(target=run_server, args=[SERVER_PORT])
    server_thread.daemon = True
    server_thread.start()
    print("Server started")
    run_client(SERVER_PORT, SOCKS_PORT)
    print("Client finished")
    print("Server closing")
