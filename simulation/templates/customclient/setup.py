import copy
import json
import os
import re
import subprocess
import time
from argparse import ArgumentParser


def print_prefix(msg):
    print(f"[COVER_SETUP] {msg}")

def readConfFile(config_path):
    print_prefix("Reading config file")
    with open(config_path, "r") as config_file:
        configs = json.load(config_file)
        config_file.close()
    print_prefix("\tRead config file\n")
    return configs


# Generate torrc
def genTorrc(confs):
    logs_dir = current_dir + "/logs/"
    hidden_service_dir = current_dir + "/traffic_gen/os/tor/"
    """
    print_prefix("Generating Torrc")
    with open("tor.os.torrc", "w") as torrc:
        torrc.writelines(
            [
                f'SocksPort {confs["socks_port"]}\n',
                f'ControlPort {confs["control_port"]}\n',
                f"LogMessageDomains 1\n",
                f"SafeLogging 0\n",
                f"TruncateLogFile 1\n",
                f"Log notice stderr\n",
                f'Log debug file {logs_dir+"tor_debug.log"}\n',
                f'Log info file {logs_dir+"tor_info.log"}\n',
                f"NumEntryGuards 1\n",
                # f'Socks5Proxy {confs["socks5_proxy_address"]}:{confs["socks5_proxy_port"]}\n',
                f"HiddenServiceDir {hidden_service_dir}\n",
                f'HiddenServicePort 80 127.0.0.1:{confs["hidden_service_port"]}\n',
            ]
        )
        torrc.close()
    """
    confs["torrc_path"] = current_dir + "/torrc"
    confs["hidden_service_dir"] = hidden_service_dir
    print_prefix("\tTorrc generated\n")
    return


# Generate os.conf for nginx
def genNginxConf(nginx_confs, torrc_confs, app_confs):
    hostname = getHostname(torrc_confs["hidden_service_dir"]).strip()
    nginx_confs["hostname"] = hostname
    print_prefix("Generating Nginx conf file")
    with open("os.conf.template", "r") as template:
        data = template.read()
        data = data.replace("{hidden_service_port}", torrc_confs["hidden_service_port"])
        data = data.replace("{hostname}", hostname)
        data = data.replace("{bind_address}", app_confs["bind_address"])
    with open("os.conf", "w") as out:
        out.write(data)
    print_prefix("\tNginx conf file generated\n")
    copyNginxConf(nginx_confs["alt_config_dir"])
    return


def getHostname(hs_dir):
    print_prefix("Getting hostname")
    path = hs_dir + "hostname"
    # check if hostname already exists
    if os.path.exists(path):
        with open(path, "r") as name_file:
            hostname = name_file.readline().strip()
            name_file.close()
    # run Tor with the new torrc until hostname is created
    else:
        print_prefix("Couldn't find hostname and running Tor here is not possible with shadow, so we're exiting...")
        exit(1)
        print_prefix("Couldn't find hostname, running Tor to generate one:")
        proc = subprocess.Popen("tor -f tor.os.torrc", shell=True)
        while not os.path.exists(path):
            time.sleep(0.5)
        proc.terminate()
        time.sleep(2)
        with open(path, "r") as name_file:
            hostname = name_file.readline()
            name_file.close()
    print_prefix(f"\tHostname: {hostname}\n")
    return hostname


def copyNginxConf(path):
    print_prefix("Copying Nginx conf file")
    clientname = os.path.basename(os.getcwd())
    os.system(f'cp os.conf "{path}/{clientname}.os.conf"')
    print_prefix("\tNginx conf file copied\n")
    return


# Config the OS app
def configOSApp(confs):
    app_config = copy.deepcopy(confs)
    del app_config["gunicorn_exec_path"]
    del app_config["bind_address"]

    confs["app_path"] = current_dir + "/traffic_gen/os"
    print_prefix("Configuring OS app")
    with open(current_dir + "/traffic_gen/os/config.json", "w") as config_file:
        config_file.write(json.dumps(app_config))
        config_file.close()
    print_prefix("\t OS app configured\n")
    return


