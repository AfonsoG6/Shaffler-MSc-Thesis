from argparse import ArgumentParser
from dpkt.pcap import Reader
from dpkt.ip import IP, inet_to_str
import json
import yaml
import os
import re


def find_client_path(data_path: str) -> str:
    client_path: str = ""
    client_pattern = re.compile(r"client")
    for element in os.listdir(data_path):
        if client_pattern.search(element):
            client_path = os.path.join(data_path, element)
            break
    if client_path:
        print(f"Client found: {client_path}")
    else:
        raise Exception("No client folder found")
    return client_path


def get_oniontrace_path(client_path: str) -> str:
    oniontrace_path: str = ""
    oniontrace_pattern = re.compile(r".*\.oniontrace\.1001\.stdout")
    for element in os.listdir(client_path):
        if oniontrace_pattern.search(element):
            oniontrace_path = os.path.join(client_path, element)
            break
    if oniontrace_path:
        print(f"Oniontrace found: {oniontrace_path}")
    else:
        raise Exception("No oniontrace file found")
    return oniontrace_path


def find_pcap_path(host_path: str) -> str:
    pcap_path: str = ""
    pcap_pattern = re.compile(r".*-(?!127\.0\.0\.1).*\.pcap")
    for element in os.listdir(host_path):
        if pcap_pattern.search(element):
            pcap_path = os.path.join(host_path, element)
            break
    if pcap_path:
        print(f"PCAP found: {pcap_path}")
    else:
        raise Exception("No pcap file found")
    return pcap_path


def find_exit_pcap_paths(data_path: str) -> list:
    pcap_paths: list = []
    exit_pattern = re.compile(r"relay\d+exit")
    for element in os.listdir(data_path):
        if exit_pattern.search(element):
            pcap_paths.append(find_pcap_path(os.path.join(data_path, element)))
    if len(pcap_paths) > 0:
        print(f"PCAPs found: {pcap_paths}")
    else:
        raise Exception("No pcap files found")
    return pcap_paths


def parse_oniontrace(oniontrace_path: str, output_path: str) -> dict:
    circuits: dict = {}
    circuit_built_pattern = re.compile(r"CIRC \d+ BUILT")
    streams: dict = {}
    stream_succeeded_pattern = re.compile(r"STREAM \d+ SUCCEEDED")
    stream_closed_pattern = re.compile(r"STREAM \d+ CLOSED")

    with open(oniontrace_path, "r") as file:
        while True:
            line: str = file.readline()
            if len(line) == 0:
                break
            search = circuit_built_pattern.search(line)
            if search:
                idx: int = search.start()
                tokens: list = line[idx:].split(" ")
                circuit_id: int = int(tokens[1])
                guard_name: str = tokens[3].split(",")[0].split("~")[1]
                exit_name: str = tokens[3].split(",")[-1].split("~")[1]
                circuits[circuit_id] = {
                    "guard_name": guard_name, "exit_name": exit_name}
                continue
            search = stream_succeeded_pattern.search(line)
            if search:
                start_time: float = round(
                    float(line.split(" ")[2]) - 946684800, 6) - 0.000001
                idx: int = search.start()
                tokens: list = line[idx:].split(" ")
                stream_id: int = int(tokens[1])
                circuit_id: int = int(tokens[3])
                destination_ip: str = tokens[4]
                streams[stream_id] = {
                    "circuit_id": circuit_id, "destination_ip": destination_ip, "start_time": start_time
                }
                continue
            search = stream_closed_pattern.search(line)
            if search:
                end_time: float = round(
                    float(line.split(" ")[2]) - 946684800, 6) + 0.000001
                idx: int = search.start()
                tokens: list = line[idx:].split(" ")
                stream_id: int = int(tokens[1])
                streams[stream_id]["end_time"] = end_time
                continue
    for stream_id in streams.keys():
        stream: dict = streams[stream_id]
        circuit_id: int = stream["circuit_id"]
        streams[stream_id]["guard_name"] = circuits[circuit_id]["guard_name"]
        streams[stream_id]["exit_name"] = circuits[circuit_id]["exit_name"]
    with open(os.path.join(output_path, "circuits.json"), "w") as file:
        json.dump(circuits, file, indent=4)
    with open(os.path.join(output_path, "streams.json"), "w") as file:
        json.dump(streams, file, indent=4)
    return streams


def find_ip(pcap_path: str) -> str:
    pattern = re.compile(r"-\d+\.\d+\.\d+\.\d+\.pcap")
    match = pattern.search(pcap_path)
    if match:
        address: str = match.group(0)[1:-5]
        print(f"IP found: {address}")
        return address
    else:
        raise Exception("No IP found")


