from argparse import ArgumentParser
from dpkt.pcap import Reader
from dpkt.ip import IP, inet_to_str
import pickle
import os

def quick_find_ip(client_path: str) -> str:
    for file in os.listdir(client_path):
        if file == "hostname.1000.stdout":
            with open(os.path.join(client_path, file), "r") as file:
                return file.read().strip()
    raise Exception("IP not found")

def slow_find_ip(pcap_path: str) -> str:
    ip_occurrences: dict = {}
    i: int = 0
    with open(pcap_path, "rb") as file:
        reader: Reader = Reader(file)
        for timestamp, packet in reader:
            try:
                ip: IP = IP(packet)
            except:
                print(f"Invalid IP packet: {packet}")
                continue
            if not ip.src in ip_occurrences.keys():
                ip_occurrences[ip.src] = 0
            if not ip.dst in ip_occurrences.keys():
                ip_occurrences[ip.dst] = 0
            ip_occurrences[ip.src] += 1
            ip_occurrences[ip.dst] += 1
            if i > 1000:
                break
            else:
                i += 1
    ip: str = ""
    for address in ip_occurrences.keys():
        if ip_occurrences[address] >= 1000:
            if ip == "":
                ip = address
            else:
                raise Exception("Multiple IPs found")
    ip = inet_to_str(ip)
    print(f"Found IP: {ip}")
    return ip


def process_packet_outflow(timestamp: float, packet: bytes, own_address: str, outflow_path: str):
    global streams_by_destination, streams, site_indexes
    try:
        ip: IP = IP(packet)
    except:
        return

    peer_address: str
    orientation: int
    if inet_to_str(ip.src) == own_address:
        peer_address = inet_to_str(ip.dst)
        orientation = 1
    elif inet_to_str(ip.dst) == own_address:
        peer_address = inet_to_str(ip.src)
        orientation = -1
    else:
        return
    if peer_address not in streams_by_destination.keys():
        return
    for stream_id in streams_by_destination[peer_address]:
        stream: dict = streams[stream_id]
        identifier: str = f"{stream['circuit_id']}-{site_indexes[stream['destination_ip']]}"
        if stream["start_time"] <= timestamp and stream["end_time"] + 1 >= timestamp:
            with open(os.path.join(outflow_path, identifier), "a") as file:
                file.write(f"{timestamp}\t{ip.len*orientation}\n")


def parse_pcap_outflow(pcap_path: str, output_path: str) -> None:
    outflow_path: str = os.path.join(output_path, "outflow")
    if not os.path.exists(outflow_path):
        os.makedirs(outflow_path)
    outflow_path = os.path.join(outflow_path, os.path.split(os.path.split(pcap_path)[0])[1])
    if not os.path.exists(outflow_path):
        os.makedirs(outflow_path)

    print(f"Parsing {pcap_path}...")
    own_address: str = slow_find_ip(pcap_path)
    with open(pcap_path, "rb") as file:
        reader: Reader = Reader(file)
        for timestamp, packet in reader:
            process_packet_outflow(
                timestamp, packet, own_address, outflow_path)


def process_packet_inflow(timestamp: float, packet: bytes, own_address: str, inflow_path: str):
    global streams_by_destination, streams, site_indexes, streams_by_guard, hosts_by_address
    try:
        ip: IP = IP(packet)
    except:
        return

    peer_address: str
    orientation: int
    if inet_to_str(ip.src) == own_address:
        peer_address = inet_to_str(ip.dst)
        orientation = 1
    elif inet_to_str(ip.dst) == own_address:
        peer_address = inet_to_str(ip.src)
        orientation = -1
    else:
        return
    if peer_address not in hosts_by_address.keys():
        return
    relay_name: str = hosts_by_address[peer_address]
    if relay_name not in streams_by_guard:
        return
    for stream_id in streams_by_guard[relay_name]:
        stream: dict = streams[stream_id]
        identifier: str = f"{stream['circuit_id']}-{site_indexes[stream['destination_ip']]}"
        if stream["start_time"] <= timestamp and stream["end_time"] + 1 >= timestamp:
            with open(os.path.join(inflow_path, identifier), "a") as file:
                file.write(f"{timestamp}\t{ip.len*orientation}\n")


def parse_pcap_inflow(pcap_path: str, output_path: str) -> None:
    inflow_path: str = os.path.join(output_path, "inflow")
    if not os.path.exists(inflow_path):
        os.makedirs(inflow_path)
    inflow_path = os.path.join(inflow_path, os.path.split(os.path.split(pcap_path)[0])[1])
    if not os.path.exists(inflow_path):
        os.makedirs(inflow_path)

    print(f"Parsing {pcap_path}...")
    own_address: str = quick_find_ip(os.path.split(pcap_path)[0])
    with open(pcap_path, "rb") as file:
        reader: Reader = Reader(file)
        for timestamp, packet in reader:
            process_packet_inflow(
                timestamp, packet, own_address, inflow_path)


streams: dict
site_indexes: dict
hosts_by_address: dict
streams_by_guard: dict
streams_by_destination: dict


def main():
    global streams, site_indexes, hosts_by_address, streams_by_guard, streams_by_destination

    parser = ArgumentParser()
    parser.add_argument("-d", "--data_path", type=str, required=True)
    parser.add_argument("-s", "--stage_path", type=str,
                        required=False, default="stage")
    parser.add_argument("-o", "--output_path", type=str,
                        required=False, default="temp")
    parser.add_argument("-p", "--pcap_path", type=str, required=True)
    parser.add_argument("-t", "--type", type=str,
                        required=True, choices=["inflow", "outflow"])
    args = parser.parse_args()

    # Parse arguments
    data_path: str = args.data_path
    stage_path: str = args.stage_path
    output_path: str = args.output_path
    pcap_path: str = args.pcap_path
    type: str = args.type

    if not os.path.exists(data_path):
        raise Exception("Data path is not valid")
    if not os.path.exists(stage_path):
        raise Exception("Stage path is not valid")
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    # Load data
    print("Loading data...")
    with open(os.path.join(stage_path, "streams.pickle"), "rb") as file:
        streams = pickle.load(file)
    with open(os.path.join(stage_path, "site_indexes.pickle"), "rb") as file:
        site_indexes = pickle.load(file)
    with open(os.path.join(stage_path, "hosts_by_address.pickle"), "rb") as file:
        hosts_by_address = pickle.load(file)
    with open(os.path.join(stage_path, "streams_by_guard.pickle"), "rb") as file:
        streams_by_guard = pickle.load(file)
    with open(os.path.join(stage_path, "streams_by_destination.pickle"), "rb") as file:
        streams_by_destination = pickle.load(file)

    if type == "inflow":
        parse_pcap_inflow(pcap_path, output_path)
    else:
        parse_pcap_outflow(pcap_path, output_path)
    
    print(f"Done parsing pcap file {pcap_path}")


if __name__ == "__main__":
    main()
