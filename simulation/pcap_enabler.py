import yaml
from argparse import ArgumentParser


def enable_pcap(hosts: dict, hostnames: list[str] = []):
    for host in hosts.keys():
        if len(hostnames) > 0 and host not in hostnames:
            continue

        host_config = hosts[host]

        if "options" in host_config.keys():
            host_config["options"]["pcap_directory"] = "."
        else:
            host_config["options"] = {"pcap_directory": "."}


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-f", "--file", type=str, required=True)
    parser.add_argument("-h", "--hosts", type=str, required=False)

    args = parser.parse_args()
    filename: str = args.file
    hostnames: list[str] = args.hosts.split(",") if args.hosts else []

    config = yaml.load(open(filename, "r"), Loader=yaml.FullLoader)
    enable_pcap(config["hosts"], hostnames)
    print("PCAP traces enabled")

    yaml.dump(config, open(filename, "w"),
              default_flow_style=False, sort_keys=False)
