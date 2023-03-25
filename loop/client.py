import requests

def run_client(server_port:int, socks_port:int = -1):
    url = f"https://localhost:{server_port}"
    socks5 = f"socks5://localhost:{socks_port}"
    
    with requests.Session() as s:
        s.verify = False # Ignore verification of server certificate
        if socks_port > 0:
            s.proxies = {"http": socks5, "https": socks5}

        for i in range(100):
            response = s.get(url)
            print(response.content)

if __name__ == '__main__':
    run_client(29999, 9090)