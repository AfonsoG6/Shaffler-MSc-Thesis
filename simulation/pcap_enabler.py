import yaml
from argparse import ArgumentParser


def enable_pcap(hosts: dict, hostnames: list, max_packet_size: int):
    for host in hosts.keys():
        if len(hostnames) > 0 and host not in hostnames:
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
    parser.add_argument("-h", "--hosts", type=str, required=False)
    parser.add_argument("-s", "--max-packet-size",
                        type=int, required=False, default=128)

    args = parser.parse_args()
    filename: str = args.file
    hostnames: list = args.hosts.split(",") if args.hosts else []
    max_packet_size: int = args.max_packet_size

    config = yaml.load(open(filename, "r"), Loader=yaml.FullLoader)
    enable_pcap(config["hosts"], hostnames, max_packet_size)
    print("PCAP traces enabled")

    yaml.dump(config, open(filename, "w"),
              default_flow_style=False, sort_keys=False)
