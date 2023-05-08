import yaml
from argparse import ArgumentParser
import re


def enable_pcap(hosts: dict, hostnames: list, max_packet_size: int):
    pattern = re.compile(r"relay\d+exit")
    
    for host in hosts.keys():
        if host not in hostnames and not pattern.match(host):
            continue

        host_config = hosts[host]

        if "options" not in host_config.keys():
            host_config["options"] = {}
        host_config["options"]["pcap_directory"] = "."
        host_config["options"]["pcap_capture_size"] = f"{max_packet_size} B"
        print(f"PCAP enabled for {host}")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-f", "--file", type=str, required=True)
    parser.add_argument("-n", "--hostnames", type=str, required=False)
    parser.add_argument("-s", "--max-packet-size",
                        type=int, required=False, default=128)

    args = parser.parse_args()
    filename: str = args.file
    hostnames: list = args.hostnames.split(",") if args.hostnames else []
    max_packet_size: int = args.max_packet_size

    config = yaml.load(open(filename, "r"), Loader=yaml.FullLoader)
    enable_pcap(config["hosts"], hostnames, max_packet_size)
    print("PCAP traces enabled")

    yaml.dump(config, open(filename, "w"),
              default_flow_style=False, sort_keys=False)
