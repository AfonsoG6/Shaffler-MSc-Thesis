import json
import os
import time
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service

def readConfig():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    with open(current_dir+'/config.json','r') as confFile:
        configs = json.load(confFile)
        confFile.close()

    return configs

def createDriver(configs):
    print(configs)
    gecko_path = configs["gecko_path"]
    load_timeout = configs["timeout"]/1000
    log_file = configs["log_path"]

    service = Service(gecko_path, log_path=log_file)

    options = FirefoxOptions()
    # Run headless
    options.add_argument('--headless')
    # Cache stuff
    options.set_preference('browser.cache.disk.enable', False)
    options.set_preference('browser.cache.memory.enable', False)
    options.set_preference('browser.cache.offline.enable', False)
    options.set_preference('network.http.use-cache', False)
    # Cookie stuff
    options.set_preference('network.cookie.cookieBehavior', 2) # Needed? Probably not...
    # Proxy stuff
    options.set_preference('network.proxy.type', 1)
    options.set_preference('network.proxy.socks_version', 5)
    options.set_preference('network.proxy.socks', '127.0.0.1')
    options.set_preference('network.proxy.socks_port', 9050) # Subject to changes
    options.set_preference('network.proxy.socks_remote_dns', True) # Important for accessing OSes

    driver = webdriver.Firefox(service=service, options=options)
    driver.set_page_load_timeout(load_timeout)

    return driver

def mainCycle(driver, configs):
    address = "http://"+configs["address"]+configs["endpoint"]
    rate = configs["rate"]/1000 # convert ms to s
    tolerated_fails = configs["fail_limit"]

    fails = 0
    base = time.time() - rate # ensure first access happens straight away
    while True:
        if time.time() - base >= rate:
            try:
                driver.get(address)
                fails = 0
                base = time.time()
            except:
                fails += 1
                if fails > tolerated_fails: 
                    break
                else:
                    continue

    print("[COVER] Exceeded fail limit... Exiting")
    driver.quit()
    return

if __name__ == "__main__":
    configs = readConfig()
    driver = createDriver(configs)
    mainCycle(driver,configs)