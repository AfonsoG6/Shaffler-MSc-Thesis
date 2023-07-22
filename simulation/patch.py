from argparse import ArgumentParser
from math import ceil
from copy import deepcopy
import random
import shutil
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

def get_servers_string(hosts: dict, port: int):
    pattern = re.compile(r"server\d+exit")
    
    servers: list = []
    for host in hosts.keys():
        if pattern.match(host):
            servers.append(f"{host}:{port}")
    return ",".join(servers)

def create_client(hosts: dict, idx: int, netnodeid: int = -1):
    global hosts_path, tgen_server_path, tgen_server_dir_path, duration
    
    newhostname: str = f"customclient{idx}"
    port: int = 10000 + idx
    # Copy customclient directory to hosts_path
    templates_path = "templates"
    dir_path = os.path.join(templates_path, "customclient")
    client_path = os.path.join(hosts_path, newhostname)
    os.makedirs(client_path, exist_ok=True)
    for elem in os.listdir(dir_path):
        if elem == "torrc":
            with open(os.path.join(dir_path, elem), "r") as f:
                data = f.read()
            pick: dict = pick_nodes()
            print(f"Picked {pick} for {newhostname}")
            data = data.replace("{entry}", pick["entry"])
            data = data.replace("{middle}", pick["middle"])
            data = data.replace("{exit}", pick["exit"])
            with open(os.path.join(client_path, elem), "w") as g:
                g.write(data)
        else:
            if os.path.isfile(os.path.join(dir_path, elem)):
                shutil.copy(os.path.join(dir_path, elem), os.path.join(client_path, elem))
            else:
                shutil.copytree(os.path.join(dir_path, elem), os.path.join(client_path, elem))
    print(f"Created {newhostname} directory")
    config_path = os.path.join(templates_path, "customclient.yaml")
    new_host = yaml.load(open(config_path, "r"), Loader=yaml.FullLoader)
    if netnodeid == -1:
        netnodeid: int = random.randint(0, 2520)
        while not netnodeid_ok(hosts, netnodeid):
            netnodeid = random.randint(0, 2520)
    new_host["network_node_id"] = netnodeid
    tgen_proc_template = new_host["processes"][3]
    new_host["processes"] = new_host["processes"][:3]
    for flow_start in range(300 + random.randint(0, 90), duration, 90):
        if flow_start + 60 >= duration:
            break
        with open(os.path.join(templates_path, "tgenrc.graphml"), "r") as f:
            data = f.read()
            data = data.replace("{servers}", get_servers_string(hosts, port))
            data = data.replace("{seed}", str(random.randint(100000000, 999999999)), 1)
            data = data.replace("{seed}", str(random.randint(100000000, 999999999)), 1)
            with open(os.path.join(client_path, f"t{flow_start}.tgenrc.graphml"), "w") as g:
                g.write(data)
        tgen_proc = deepcopy(tgen_proc_template)
        tgen_proc["args"] = f"t{flow_start}.tgenrc.graphml"
        tgen_proc["start_time"] = flow_start
        tgen_proc["shutdown_time"] = flow_start + 60
        new_host["processes"].append(tgen_proc)
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

def rm_minimal(hosts_cfg: dict, hosts_path: str):
    hosts_to_rm: list = []
    for host in hosts_cfg.keys():
        if host.startswith("markov") or host.startswith("perf"):
            hosts_to_rm.append(host)
        else:
            for process in hosts_cfg[host]["processes"]:
                if host.startswith("custom"):
                    if process["path"].endswith("oniontrace") and process["args"].startswith("Mode=record"):
                        hosts_cfg[host]["processes"].remove(process)
                else:
                    if process["path"].endswith("oniontrace"):
                        hosts_cfg[host]["processes"].remove(process)
    for host in hosts_to_rm:
        hosts_cfg.pop(host)
        shutil.rmtree(os.path.join(hosts_path, host), ignore_errors=True)

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-s", "--simulation", type=str, required=True)
    parser.add_argument("-c", "--num-clients", type=int, required=False, default=-1)
    parser.add_argument("-d", "--duration", type=float, required=False, default=1)
    #Flag to specify if we want the same netnodeid for all clients
    parser.add_argument("-g", "--global_netnodeid", action="store_true", required=False, default=False)
    #Flag to specify if minimal or not
    parser.add_argument("-m", "--minimal", action="store_true", required=False, default=False)

    args = parser.parse_args()
    simulation: str = args.simulation
    num_clients: int = args.num_clients
    duration: int = ceil(args.duration * 3600)
    global_netnodeid: bool = args.global_netnodeid
    minimal: bool = args.minimal
    
    
    config_path = os.path.join(simulation, "shadow.config.yaml")
    conf_path = os.path.join(simulation, "conf")
    hosts_path = os.path.join(simulation, "shadow.data.template", "hosts")
    
    tgen_server_path = os.path.join(conf_path, "tgen-server.tgenrc.graphml")
    tgen_server_dir_path = os.path.join(conf_path, "tgen-server")
    os.makedirs(tgen_server_dir_path, exist_ok=True)
    
    nodes: dict = load_nodes()
    config = yaml.load(open(config_path, "r"), Loader=yaml.FullLoader)
    config["general"]["stop_time"] = int(duration)
    
    netnodeid: int = -1
    if global_netnodeid:
        netnodeid: int = random.randint(0, 2520)
        while not netnodeid_ok(config["hosts"], netnodeid):
            netnodeid = random.randint(0, 2520)

    ports: set = set()
    for idx in range(num_clients):
        create_client(config["hosts"], idx, netnodeid)
        ports.add(10000 + idx)
    patch_servers(config["hosts"], ports)

    if minimal:
        rm_minimal(config["hosts"], hosts_path)

    yaml.dump(config, open(config_path, "w"), default_flow_style=False, sort_keys=False)
    
    tconf_path = os.path.join("templates", "conf")
    for elem in os.listdir(tconf_path):
        if os.path.isfile(os.path.join(tconf_path, elem)):
            shutil.copy(os.path.join(tconf_path, elem), os.path.join(conf_path, elem))
        else:
            shutil.copytree(os.path.join(tconf_path, elem), os.path.join(conf_path, elem))

    print("Done!")
