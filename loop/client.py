import requests
import argparse

def run_client(server_host:str, server_port:int, socks_port:int = -1):
    url = f"https://{server_host}:{server_port}"
    socks5 = f"socks5://localhost:{socks_port}"
    
    with requests.Session() as s:
        s.verify = False # Ignore verification of server certificate
        if socks_port > 0:
            s.proxies = {"http": socks5, "https": socks5}

        for i in range(100):
            response = s.get(url)
            print(response.content)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--server_host", "-h", type=str, default="127.0.0.1")
    parser.add_argument("--server_port", "-p", type=int, default=29999)
    parser.add_argument("--socks_port", "-s", type=int, default=-1)
    args=parser.parse_args()
    run_client(args.server_host, args.server_port, args.socks_port)