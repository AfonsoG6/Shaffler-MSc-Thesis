from argparse import ArgumentParser
import xml.etree.ElementTree as ET
import random
import yaml
import re
import os


def patch_clients(hosts: dict, hostnames: list, num_clients: int, max_packet_size: int) -> set:
    pattern = re.compile(r"markovclient\d+exit")
    ports = set()
    
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
            print(f"Added hostname process to {host}")
            
            idx = int(host[len("markovclient"):-len("exit")])
            print(f"Markov client {idx}")
            port = 10000 + idx
            ports.add(port)
            
            patch_client_tgenrc(port, os.path.join(hosts_path, host, "tgenrc.graphml"))
            print(f"Replaced tgenrc for {host}")
            patch_server_tgenrc(port, tgen_server_path, os.path.join(tgen_server_dir_path, f"{port}.tgenrc.graphml"))
            print(f"Created duplicate tgenrc for {host} with port {port}")
    return ports


def patch_servers(hosts: dict, hostnames: list, max_packet_size: int, ports: set):
    pattern = re.compile(r"server\d+exit")
    for host in hosts.keys():
        if pattern.match(host) and ((len(hostnames) > 0 and host in hostnames) or len(hostnames) == 0):
            host_config = hosts[host]
            if "host_options" not in host_config.keys():
                host_config["host_options"] = {}
            host_config["host_options"]["pcap_enabled"] = True
            host_config["host_options"]["pcap_capture_size"] = f"{max_packet_size} B"
            print(f"PCAP enabled for {host}")
            
            host_config["processes"].append(
                {"path": "hostname", "args": "-I", "start_time": 60})
            print(f"Added hostname process to {host}")
            
            for port in ports:
                process = host_config["processes"][0].copy()
                process["args"] = process["args"].replace("tgen-server.tgenrc.graphml", f"tgen-server/{port}.tgenrc.graphml")
                host_config["processes"].append(process)
            print("Added duplicate tgen processes to server")

def patch_client_tgenrc(new_port: int, original_path: str, target_path: str = ""):
    if target_path == "":
        target_path = original_path
    with open(original_path, "r") as f:
        tgenrc = f.read()
    tgenrc = tgenrc.replace(":80", f":{new_port}")
    with open(target_path, "w") as f:
        f.write(tgenrc)

def patch_server_tgenrc(new_port: int, original_path: str, target_path: str = ""):
    if target_path == "":
        target_path = original_path
    with open(original_path, "r") as f:
        tgenrc = f.read()
        
    newtgenrc = tgenrc.replace("<data key=\"d0\">80", f"<data key=\"d0\">{new_port}")
    with open(target_path, "w") as f:
        f.write(newtgenrc)

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-s", "--simulation", type=str, required=True)
    parser.add_argument("-n", "--hostnames", type=str, required=False)
    parser.add_argument("-c", "--num-clients", type=int, required=False, default=-1)
    parser.add_argument("-p", "--max-packet-size", type=int, required=False, default=24)
    parser.add_argument("-d", "--duration", type=float, required=False, default=1)

    args = parser.parse_args()
    simulation: str = args.simulation
    hostnames: list = args.hostnames.split(",") if args.hostnames else []
    num_clients: int = args.num_clients
    max_packet_size: int = args.max_packet_size
    duration: int = args.duration
    
    config_path = os.path.join(simulation, "shadow.config.yaml")
    conf_path = os.path.join(simulation, "conf")
    hosts_path = os.path.join(simulation, "shadow.data.template", "hosts")
    
    tgen_server_path = os.path.join(conf_path, "tgen-server.tgenrc.graphml")
    tgen_server_dir_path = os.path.join(conf_path, "tgen-server")
    os.makedirs(tgen_server_dir_path, exist_ok=True)

    config = yaml.load(open(config_path, "r"), Loader=yaml.FullLoader)
    config["general"]["stop_time"] = int(duration * 3600)
    ports = patch_clients(config["hosts"], hostnames, num_clients, max_packet_size)
    patch_servers(config["hosts"], hostnames, max_packet_size, ports)
    
    yaml.dump(config, open(config_path, "w"), default_flow_style=False, sort_keys=False)

    print("Done!")