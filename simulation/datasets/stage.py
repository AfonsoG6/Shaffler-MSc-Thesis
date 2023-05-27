from argparse import ArgumentParser
import pickle
import json
import os
import re

CLOCK_SYNC = -946684800

info_clients: dict = {} # {client_name: [{timestamp, circuit_idx, site_idx}]}
info_servers: dict = {} # {address: [{timestamp, port, circuit_idx, site_idx}]}
circuit_idxs: dict = {}
site_counter: int = 0

def find_clients(hosts_path: str) -> list:
    clients: list = []
    client_pattern = re.compile(r"client")
    for element in os.listdir(hosts_path):
        if client_pattern.search(element) and os.path.exists(os.path.join(hosts_path, element, "eth0.pcap")):
            clients.append(element)
    if len(clients) > 0:
        print(f"Clients found: {len(clients)}")
    else:
        raise Exception(f"No client folder found in {hosts_path}")
    return clients

def circuit_idxs_key(client_name: str, circuit_path: str) -> str:
    return f"{client_name},{circuit_path}"

def parse_oniontrace(hostname: str, batch_id: int, hosts_path: str) -> None:
    global info_clients, info_servers, circuit_idxs, site_counter
    timestamps: dict = {}
    circuit_paths: dict = {}
    awaiting_circuits: list = []
    stream_new_pattern = re.compile(r"STREAM \d+ NEW")
    stream_succeeded_pattern = re.compile(r"STREAM \d+ SUCCEEDED")
    circ_pattern = re.compile(r"CIRC \d+ (BUILT|CLOSED)")

    oniontrace_path: str = os.path.join(hosts_path, hostname, "oniontrace.1002.stdout")
    if not os.path.exists(oniontrace_path):
        raise Exception(f"Oniontrace file not found for {hostname} in {hosts_path}")

    if hostname not in info_clients[batch_id].keys():
        info_clients[batch_id][hostname] = []

    with open(oniontrace_path, "r") as file:
        while True:
            line: str = file.readline()
            if len(line) == 0:
                break
            match = circ_pattern.search(line)
            if match:
                tokens: list = line[match.start():].split(" ")
                circuit_id: int = int(tokens[1])
                if circuit_id not in circuit_paths.keys():
                    circuit_paths[circuit_id] = tokens[3]
                continue
            match = stream_new_pattern.search(line)
            if match:
                tokens: list = line[match.start():].split(" ")
                stream_id: int = int(tokens[1])
                site: str = tokens[4]
                timestamp: float = round(float(line.split(" ")[2]) + CLOCK_SYNC, 6)
                if "$" in site or timestamp >= 3540:
                    continue
                timestamps[stream_id] = timestamp
                continue
            match = stream_succeeded_pattern.search(line)
            if match:
                tokens: list = line[match.start():].split(" ")
                stream_id: int = int(tokens[1])
                circuit_id: int = int(tokens[3])
                site: str = tokens[4]
                if "$" in site or stream_id not in timestamps.keys():
                    continue
                address: str = site.split(":")[0]
                port: int = int(site.split(":")[1])
                site_id: int = site_counter
                site_counter += 1
                requires_update: bool = False
                if circuit_id not in circuit_paths.keys():
                    # Circuit is still unknown
                    circuit_idx: int = circuit_id
                    requires_update = True
                else:
                    cikey: str = circuit_idxs_key(hostname, circuit_paths[circuit_id])
                    if cikey not in circuit_idxs.keys():
                        circuit_idxs[cikey] = len(circuit_idxs.keys())
                    circuit_idx: int = circuit_idxs[cikey]
                info_clients[batch_id][hostname].append({
                    "timestamp": timestamps[stream_id],
                    "circuit_idx": circuit_idx,
                    "site_idx": site_id
                })
                if address not in info_servers[batch_id].keys():
                    info_servers[batch_id][address] = []
                info_servers[batch_id][address].append({
                    "timestamp": timestamps[stream_id],
                    "port": port,
                    "circuit_idx": circuit_idx,
                    "site_idx": site_id
                })
                if requires_update:
                    awaiting_circuits.append(info_clients[batch_id][hostname][-1])
                    awaiting_circuits.append(info_servers[batch_id][address][-1])
                continue
    for info in awaiting_circuits:
        print(f"Updating circuit index for {hostname} at {info['timestamp']}")
        circuit_id: int = info["circuit_idx"]
        if circuit_id not in circuit_paths.keys():
            raise Exception(f"Circuit {circuit_id} not found")
        cikey: str = circuit_idxs_key(hostname, circuit_paths[circuit_id])
        if cikey not in circuit_idxs.keys():
            circuit_idxs[cikey] = len(circuit_idxs.keys())
        info["circuit_idx"] = circuit_idxs[cikey]

def main():
    parser = ArgumentParser()
    parser.add_argument("-s", "--simulation", type=str, required=True)
    args = parser.parse_args()

    # Parse arguments
    simulation: str = args.simulation
    
    hosts_paths: dict = {}
    data_pattern: re.Pattern = re.compile(r"shadow\.data\.\d")
    for element in os.listdir(simulation):
        if data_pattern.search(element):
            batch_id: int = int(element.split(".")[-1])
            hosts_paths[batch_id] = os.path.join(simulation, element, "hosts")
    
    if not os.path.exists(simulation):
        raise Exception("Simulation path is not valid")
    if not os.path.exists("stage"):
        os.makedirs("stage")

    for batch_id in hosts_paths.keys():
        info_clients[batch_id] = {}
        info_servers[batch_id] = {}
        clients: list = find_clients(hosts_paths[batch_id])
        for client in clients:
            parse_oniontrace(client, batch_id, hosts_paths[batch_id])

    for batch_id in info_clients.keys():
        with open(os.path.join("stage", f"info_clients_{batch_id}.pickle"), "wb") as file:
            pickle.dump(info_clients, file)
        with open(os.path.join("stage", f"info_clients_{batch_id}.json"), "w") as file:
            json.dump(info_clients, file, indent=4)
    
    # Sort info_servers by timestamp
    for batch_id in info_servers.keys():
        for address in info_servers[batch_id].keys():
            info_servers[address].sort(key=lambda x: x["timestamp"])

        with open(os.path.join("stage", f"info_servers_{batch_id}.pickle"), "wb") as file:
            pickle.dump(info_servers, file)
        with open(os.path.join("stage", f"info_servers_{batch_id}.json"), "w") as file:
            json.dump(info_servers, file, indent=4)

if __name__ == "__main__":
    main()
