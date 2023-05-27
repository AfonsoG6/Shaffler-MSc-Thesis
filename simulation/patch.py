from argparse import ArgumentParser
import xml.etree.ElementTree as ET
import random
import yaml
import re
import os

def patch_servers(hosts: dict, ports: set):
    pattern = re.compile(r"server\d+exit")
    for host in hosts.keys():
        if pattern.match(host):
            host_config = hosts[host]
            if "host_options" not in host_config.keys():
                host_config["host_options"] = {}
            host_config["host_options"]["pcap_enabled"] = True
            host_config["host_options"]["pcap_capture_size"] = f"24 B"
            print(f"PCAP enabled for {host}")
            
            host_config["processes"].append(
                {"path": "hostname", "args": "-I", "start_time": 60})
            print(f"Added hostname process to {host}")
            
            for port in ports:
                process = host_config["processes"][0].copy()
                process["args"] = process["args"].replace("tgen-server.tgenrc.graphml", f"tgen-server/{port}.tgenrc.graphml")
                host_config["processes"].append(process)
            print("Added duplicate tgen processes to server")

def netnodeid_ok(hosts: dict, netnodeid: int):
    for host in hosts.keys():
        if hosts[host]["network_node_id"] == netnodeid:
            return False
    return True

def create_client(hosts: dict, idx: int):
    global hosts_path, tgen_server_path, tgen_server_dir_path
    
    newhostname: str = f"customclient{idx}"
    port: int = 10000 + idx
    # Copy customclient directory to hosts_path
    templates_path = "templates"
    dir_path = os.path.join(templates_path, "customclient")
    client_path = os.path.join(hosts_path, newhostname)
    os.makedirs(client_path, exist_ok=True)
    for file in os.listdir(dir_path):
        with open(os.path.join(dir_path, file), "r") as f:
            with open(os.path.join(client_path, file), "w") as g:
                data = f.read()
                if file == "tgenrc.graphml":
                    data = data.replace("{port}", str(port))
                g.write(data)
    print(f"Created {newhostname} directory")
    config_path = os.path.join(templates_path, "customclient.yaml")
    new_host = yaml.load(open(config_path, "r"), Loader=yaml.FullLoader)
    netnodeid: int = random.randint(0, 2520)
    while not netnodeid_ok(hosts, netnodeid):
        netnodeid = random.randint(0, 2520)
    new_host["network_node_id"] = netnodeid
    hosts[newhostname] = new_host
    print(f"Added {newhostname} to shadow.config.yaml")
    patch_server_tgenrc(port, tgen_server_path, os.path.join(tgen_server_dir_path, f"{port}.tgenrc.graphml"))
    print(f"Created duplicate tgenrc for {newhostname} with port {port}")

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
    parser.add_argument("-c", "--num-clients", type=int, required=False, default=-1)
    parser.add_argument("-d", "--duration", type=float, required=False, default=1)

    args = parser.parse_args()
    simulation: str = args.simulation
    num_clients: int = args.num_clients
    duration: float = args.duration
    
    config_path = os.path.join(simulation, "shadow.config.yaml")
    conf_path = os.path.join(simulation, "conf")
    hosts_path = os.path.join(simulation, "shadow.data.template", "hosts")
    
    tgen_server_path = os.path.join(conf_path, "tgen-server.tgenrc.graphml")
    tgen_server_dir_path = os.path.join(conf_path, "tgen-server")
    os.makedirs(tgen_server_dir_path, exist_ok=True)

    config = yaml.load(open(config_path, "r"), Loader=yaml.FullLoader)
    config["general"]["stop_time"] = int(duration * 3600)
    ports: set = set()
    for idx in range(num_clients):
        create_client(config["hosts"], idx)
        ports.add(10000 + idx)
    patch_servers(config["hosts"], ports)
    
    yaml.dump(config, open(config_path, "w"), default_flow_style=False, sort_keys=False)

    print("Done!")