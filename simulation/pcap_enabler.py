import yaml
from argparse import ArgumentParser


def enable_pcap(hosts: dict):
    for host in hosts.keys():
        host_config = hosts[host]

        if "options" in host_config.keys():
            host_config["options"]["pcap_directory"] = "."
        else:
            host_config["options"] = {"pcap_directory": "."}

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-f", "--file", type=str, required=True)

    args = parser.parse_args()
    filename: str = args.file
    pcap: bool = args.pcap
    streamtrace: bool = args.streamtrace

    config = yaml.load(open(filename, "r"), Loader=yaml.FullLoader)
    enable_pcap(config["hosts"])
    print("PCAP traces enabled")

    yaml.dump(config, open(filename, "w"),
              default_flow_style=False, sort_keys=False)
