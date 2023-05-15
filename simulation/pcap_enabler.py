from argparse import ArgumentParser
import yaml
import re


def enable_pcap_clients(hosts: dict, hostnames: list, num_clients: int, max_packet_size: int):
    pattern = re.compile(r".*client.*")

    i: int = 0
    for host in hosts.keys():
        if pattern.match(host) and ((len(hostnames) > 0 and host in hostnames) or len(hostnames) == 0):
            if num_clients > 0 and i >= num_clients:
                break
            i += 1
            
            host_config = hosts[host]

            if "host_options" not in host_config.keys():
                host_config["host_options"] = {}
            host_config["host_options"]["pcap_enabled"] = True
            host_config["host_options"]["pcap_capture_size"] = f"{max_packet_size} B"
            print(f"PCAP enabled for {host}")

            host_config["processes"].append(
                {"path": "hostname", "args": "-I", "start_time": 60})


def enable_pcap_exits(hosts: dict, hostnames: list, max_packet_size: int):
    pattern = re.compile(r"relay\d+exit")

    for host in hosts.keys():
        if pattern.match(host) and ((len(hostnames) > 0 and host in hostnames) or len(hostnames) == 0):
            host_config = hosts[host]

            if "host_options" not in host_config.keys():
                host_config["host_options"] = {}
            host_config["host_options"]["pcap_enabled"] = True
            host_config["host_options"]["pcap_capture_size"] = f"{max_packet_size} B"
            print(f"PCAP enabled for {host}")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-f", "--file", type=str, required=True)
    parser.add_argument("-n", "--hostnames", type=str, required=False)
    parser.add_argument("-c", "--num-clients", type=int, required=False, default=-1)
    parser.add_argument("-s", "--max-packet-size",
                        type=int, required=False, default=21)

    args = parser.parse_args()
    filename: str = args.file
    hostnames: list = args.hostnames.split(",") if args.hostnames else []
    num_clients: int = args.num_clients
    max_packet_size: int = args.max_packet_size

    config = yaml.load(open(filename, "r"), Loader=yaml.FullLoader)
    enable_pcap_clients(config["hosts"], hostnames, num_clients, max_packet_size)
    enable_pcap_exits(config["hosts"], hostnames, max_packet_size)
    print("PCAP traces enabled")

    yaml.dump(config, open(filename, "w"),
              default_flow_style=False, sort_keys=False)