def parse_pcap_inflow(pcap_path: str, streams: dict, streams_by_guard: dict, hosts_by_address: dict, site_indexes: dict, output_path: str) -> None:
    if not os.path.exists(os.path.join(output_path, "inflow")):
        os.makedirs(os.path.join(output_path, "inflow"))

    own_address: str = find_ip(pcap_path)

    packets: dict = {}
    with open(pcap_path, "rb") as file:
        reader: Reader = Reader(file)
        for timestamp, packet in reader:
            try:
                ip: IP = IP(packet)
            except:
                print(f"Invalid IP packet: {packet}")
                continue

            peer_address: str
            orientation: int
            if inet_to_str(ip.src) == own_address:
                peer_address = inet_to_str(ip.dst)
                orientation = 1
            elif inet_to_str(ip.dst) == own_address:
                peer_address = inet_to_str(ip.src)
                orientation = -1
            else:
                print(
                    f"Invalid packet (neither source nor destination is the expected address) {inet_to_str(ip.src)} -> {inet_to_str(ip.dst)} (own address: {own_address})")
                continue
            if peer_address not in hosts_by_address.keys():
                continue
            relay_name: str = hosts_by_address[peer_address]
            if relay_name not in streams_by_guard:
                continue
            for stream_id in streams_by_guard[relay_name]:
                stream: dict = streams[stream_id]
                identifier: str = f"{stream['circuit_id']}-{site_indexes[stream['destination_ip']]}"
                if stream["start_time"] <= timestamp and stream["end_time"] >= timestamp:
                    if identifier not in packets:
                        packets[identifier] = []
                    packets[identifier].append(
                        f"{timestamp}\t{ip.len*orientation}")
    for identifier in packets.keys():
        with open(os.path.join(output_path, "inflow", identifier), "w") as file:
            file.write("\n".join(packets[identifier]))


def parse_pcap_outflow(data_path: str, streams: dict, streams_by_destination: dict, site_indexes: dict, output_path: str) -> None:
    if not os.path.exists(os.path.join(output_path, "outflow")):
        os.makedirs(os.path.join(output_path, "outflow"))

    packets: dict = {}
    for pcap_path in find_exit_pcap_paths(data_path):
        own_address: str = find_ip(pcap_path)
        with open(pcap_path, "rb") as file:
            reader: Reader = Reader(file)
            for timestamp, packet in reader:
                try:
                    ip: IP = IP(packet)
                except:
                    print(f"Invalid IP packet: {packet}")
                    continue

                peer_address: str
                orientation: int
                if inet_to_str(ip.src) == own_address:
                    peer_address = inet_to_str(ip.dst)
                    orientation = 1
                elif inet_to_str(ip.dst) == own_address:
                    peer_address = inet_to_str(ip.src)
                    orientation = -1
                else:
                    print(
                        f"Invalid packet (neither source nor destination is the expected address) {inet_to_str(ip.src)} -> {inet_to_str(ip.dst)} (own address: {own_address})")
                    continue
                if peer_address not in streams_by_destination.keys():
                    continue
                for stream_id in streams_by_destination[peer_address]:
                    stream: dict = streams[stream_id]
                    identifier: str = f"{stream['circuit_id']}-{site_indexes[stream['destination_ip']]}"
                    if stream["start_time"] <= timestamp and stream["end_time"] + 1 >= timestamp:
                        if identifier not in packets:
                            packets[identifier] = []
                        packets[identifier].append(
                            f"{timestamp}\t{ip.len*orientation}")
    for identifier in packets.keys():
        with open(os.path.join(output_path, "outflow", identifier), "w") as file:
            file.write("\n".join(packets[identifier]))


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-d", "--data_path", type=str, required=True)
    parser.add_argument("-c", "--config_path", type=str, required=True)
    parser.add_argument("-o", "--output_path", type=str,
                        required=False, default="dataset")
    args = parser.parse_args()

    # Parse arguments
    data_path: str = args.data_path
    config_path: str = args.config_path
    output_path: str = args.output_path

    if not os.path.exists(data_path):
        raise Exception("Data path does not exist")
    if not os.path.exists(config_path):
        raise Exception("Config path does not exist")
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    # Create pairing of (exit fingerprint, server ip) to (start time, end time, circuit id, stream id)
    client_path: str = find_client_path(data_path)
    client_pcap_path: str = find_pcap_path(client_path)
    oniontrace_path: str = get_oniontrace_path(client_path)
    streams: dict = parse_oniontrace(oniontrace_path, output_path)

    # Create dictionary of destination address to idx
    site_indexes: dict = {}
    idx: int = 0
    for stream_id in streams.keys():
        site: str = streams[stream_id]["destination_ip"]
        if site not in site_indexes.keys():
            site_indexes[site] = idx
            idx += 1
    with open(os.path.join(output_path, "site_indexes.json"), "w") as file:
        json.dump(site_indexes, file, indent=4)

    # Create dictonary of relay name to ip address
    hosts_by_address: dict = {}
    with open(config_path, "r") as file:
        config: dict = yaml.safe_load(file)
        for relay in config["hosts"].keys():
            if "ip_addr" in config["hosts"][relay].keys():
                hosts_by_address[config["hosts"][relay]["ip_addr"]] = relay
    with open(os.path.join(output_path, "hosts_by_address.json"), "w") as file:
        json.dump(hosts_by_address, file, indent=4)

    streams_by_guard: dict = {}
    for stream_id in streams.keys():
        guard_name: str = streams[stream_id]["guard_name"]
        if guard_name not in streams_by_guard.keys():
            streams_by_guard[guard_name] = []
        streams_by_guard[guard_name].append(stream_id)
    with open(os.path.join(output_path, "streams_by_guard.json"), "w") as file:
        json.dump(streams_by_guard, file, indent=4)

    streams_by_destination: dict = {}
    for stream_id in streams.keys():
        destination_ip: str = streams[stream_id]["destination_ip"].split(":")[
            0]
        if destination_ip not in streams_by_destination.keys():
            streams_by_destination[destination_ip] = []
        streams_by_destination[destination_ip].append(stream_id)
    with open(os.path.join(output_path, "streams_by_destination.json"), "w") as file:
        json.dump(streams_by_destination, file, indent=4)

    parse_pcap_inflow(client_pcap_path, streams, streams_by_guard,
                      hosts_by_address, site_indexes, output_path)
    parse_pcap_outflow(data_path, streams, streams_by_destination,
                       site_indexes, output_path)
