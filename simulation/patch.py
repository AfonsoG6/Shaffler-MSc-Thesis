from argparse import ArgumentParser
import xml.etree.ElementTree as ET
import random
import yaml
import re
import os


def patch_clients(hosts: dict, hostnames: list, num_clients: int, max_packet_size: int):
    pattern = re.compile(r".*client.*")

    i: int = 0
    host_keys = list(hosts.keys())
    random.shuffle(host_keys)
    for host in host_keys:
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


def patch_exits(hosts: dict, hostnames: list, max_packet_size: int):
    pattern = re.compile(r"relay\d+exit")

    for host in hosts.keys():
        if pattern.match(host) and ((len(hostnames) > 0 and host in hostnames) or len(hostnames) == 0):
            host_config = hosts[host]

            if "host_options" not in host_config.keys():
                host_config["host_options"] = {}
            host_config["host_options"]["pcap_enabled"] = True
            host_config["host_options"]["pcap_capture_size"] = f"{max_packet_size} B"
            print(f"PCAP enabled for {host}")

def patch_client_tgenrc(new_port: int, original_path: str, target_path: str = ""):
    if target_path == "":
        target_path = original_path
    with open(original_path, "r") as f:
        tgenrc = f.read()
        tgenrc = tgenrc.replace(":80", f":{new_port}")
    with open(target_path, "w") as f:
        f.write(tgenrc)

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-s", "--simulation", type=str, required=True)
    parser.add_argument("-n", "--hostnames", type=str, required=False)
    parser.add_argument("-c", "--num-clients", type=int,
                        required=False, default=-1)
    parser.add_argument("-p", "--max-packet-size",
                        type=int, required=False, default=24)

    args = parser.parse_args()
    simulation: str = args.simulation
    hostnames: list = args.hostnames.split(",") if args.hostnames else []
    num_clients: int = args.num_clients
    max_packet_size: int = args.max_packet_size
    
    config_path = os.path.join(simulation, "shadow.config.yaml")
    conf_path = os.path.join(simulation, "conf")
    hosts_path = os.path.join(simulation, "shadow.data.template", "hosts")

    tgen_perf_path = os.path.join(conf_path, "tgen-perf-exit.tgenrc.graphml")
    tgen_perf_dir_path = os.path.join(conf_path, "tgen-perf-exit")
    os.makedirs(tgen_perf_dir_path, exist_ok=True)
    
    markov_pattern = re.compile(r"markovclient\d+exit")
    perf_pattern = re.compile(r"perfclient\d+exit")
    ports_needed = set()
    for host in os.listdir(hosts_path):
        if markov_pattern.match(host):
            idx = int(host[len("markovclient"):-len("exit")])
            print(f"Markov client {idx}")
            own_port = 10000 + idx
            ports_needed.add(own_port)
            patch_client_tgenrc(own_port, os.path.join(hosts_path, host, "tgenrc.graphml"))
        if perf_pattern.match(host):
            idx = int(host[len("perfclient"):-len("exit")])
            print(f"Perf client {idx}")
            own_port = 20000 + idx
            ports_needed.add(own_port)
            patch_client_tgenrc(own_port, tgen_perf_path, os.path.join(tgen_perf_dir_path, f"tgen-perf-exit-{own_port}.tgenrc.graphml"))

    tgen_server_path = os.path.join(conf_path, "tgen-server.tgenrc.graphml")
    tgen_server_dir_path = os.path.join(conf_path, "tgen-server")
    os.makedirs(tgen_server_dir_path, exist_ok=True)
    with open(tgen_server_path, "r") as f:
        tgen_server = f.read()
    for port in ports_needed:
        new_tgen_server = tgen_server.replace("<data key=\"d0\">80", f"<data key=\"d0\">{port}")
        with open(os.path.join(tgen_server_dir_path, f"tgen-server-{port}.tgenrc.graphml"), "w") as f:
            f.write(new_tgen_server)

    config = yaml.load(open(config_path, "r"), Loader=yaml.FullLoader)
    
    server_pattern = re.compile(r".*server.*")
    for host in config["hosts"].keys():
        if server_pattern.match(host):
            for port in ports_needed:
                process = config["hosts"][host]["processes"][0].copy()
                process["args"] = process["args"].replace("tgen-server.tgenrc.graphml", f"tgen-server/tgen-server-{port}.tgenrc.graphml")
                config["hosts"][host]["processes"].append(process)
    
    patch_clients(config["hosts"], hostnames, num_clients, max_packet_size)
    patch_exits(config["hosts"], hostnames, max_packet_size)
    
    print("Done!")

    yaml.dump(config, open(config_path, "w"), default_flow_style=False, sort_keys=False)
