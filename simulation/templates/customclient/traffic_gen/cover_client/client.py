import json
import os
import time
from requests_html import HTMLSession, HTMLResponse
from requests import Response
from fake_useragent import UserAgent
from threading import Thread, Condition
from random import random
from datetime import datetime

def log(context: str, message: str) -> None:
    print(f"{datetime.now().strftime('%b %d %H:%M:%S.%f')} [LOG,{context}] {message}", flush=True)

def do_request(
    session: HTMLSession, address: str, headers: dict, timeout: float, socks5: str, thread_id: int, request_id: int
):
    log(f"THREAD#{thread_id}", f"Sending request #{request_id} to {address}")
    res: Response = session.get(
        address,
        headers=headers,
        timeout=timeout,
        proxies={"http": socks5, "https": socks5},
    )
    log(f"THREAD#{thread_id}", f"Received response for request #{request_id}: {res.status_code}")
    """
    if not isinstance(res, HTMLResponse):
        log(f"THREAD#{thread_id}", "Received non-HTML response")
        return
    hres: HTMLResponse = res
    hres.html.render(timeout=timeout)
    """


def run_client(start_delay, configs, thread_id):
    address = "http://" + configs["address"] + configs["endpoint"]
    base_delta = configs["delta"]
    deviation = configs["deviation"]
    tolerated_fails = configs["fail_limit"]
    base_timeout = configs["timeout"]
    # socks5 = f"socks5://127.0.0.1:9050" # DNS to be resolved client side
    socks5 = f"socks5h://127.0.0.1:9050"  # DNS to be resolved on the proxy side
    headers = {
        "User-Agent": UserAgent().random,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

    time.sleep(start_delay)

    fails = 0
    counter = 1
    with HTMLSession() as session:
        while True:
            try:
                t0 = time.time()
                # Delta is base_delta +/- deviation
                target_delta = base_delta + (random() * 2 - 1) * deviation
                # Timeout is minimum of base_timeout and delta
                timeout = base_timeout if base_timeout < target_delta else target_delta
                do_request(session, address, headers, timeout, socks5, thread_id, counter)
                fails = 0
                counter += 1
                delta = time.time() - t0
                remaining = target_delta - delta
                if remaining > 0:
                    log(f"THREAD#{thread_id}", f"Sleeping for {remaining} seconds of a total of {target_delta} seconds")
                    time.sleep(remaining)
            except Exception as e:
                log(f"THREAD#{thread_id}", f"Exception: {e}")
                fails += 1
                if tolerated_fails >= 0 and fails > tolerated_fails:
                    log(f"THREAD#{thread_id}", "Exceeded fail limit... Stopping Client Thread")
                    return


def readConfig():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    with open(current_dir + "/config.json", "r") as confFile:
        configs = json.load(confFile)
        confFile.close()
    return configs


def main(configs):
    delta = configs["delta"]
    num_threads = configs["threads"]
    threads = []
    for i in range(num_threads):
        start_delay = i * delta / num_threads
        client_thread = Thread(target=run_client, args=[start_delay, configs, i+1])
        threads.append(client_thread)
        client_thread.daemon = True
        client_thread.start()
        log("MAIN", f"Launched new client thread with start delay {start_delay}")
    for thread in threads:
        thread.join()
        log("MAIN", "Client thread has been joined")
    log("MAIN", "All client threads have been joined... Exiting")


if __name__ == "__main__":
    configs = readConfig()
    main(configs)
