from argparse import ArgumentParser
import pickle
import json
import os
import re

CLOCK_SYNC = -946684800

info_clients: dict = {} # {client_name: [{timestamp, circuit_idx, site_idx}]}
info_servers: list = [] # [{timestamp, port, circuit_idx, site_idx}]
circuit_idxs: dict = {}
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


def parse_oniontrace(hostname: str, hosts_path: str, flow_interval: float) -> None:
    global info_clients, info_servers, site_counter

    stream_new_pattern = re.compile(r"STREAM \d+ NEW")
    stream_succeeded_pattern = re.compile(r"STREAM \d+ SUCCEEDED")
    oniontrace_path: str = os.path.join(hosts_path, hostname, "oniontrace.1002.stdout")
    if not os.path.exists(oniontrace_path):
        raise Exception(f"Oniontrace file not found for {hostname} in {hosts_path}")

    if hostname not in info_clients.keys():
        info_clients[hostname] = []
    circuit_idx: int = int(hostname[len("customclient"):])
    
    last_start_ts: float = -100000
    last_end_ts: float = -100000
    
    with open(oniontrace_path, "r") as file:
        while True:
            line: str = file.readline()
            if len(line) == 0:
                break
            match = stream_new_pattern.search(line)
            if match:
                tokens: list = line[match.start():].split(" ")
                site: str = tokens[4]
                port: int = int(site.split(":")[1])
                if "$" in site:
                    continue
                timestamp: float = round(float(line.split(" ")[2]) + CLOCK_SYNC, 6)
                if timestamp < last_start_ts + flow_interval:
                    # Still the same flow
                    continue
                # New flow
                if last_end_ts > last_start_ts:
                    # Update the previous flow's duration
                    duration: float = last_end_ts - last_start_ts
                    if duration < 60:
                        duration = 60
                    info_clients[hostname][-1]["duration"] = duration
                    info_servers[-1]["duration"] = duration
                last_start_ts = timestamp
                site_idx: int = site_counter
                site_counter += 1
                info_clients[hostname].append({
                    "timestamp": timestamp,
                    "duration": flow_interval-0.00001,
                    "circuit_idx": circuit_idx,
                    "site_idx": site_idx
                })
                info_servers.append({
                    "timestamp": timestamp,
                    "duration": flow_interval-0.00001,
                    "port": port,
                    "circuit_idx": circuit_idx,
                    "site_idx": site_idx
                })
                print(f"Found flow for {hostname} at {timestamp}")
            match = stream_succeeded_pattern.search(line)
            if match:
                timestamp: float = round(float(line.split(" ")[2]) + CLOCK_SYNC, 6)
                last_end_ts = timestamp

def main():
    parser = ArgumentParser()
    parser.add_argument("-s", "--simulation", type=str, required=True)
    parser.add_argument("-f", "--flow_interval", type=float, default=150)
    args = parser.parse_args()

    # Parse arguments
    simulation: str = args.simulation
    flow_interval: float = args.flow_interval
    
    hosts_path: str = os.path.join(simulation, "shadow.data", "hosts")
    
    if not os.path.exists(simulation):
        raise Exception("Simulation path is not valid")
    if not os.path.exists("stage"):
        os.makedirs("stage")

    clients: list = find_clients(hosts_path)
    for client in clients:
        parse_oniontrace(client, hosts_path, flow_interval)

    with open(os.path.join("stage", f"info_clients.pickle"), "wb") as file:
        pickle.dump(info_clients, file)
    with open(os.path.join("stage", f"info_clients.json"), "w") as file:
        json.dump(info_clients, file, indent=4)
    
    # Sort info_servers by timestamp
    info_servers.sort(key=lambda x: x["timestamp"])

    with open(os.path.join("stage", f"info_servers.pickle"), "wb") as file:
        pickle.dump(info_servers, file)
    with open(os.path.join("stage", f"info_servers.json"), "w") as file:
        json.dump(info_servers, file, indent=4)

if __name__ == "__main__":
    main()
