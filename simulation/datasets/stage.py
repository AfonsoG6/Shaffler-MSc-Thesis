from argparse import ArgumentParser
import pickle
import json
import yaml
import sys
import os
import re

CLOCK_SYNC = -946684800

info_clients: dict = {} # {client_name: [{timestamp, circuit_idx, site_idx}]}
info_servers: dict = {} # {address: [{timestamp, port, circuit_idx, site_idx}]}
circuit_idxs: dict = {}
site_idxs: dict = {}

def find_clients(hosts_path: str) -> list:
    clients: list = []
    client_pattern = re.compile(r"client")
    for element in os.listdir(hosts_path):
        if client_pattern.search(element) and os.path.exists(os.path.join(hosts_path, element, "eth0.pcap")):
            clients.append(element)
    if len(clients) > 0:
        print(f"Clients found: {len(clients)}")
    else:
        raise Exception("No client folder found")
    return clients

def circuit_idxs_key(client_name: str, circuit_path: str) -> str:
    return f"{client_name},{circuit_path}"

def parse_oniontrace(hosts_path: str, hostname: str) -> None:
    global info_clients, info_servers, circuit_idxs, site_idxs
    timestamps: dict = {}
    circuit_paths: dict = {}
    stream_new_pattern = re.compile(r"STREAM \d+ NEW")
    stream_succeeded_pattern = re.compile(r"STREAM \d+ SUCCEEDED")
    circ_built_pattern = re.compile(r"CIRC \d+ BUILT")

    oniontrace_path: str = os.path.join(hosts_path, hostname, "oniontrace.1002.stdout")
    if not os.path.exists(oniontrace_path):
        raise Exception("Oniontrace file not found")

    if hostname not in info_clients.keys():
        info_clients[hostname] = []

    with open(oniontrace_path, "r") as file:
        while True:
            line: str = file.readline()
            if len(line) == 0:
                break
            match = circ_built_pattern.search(line)
            if match:
                tokens: list = line[match.start():].split(" ")
                circuit_id: int = int(tokens[1])
                circuit_paths[circuit_id] = tokens[3]
            match = stream_new_pattern.search(line)
            if match:
                tokens: list = line[match.start():].split(" ")
                stream_id: int = int(tokens[1])
                site: str = tokens[4]
                if "$" in site:
                    continue
                timestamps[stream_id] = round(float(line.split(" ")[2]) + CLOCK_SYNC, 6)
                continue
            match = stream_succeeded_pattern.search(line)
            if match:
                tokens: list = line[match.start():].split(" ")
                stream_id: int = int(tokens[1])
                circuit_id: int = int(tokens[3])
                site: str = tokens[4]
                if "$" in site:
                    continue
                address: str = site.split(":")[0]
                port: int = int(site.split(":")[1])
                if site not in site_idxs.keys():
                    site_idxs[site] = len(site_idxs.keys())
                cikey: str = circuit_idxs_key(hostname, circuit_paths[circuit_id])
                if cikey not in circuit_idxs.keys():
                    circuit_idxs[cikey] = len(circuit_idxs.keys())
                circuit_idx: int = circuit_idxs[cikey]
                info_clients[hostname].append({
                    "timestamp": timestamps[stream_id],
                    "circuit_idx": circuit_idx,
                    "site_idx": site_idxs[site]
                })
                if address not in info_servers.keys():
                    info_servers[address] = []
                info_servers[address].append({
                    "timestamp": timestamps[stream_id],
                    "port": port,
                    "circuit_idx": circuit_idx,
                    "site_idx": site_idxs[site]
                })
                continue

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
        parse_oniontrace(hosts_path, client)

    with open(os.path.join("stage", "info_clients.pickle"), "wb") as file:
        pickle.dump(info_clients, file)
    with open(os.path.join("stage", "info_clients.json"), "w") as file:
        json.dump(info_clients, file, indent=4)
    
    # Sort info_servers by timestamp
    for address in info_servers.keys():
        info_servers[address].sort(key=lambda x: x["timestamp"])

    with open(os.path.join("stage", "info_servers.pickle"), "wb") as file:
        pickle.dump(info_servers, file)
    with open(os.path.join("stage", "info_servers.json"), "w") as file:
        json.dump(info_servers, file, indent=4)

if __name__ == "__main__":
    main()
