from argparse import ArgumentParser
from dpkt.pcap import Reader
from dpkt.ip import IP, inet_to_str
import pickle
import os

info_clients: dict = {} # {client_name: [{timestamp, circuit_idx, site_idx}]}
info_servers: dict = {} # {address: [{timestamp, port, circuit_idx, site_idx}]}

def get_address(host_path: str) -> str:
    file_path: str = os.path.join(host_path, "hostname.1000.stdout")
    if not os.path.exists(file_path):
        raise Exception(f"Hostname file not found: {file_path}")
    with open(os.path.join(host_path, "hostname.1000.stdout"), "r") as file:
        return file.read().strip()

def get_orientation_client(ip: IP, own_address: str) -> int:
    if inet_to_str(ip.src) == own_address:
        return 1
    elif inet_to_str(ip.dst) == own_address:
        return -1
    else:
        raise Exception("Packet is not related to the client")

def get_orientation_server(ip: IP, own_address: str) -> int:
    if inet_to_str(ip.src) == own_address:
        return -1
    elif inet_to_str(ip.dst) == own_address:
        return 1
    else:
        raise Exception("Packet is not related to the server")

def get_port(ip: IP, own_address: str) -> int:
    if inet_to_str(ip.src) == own_address:
        return int.from_bytes(ip.data[0:2], "big")
    elif inet_to_str(ip.dst) == own_address:
        return int.from_bytes(ip.data[2:4], "big")
    else:
        raise Exception("Packet is not related to the server")

def timestamp_str(timestamp: float) -> str:
    return "{:.6f}".format(timestamp)

def parse_pcap_outflow(info_server: list, hostname: str, hosts_path: str, output_path: str) -> None:
    outflow_path: str = os.path.join(output_path, "outflow")
    os.makedirs(outflow_path, exist_ok=True)

    pcap_path: str = os.path.join(hosts_path, hostname, "eth0.pcap")
    print(f"[{hostname} process] Parsing {pcap_path}...")
    own_address: str = get_address(os.path.join(hosts_path, hostname))
    with open(pcap_path, "rb") as file:
        reader: Reader = Reader(file)
        completed_idx: int = 0
        for timestamp, packet in reader:
            try:
                ip: IP = IP(packet)
            except:
                print(f"Invalid IP packet: {packet}")
                continue
            for idx in range(completed_idx, len(info_server)):
                if timestamp < info_server[idx]["timestamp"]:
                    break
                if timestamp > info_server[idx]["timestamp"] + 60:
                    completed_idx = max(completed_idx, idx+1)
                    continue
                try:
                    orientation = get_orientation_server(ip, own_address)
                    port = get_port(ip, own_address)
                except:
                    continue
                if (port == 80) or ((port >= 20000 and port <= 20100) and (port != info_server[idx]["port"])):
                    continue
                file_path: str = os.path.join(outflow_path, f"{info_server[idx]['circuit_idx']}_{info_server[idx]['site_idx']}")
                with open(file_path, "a") as file:
                    file.write(f"{timestamp_str(timestamp-info_server[idx]['timestamp'])}\t{ip.len*orientation}\n")
                break


def parse_pcap_inflow(info_client: list, hostname: str, hosts_path: str, output_path: str) -> None:
    inflow_path: str = os.path.join(output_path, "inflow")
    os.makedirs(inflow_path, exist_ok=True)

    pcap_path: str = os.path.join(hosts_path, hostname, "eth0.pcap")
    print(f"[{hostname} process] Parsing {pcap_path}...")
    own_address: str = get_address(os.path.join(hosts_path, hostname))
    with open(pcap_path, "rb") as file:
        reader: Reader = Reader(file)
        completed_idx: int = 0
        for timestamp, packet in reader:
            try:
                ip: IP = IP(packet)
            except:
                print(f"Invalid IP packet: {packet}")
                continue
            for idx in range(completed_idx, len(info_client)):
                if timestamp < info_client[idx]["timestamp"]:
                    break
                if timestamp > info_client[idx]["timestamp"] + 60:
                    completed_idx = max(completed_idx, idx+1)
                    continue
                try:
                    orientation = get_orientation_client(IP(packet), own_address)
                except:
                    continue
                file_path: str = os.path.join(inflow_path, f"{info_client[idx]['circuit_idx']}_{info_client[idx]['site_idx']}")
                with open(file_path, "a") as file:
                    file.write(f"{timestamp_str(timestamp-info_client[idx]['timestamp'])}\t{ip.len*orientation}\n")
                break

def main():
    global streams, site_indexes, hosts_by_address, streams_by_guard, streams_by_destination

    parser = ArgumentParser()
    parser.add_argument("-s", "--simulation", type=str, required=True)
    parser.add_argument("-n", "--hostname", type=str, required=True)
    parser.add_argument("-o", "--output_path", type=str, required=True)
    args = parser.parse_args()

    # Parse arguments
    simulation: str = args.simulation
    hostname: str = args.hostname
    output_path: str = args.output_path
    
    stage_path: str = "stage"
    hosts_path: str = os.path.join(simulation, "shadow.data", "hosts")

    if not os.path.exists(simulation):
        raise Exception(f"Simulation path is not valid: {os.path.abspath(simulation)}")
    if not os.path.exists(stage_path):
        raise Exception(f"Stage path is not valid: {os.path.abspath(stage_path)}")
    os.makedirs(output_path, exist_ok=True)

    # Load data
    print(f"[{hostname}] Loading data...")
    with open(os.path.join(stage_path, "info_clients.pickle"), "rb") as file:
        info_clients = pickle.load(file)
    with open(os.path.join(stage_path, "info_servers.pickle"), "rb") as file:
        info_servers = pickle.load(file)

    if hostname in info_clients.keys():
        parse_pcap_inflow(info_clients[hostname], hostname, hosts_path, output_path)
    elif hostname.startswith("server"):
        parse_pcap_outflow(info_servers[get_address(os.path.join(hosts_path, hostname))], hostname, hosts_path, output_path)
    else:
        raise Exception(f"Invalid hostname: {hostname}")

    print(f"[{hostname}] Done parsing pcap file for {hostname}")


if __name__ == "__main__":
    main()
