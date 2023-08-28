import copy
import json
import os
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
        print_prefix(
            "Couldn't find hostname and running Tor here is not possible with shadow, so we're exiting..."
        )
        exit(1)
    print_prefix(f"\tHostname: {hostname}\n")
    return hostname


# Config the OS app
def configOSApp(confs):
    app_config = copy.deepcopy(confs)
    del app_config["bind_address"]

    confs["app_path"] = current_dir + "/traffic_gen/os"
    print_prefix("Configuring OS app")
    with open(current_dir + "/traffic_gen/os/config.json", "w") as config_file:
        config_file.write(json.dumps(app_config))
        config_file.close()
    print_prefix("\t OS app configured\n")
    return


def extractCoverClientConfig(configs):
    cover_client_configs = {
        "log_path": current_dir + "/logs/cclient.log",
        "timeout": configs["cclient"]["timeout"],
        "address": getHostname(current_dir + "/traffic_gen/os/tor/").strip(),
        "endpoint": configs["cclient"]["endpoint"],
        "delta": configs["cclient"]["delta"],
        "deviation": configs["cclient"]["deviation"],
        "threads": configs["cclient"]["threads"],
        "fail_limit": configs["cclient"]["fail_limit"],
    }

    with open(
        current_dir + "/traffic_gen/cover_client/config.json", "w"
    ) as config_file:
        config_file.write(json.dumps(cover_client_configs))
        config_file.close()
    return


def main():
    print_prefix("\n===== STARTING SETUP =====\n")
    configs = readConfFile(config_path)
    os.makedirs(current_dir + "/logs", exist_ok=True)
    configOSApp(configs["app"])
    extractCoverClientConfig(configs)
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
