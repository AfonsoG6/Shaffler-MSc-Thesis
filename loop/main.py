from client import run_client
from server import run_server
from multiprocessing import Process
import subprocess

SERVER_PORT = 29999
SOCKS_PORT = 9090
EXIT_FINGERPRINT = "0A9B1B207FD13A6F117F95CAFA358EEE2234F19A"

def run_torclient(socks_port:int, exit_fingerprint:str):
    subprocess.run(f"tor --Address torclientloop --Nickname torclientloop --defaults-torrc torrc-defaults -f torrc --SocksPort 127.0.0.1:{socks_port} --ExitNodes {exit_fingerprint}")

if __name__ == '__main__':
    server_process = Process(target=run_server, args=[SERVER_PORT])
    tor_process = Process(target=run_torclient, args=[SOCKS_PORT, EXIT_FINGERPRINT])
    
    server_process.start()
    tor_process.start()
    
    run_client(SERVER_PORT, SOCKS_PORT)
    
    tor_process.kill()
    server_process.kill()
