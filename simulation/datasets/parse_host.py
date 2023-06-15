from argparse import ArgumentParser
from dpkt.pcap import Reader
from dpkt.ip import inet_to_str
import pickle
import os

info_clients: dict = {} # {client_name: [{timestamp, circuit_idx, site_idx}]}
info_servers: list = [] # [{timestamp, port, circuit_idx, site_idx}]

class IP:
    def __init__(self, packet: bytes) -> None:
        self.src = packet[12:16]
        self.dst = packet[16:20]
        self.len = int.from_bytes(packet[2:4], "big")
        self.src_port = int.from_bytes(packet[20:22], "big")
        self.dst_port = int.from_bytes(packet[22:24], "big")
    
    def __str__(self) -> str:
        return f"Source: {inet_to_str(self.src)}:{self.src_port}\nDestination: {inet_to_str(self.dst)}:{self.dst_port}\nLength: {self.len}"

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
        return ip.src_port
    elif inet_to_str(ip.dst) == own_address:
        return ip.dst_port
    else:
        raise Exception("Packet is not related to the server")

def timestamp_str(timestamp: float) -> str:
    return "{:.6f}".format(timestamp)

def parse_pcap_outflow(info_servers: dict, hostname: str, hosts_path: str, output_path: str) -> None:
    outflow_path: str = os.path.join(output_path, "outflow")
    os.makedirs(outflow_path, exist_ok=True)

    pcap_path: str = os.path.join(hosts_path, hostname, "eth0.pcap")
    print(f"[{hostname} process] Parsing {pcap_path}...")
    
    own_address: str = get_address(os.path.join(hosts_path, hostname))
    completed_idx: dict = {}
    for port in info_servers.keys():
        completed_idx[port] = 0

    with open(pcap_path, "rb") as file:
        reader: Reader = Reader(file)
        for timestamp, packet in reader:
            ip: IP = IP(packet)
            try:
                orientation = get_orientation_server(ip, own_address)
                port = get_port(ip, own_address)
                if port not in info_servers.keys():
                    continue
                info: list = info_servers[port]
            except:
                continue
            for idx in range(completed_idx[port], len(info)):
                if timestamp < info[idx]["timestamp"]:
                    break
                if timestamp > info[idx]["timestamp"] + info[idx]["duration"]:
                    completed_idx[port] += 1
                    continue
                dir_path: str = os.path.join(outflow_path, f"{info[idx]['circuit_idx']}_{info[idx]['site_idx']}")
                os.makedirs(dir_path, exist_ok=True)
                file_path: str = os.path.join(dir_path, hostname)
                with open(file_path, "a") as file:
                    file.write(f"{timestamp_str(timestamp-info[idx]['timestamp'])}\t{ip.len*orientation}\n")
                break


def parse_pcap_inflow(info: list, hostname: str, hosts_path: str, output_path: str) -> None:
    inflow_path: str = os.path.join(output_path, "inflow")
    os.makedirs(inflow_path, exist_ok=True)

    pcap_path: str = os.path.join(hosts_path, hostname, "eth0.pcap")
    own_address: str = get_address(os.path.join(hosts_path, hostname))
    with open(pcap_path, "rb") as file:
        reader: Reader = Reader(file)
        completed_idx: int = 0
        for timestamp, packet in reader:
            ip: IP = IP(packet)
            for idx in range(completed_idx, len(info)):
                if timestamp < info[idx]["timestamp"]:
                    break
                if timestamp > info[idx]["timestamp"] + info[idx]["duration"]:
                    completed_idx += 1
                    continue
                try:
                    orientation = get_orientation_client(ip, own_address)
                except:
                    continue
                file_path: str = os.path.join(inflow_path, f"{info[idx]['circuit_idx']}_{info[idx]['site_idx']}")
                with open(file_path, "a") as file:
                    file.write(f"{timestamp_str(timestamp-info[idx]['timestamp'])}\t{ip.len*orientation}\n")
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
    hosts_path: str = os.path.join(simulation, f"shadow.data", "hosts")
    info_clients_path: str = os.path.join(stage_path, f"info_clients.pickle")
    info_servers_path: str = os.path.join(stage_path, f"info_servers.pickle")

    if not os.path.exists(simulation):
        raise Exception(f"Simulation path is not valid: {os.path.abspath(simulation)}")
    if not os.path.exists(hosts_path):
        raise Exception(f"Hosts path is not valid: {os.path.abspath(hosts_path)}")
    if not os.path.exists(stage_path):
        raise Exception(f"Stage path is not valid: {os.path.abspath(stage_path)}")
    if not os.path.exists(info_clients_path):
        raise Exception(f"Info_Clients path is not valid: {os.path.abspath(info_clients_path)}")
    if not os.path.exists(info_servers_path):
        raise Exception(f"Info_Servers path is not valid: {os.path.abspath(info_servers_path)}")
    os.makedirs(output_path, exist_ok=True)

    with open(info_clients_path, "rb") as file:
        info_clients = pickle.load(file)
    with open(info_servers_path, "rb") as file:
        info_servers = pickle.load(file)

    if hostname in info_clients.keys():
        parse_pcap_inflow(info_clients[hostname], hostname, hosts_path, output_path)
    elif hostname.startswith("server"):
        parse_pcap_outflow(info_servers, hostname, hosts_path, output_path)
    else:
        raise Exception(f"Invalid hostname: {hostname}")

    print(f"[{hostname}] Done parsing pcap file for {hostname}")


if __name__ == "__main__":
    main()