# Generate user.js (tbb preferences)
def genTbbPrefs(confs, path):
    print_prefix("Generating TBB user prefs")
    path = path.rstrip("/")
    with open("user.js", "w") as prefs:
        prefs.writelines(
            [
                f'user_pref("extensions.torlauncher.control_port", {confs["control_port"]});\n',
                f'user_pref("extensions.torlauncher.start_tor", false);\n',
                f'user_pref("network.proxy.socks_port", {confs["socks_port"]});\n',
            ]
        )
        prefs.close()
    print_prefix("\tTBB user prefs generated\n")
    profile_dir = getDefaultProfileDir(path)
    copyTbbPrefs(path + "/" + profile_dir)
    return


def getDefaultProfileDir(profies_path):
    print_prefix("Getting TBB profile dir")
    with open(profies_path + "/profiles.ini", "r") as profiles:
        content = profiles.readlines()
        profiles.close()

    dir = ""
    for line in content:
        if re.search("Path=", line) != None:
            dir = line.split("=")[1].strip()
        elif re.search("Default=1", line) != None and dir != "":
            break

    print_prefix(f"\tTBB profile dir: {dir}\n")
    return dir + "/"


def copyTbbPrefs(path):
    print_prefix("Copying TBB user prefs to profile dir")
    os.system(f'cp user.js "{path}"')
    print_prefix("\tTBB user prefs copied\n")
    return


def extractCoverClientConfig(configs):
    cover_client_configs = {
        "gecko_path": configs["cclient"]["gecko_path"],
        "log_path": current_dir + "/logs/cclient.log",
        "timeout": configs["cclient"]["timeout"],
        "address": configs["nginx"]["hostname"],
        "endpoint": configs["cclient"]["endpoint"],
        "rate": configs["cclient"]["rate"],
        "fail_limit": configs["cclient"]["fail_limit"],
    }

    with open(
        current_dir + "/traffic_gen/cover_client/config.json", "w"
    ) as config_file:
        config_file.write(json.dumps(cover_client_configs))
        config_file.close()
    return


def extractManagerConfig(confs):
    manager_config = copy.deepcopy(confs["manager"])

    manager_config["logs"]["log_file"] = current_dir + "/logs/manager.log"
    manager_config["launcher"] = {
        "tbb_exec_path": confs["tbb"]["tbb_exec_path"],
        "tor_exec_path": confs["tor"]["tor_exec_path"],
        "torrc_path": confs["tor"]["torrc"]["torrc_path"],
        "cclient": {
            "cclient_exec_path": current_dir + "/traffic_gen/cover_client/client.py",
            "python_exec_path": confs["cclient"]["python_path"],
        },
        "nginx": {
            "exec_path": confs["nginx"]["exec_path"],
            "status_address": "http://127.0.0.1:"
            + confs["tor"]["torrc"]["hidden_service_port"]
            + "/nginx_status",
            "check_period": confs["nginx"]["check_period"],
        },
        "gunicorn": {
            "exec_path": confs["app"]["gunicorn_exec_path"],
            "bind_address": confs["app"]["bind_address"],
            "log_file": current_dir + "/logs/gunicorn.log",
            "app_path": confs["app"]["app_path"],
        },
    }

    with open(current_dir + "/manager/config.json", "w") as config_file:
        config_file.write(json.dumps(manager_config))
        config_file.close()
    return


def main():
    print_prefix("\n===== STARTING SETUP =====\n")
    configs = readConfFile(config_path)
    os.makedirs(current_dir + "/logs", exist_ok=True)
    genTorrc(configs["tor"]["torrc"])
    genNginxConf(configs["nginx"], configs["tor"]["torrc"], configs["app"])
    #genTbbPrefs(configs["tor"]["torrc"], configs["tbb"]["tbb_profiles_dir"])
    configOSApp(configs["app"])
    extractCoverClientConfig(configs)
    #extractManagerConfig(configs)
    print_prefix("===== SETUP FINISHED =====\n")
    return


if __name__ == "__main__":
    parser: ArgumentParser = ArgumentParser()
    parser.add_argument(
        "-d",
        "--dir",
        type=str,
        default=".",
        help="Directory where the setup is being run",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default="config.json",
        help="Path to the config file",
    )
    args = parser.parse_args()
    current_dir: str = args.dir
    current_dir = current_dir.rstrip("/")
    config_path: str = args.config
    main()
