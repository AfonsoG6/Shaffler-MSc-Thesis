from argparse import ArgumentParser
import pickle
import json
import os
import re

info_clients: dict = {} # {client_name: [{timestamp, circuit_idx, site_idx}]}
info_servers: dict = {} # {port: [{timestamp, port, circuit_idx, site_idx}]}
site_counter: int = 0

def find_clients(hosts_path: str) -> list:
    clients: list = []
    client_pattern = re.compile(r"customclient\d+")
    for element in os.listdir(hosts_path):
        if client_pattern.search(element) and os.path.exists(os.path.join(hosts_path, element, "eth0.pcap")):
            clients.append(element)
    if len(clients) > 0:
        print(f"Clients found: {len(clients)}")
    else:
        raise Exception(f"No client folder found in {hosts_path}")
    return clients


def get_client_flows(hostname: str, hosts_path: str) -> None:
    global info_clients, info_servers, site_counter

    host_path = os.path.join(hosts_path, hostname)
    circuit_idx: int = int(hostname[len("customclient"):])
    port: int = 10000 + circuit_idx

    if hostname not in info_clients.keys():
        info_clients[hostname] = []
    if port not in info_servers.keys():
        info_servers[port] = []
    
    for file in os.listdir(host_path):
        if file.endswith(".tgenrc.graphml"):
            timestamp: int = int(file.split(".")[0].replace("t", ""))
            site_idx: int = site_counter
            site_counter += 1
            info_clients[hostname].append({
                "timestamp": timestamp,
                "duration": 30,
                "circuit_idx": circuit_idx,
                "site_idx": site_idx
            })
            info_servers[port].append({
                "timestamp": timestamp,
                "duration": 30,
                "circuit_idx": circuit_idx,
                "site_idx": site_idx
            })
            print(f"Found flow for {hostname} at {timestamp}")

def main():
    parser = ArgumentParser()
    parser.add_argument("-s", "--simulation", type=str, required=True)
    args = parser.parse_args()

    # Parse arguments
    simulation: str = args.simulation
    
    hosts_path: str = os.path.join(simulation, "shadow.data", "hosts")
    
    if not os.path.exists(simulation):
        raise Exception("Simulation path is not valid")
    if not os.path.exists("stage"):
        os.makedirs("stage")

    clients: list = find_clients(hosts_path)
    for client in clients:
        get_client_flows(client, hosts_path)

    # Sort info_clients by timestamp
    for hostname in info_clients.keys():
        info_clients[hostname].sort(key=lambda x: x["timestamp"])
    
    # Sort info_servers by timestamp
    for port in info_servers.keys():
        info_servers[port].sort(key=lambda x: x["timestamp"])

    with open(os.path.join("stage", f"info_clients.pickle"), "wb") as file:
        pickle.dump(info_clients, file)
    with open(os.path.join("stage", f"info_clients.json"), "w") as file:
        json.dump(info_clients, file, indent=4)
    with open(os.path.join("stage", f"info_servers.pickle"), "wb") as file:
        pickle.dump(info_servers, file)
    with open(os.path.join("stage", f"info_servers.json"), "w") as file:
        json.dump(info_servers, file, indent=4)

if __name__ == "__main__":
    main()
