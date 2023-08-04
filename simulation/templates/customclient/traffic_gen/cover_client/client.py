import json
import os
import time
from requests_html import HTMLSession, HTMLResponse
from requests import Response
from fake_useragent import UserAgent


def readConfig():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    with open(current_dir + "/config.json", "r") as confFile:
        configs = json.load(confFile)
        confFile.close()
    return configs


def mainCycle(configs):
    address = "http://" + configs["address"] + configs["endpoint"]
    rate = configs["rate"] / 1000  # convert ms to s
    tolerated_fails = configs["fail_limit"]
    load_timeout = configs["timeout"] / 1000

    headers = {
        "User-Agent": UserAgent().random,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    # socks5 = f"socks5://localhost:9050" # DNS to be resolved client side
    socks5 = f"socks5h://127.0.0.1:9050"  # DNS to be resolved on the proxy side

    fails = 0
    base = time.time() - rate  # ensure first access happens straight away
    while True:
        if time.time() - base >= rate:
            try:
                session: HTMLSession = HTMLSession()
                res: Response = session.get(
                    address,
                    headers=headers,
                    timeout=load_timeout,
                    proxies={"http": socks5, "https": socks5},
                )
                print(f"[COVER] Received response: {res.status_code}")
                if not isinstance(res, HTMLResponse):
                    print("[COVER] Received non-HTML response")
                    continue
                #res.html.render(timeout=load_timeout)
                fails = 0
                base = time.time()
            except:
                fails += 1
                if fails > tolerated_fails:
                    break
                else:
                    continue

    print("[COVER] Exceeded fail limit... Exiting")
    return


if __name__ == "__main__":
    configs = readConfig()
    mainCycle(configs)
