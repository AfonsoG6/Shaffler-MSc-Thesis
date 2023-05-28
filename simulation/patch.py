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

def create_client(hosts: dict, idx: int, netnodeid: int = -1):
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
                    data = data.replace("{time}", str(random.randint(1, 60)))
                    data = data.replace("{seed}", str(random.randint(100000000, 999999999)), 1)
                    data = data.replace("{seed}", str(random.randint(100000000, 999999999)), 1)
                elif file == "torrc":
                    pick: dict = pick_nodes()
                    print(f"Picked {pick} for {newhostname}")
                    data = data.replace("{entry}", pick["entry"])
                    data = data.replace("{middle}", pick["middle"])
                    data = data.replace("{exit}", pick["exit"])
                g.write(data)
    print(f"Created {newhostname} directory")
    config_path = os.path.join(templates_path, "customclient.yaml")
    new_host = yaml.load(open(config_path, "r"), Loader=yaml.FullLoader)
    if netnodeid == -1:
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

def load_nodes():
    global hosts_path
    nodes: dict = {"entry": [], "middle": [], "exit": []}
    fingerprints_path = os.path.join(hosts_path, "bwauthority", "v3bw")
    with open(fingerprints_path, "r") as f:
        for line in f.readlines():
            if not line.startswith("node_id"):
                continue
            fp: str = line.split("\t")[0].split("=")[1]
            nick: str = line.split("\t")[2].split("=")[1]
            if "guard" in nick:
                nodes["entry"].append(fp)
            if "exit" in nick:
                nodes["exit"].append(fp)
            if "relay" in nick:
                nodes["middle"].append(fp)
    return nodes

def pick_nodes():
    global nodes
    pick: dict = {}
    order: list = ["entry", "middle", "exit"]
    random.shuffle(order)
    for cat in order:
        choice: str = random.choice(nodes[cat])
        while choice in pick.values():
            choice = random.choice(nodes[cat])
        pick[cat] = choice
    return pick

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-s", "--simulation", type=str, required=True)
    parser.add_argument("-c", "--num-clients", type=int, required=False, default=-1)
    parser.add_argument("-d", "--duration", type=float, required=False, default=1)
    #Flag to specify if we want the same netnodeid for all clients
    parser.add_argument("-g", "--global_netnodeid", action="store_true", required=False, default=False)

    args = parser.parse_args()
    simulation: str = args.simulation
    num_clients: int = args.num_clients
    duration: float = args.duration
    global_netnodeid: bool = args.global_netnodeid
    
    
    config_path = os.path.join(simulation, "shadow.config.yaml")
    conf_path = os.path.join(simulation, "conf")
    hosts_path = os.path.join(simulation, "shadow.data.template", "hosts")
    
    tgen_server_path = os.path.join(conf_path, "tgen-server.tgenrc.graphml")
    tgen_server_dir_path = os.path.join(conf_path, "tgen-server")
    os.makedirs(tgen_server_dir_path, exist_ok=True)
    
    nodes: dict = load_nodes()
    config = yaml.load(open(config_path, "r"), Loader=yaml.FullLoader)
    config["general"]["stop_time"] = int(duration * 3600)
    
    netnodeid: int = -1
    if global_netnodeid:
        netnodeid: int = random.randint(0, 2520)
        while not netnodeid_ok(config["hosts"], netnodeid):
            netnodeid = random.randint(0, 2520)

    ports: set = set()
    for idx in range(num_clients):
        create_client(config["hosts"], idx)
        ports.add(10000 + idx)
    patch_servers(config["hosts"], ports)

    for host in config["hosts"].keys():
        for process in config["hosts"][host]["processes"]:
            if host.startswith("customclient"):
                if process["path"].endswith("oniontrace") and process["args"].startswith("Mode=record"):
                    config["hosts"][host]["processes"].remove(process)
            else:
                if process["path"].endswith("oniontrace"):
                    config["hosts"][host]["processes"].remove(process)

    yaml.dump(config, open(config_path, "w"), default_flow_style=False, sort_keys=False)

    print("Done!")