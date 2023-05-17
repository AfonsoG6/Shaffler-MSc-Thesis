from argparse import ArgumentParser
from dpkt.pcap import Reader
from dpkt.ip import IP, inet_to_str
from progress_bar import print_progress_bar
import json
import yaml
import sys
import os
import re


def find_client_paths(data_path: str) -> list:
    client_paths: list = []
    client_pattern = re.compile(r"client")
    for element in os.listdir(data_path):
        if client_pattern.search(element):
            client_paths.append(os.path.join(data_path, element))
    if len(client_paths) > 0:
        print(f"Clients found: {len(client_paths)}")
    else:
        raise Exception("No client folder found")
    return client_paths


def get_oniontrace_path(client_path: str) -> str:
    oniontrace_path: str = ""
    oniontrace_pattern = re.compile(r"oniontrace\.1001\.stdout")
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
    pcap_pattern = re.compile(r"eth\d\.pcap")
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


def get_id(ids: list, tentative_id: int) -> int:
    id: int = tentative_id
    while id in ids:
        id += 13 % sys.maxsize
    return id


def get_all_values(dict_of_dict: dict) -> list:
    values: list = []
    for key in dict_of_dict.keys():
        for key2 in dict_of_dict[key].keys():
            values.append(dict_of_dict[key][key2])
    return values


circuit_ids: dict = {}


def get_global_circuit_id(client_idx: int, circuit_id: int) -> int:
    global circuit_ids
    if client_idx not in circuit_ids:
        circuit_ids[client_idx] = {}
    if circuit_id not in circuit_ids[client_idx]:
        circuit_ids[client_idx][circuit_id] = get_id(
            get_all_values(circuit_ids), circuit_id)
    return circuit_ids[client_idx][circuit_id]


def parse_oniontrace(oniontrace_path: str, streams: dict, client_idx: int) -> None:
    circuits: dict = {}
    circuit_built_pattern = re.compile(r"CIRC \d+ BUILT")
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
                circuit_id: int = get_global_circuit_id(
                    client_idx, int(tokens[1]))
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
                stream_id: int = get_id(list(streams.keys()), int(tokens[1]))
                circuit_id: int = get_global_circuit_id(
                    client_idx, int(tokens[3]))
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
    stream_ids_to_remove: list = []
    for stream_id in streams.keys():
        stream: dict = streams[stream_id]
        if not "end_time" in stream.keys():
            stream_ids_to_remove.append(stream_id)
        circuit_id: int = stream["circuit_id"]
        if circuit_id in circuits.keys():
            streams[stream_id]["guard_name"] = circuits[circuit_id]["guard_name"]
            streams[stream_id]["exit_name"] = circuits[circuit_id]["exit_name"]
        else:
            stream_ids_to_remove.append(stream_id)
    for stream_id in stream_ids_to_remove:
        streams.pop(stream_id)


def find_ip(pcap_path: str) -> str:
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


def parse_pcap_inflow(client_paths: list, streams: dict, streams_by_guard: dict, hosts_by_address: dict, site_indexes: dict, output_path: str) -> None:
    if os.path.exists(os.path.join(output_path, "inflow")):
        os.remove(os.path.join(output_path, "inflow"))
    os.makedirs(os.path.join(output_path, "inflow"))

    for client_path in client_paths:
        pcap_path: str = find_pcap_path(client_path)
        print(f"Parsing {pcap_path}...")
        own_address: str = find_ip(pcap_path)
        size_processed: int = 24    # bytes of pcap header
        size: int = os.path.getsize(pcap_path)
        with open(pcap_path, "rb") as file:
            reader: Reader = Reader(file)
            for timestamp, packet in reader:
                print_progress_bar(size_processed, size, 50)
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
                        with open(os.path.join(output_path, "inflow", identifier), "a") as file:
                            file.write(f"{timestamp}\t{ip.len*orientation}\n")
                # bytes of pcap packet header + packet
                size_processed += 16 + len(packet)
        print("\n")


def parse_pcap_outflow(data_path: str, streams: dict, streams_by_destination: dict, site_indexes: dict, output_path: str) -> None:
    if os.path.exists(os.path.join(output_path, "outflow")):
        os.remove(os.path.join(output_path, "outflow"))
    os.makedirs(os.path.join(output_path, "outflow"))

    for pcap_path in find_exit_pcap_paths(data_path):
        print(f"Parsing {pcap_path}...")
        own_address: str = find_ip(pcap_path)
        size_processed: int = 24    # bytes of pcap header
        size: int = os.path.getsize(pcap_path)
        with open(pcap_path, "rb") as file:
            reader: Reader = Reader(file)
            for timestamp, packet in reader:
                print_progress_bar(size_processed, size, 50)
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
                        with open(os.path.join(output_path, "outflow", identifier), "w") as file:
                            file.write(f"{timestamp}\t{ip.len*orientation}\n")
                # bytes of pcap packet header + packet
                size_processed += 16 + len(packet)
        print("\n")


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
    if not os.path.exists(os.path.join(output_path, "dictionaries")):
        os.makedirs(os.path.join(output_path, "dictionaries"))

    # Create pairing of (exit fingerprint, server ip) to (start time, end time, circuit id, stream id)
    aux_client_paths: list = find_client_paths(data_path)
    client_paths: list = []
    for client_path in aux_client_paths:
        try:
            find_pcap_path(client_path)
            client_paths.append(client_path)
        except Exception as e:
            continue
    streams: dict = {}
    client_idx: int = 0
    for client_path in client_paths:
        oniontrace_path: str = get_oniontrace_path(client_path)
        print(f"Parsing oniontrace file: {oniontrace_path}")
        parse_oniontrace(oniontrace_path, streams, client_idx)
        client_idx += 1
    with open(os.path.join(output_path, "dictionaries", "streams.json"), "w") as file:
        json.dump(streams, file, indent=4)

    # Create dictionary of destination address to idx
    print("Creating site_indexes dictionary...")
    site_indexes: dict = {}
    idx: int = 0
    for stream_id in streams.keys():
        site: str = streams[stream_id]["destination_ip"]
        if site not in site_indexes.keys():
            site_indexes[site] = idx
            idx += 1
    with open(os.path.join(output_path, "dictionaries", "site_indexes.json"), "w") as file:
        json.dump(site_indexes, file, indent=4)

    # Create dictonary of relay name to ip address
    print("Creating hosts_by_address dictionary...")
    hosts_by_address: dict = {}
    with open(config_path, "r") as file:
        config: dict = yaml.safe_load(file)
        for relay in config["hosts"].keys():
            if "ip_addr" in config["hosts"][relay].keys():
                hosts_by_address[config["hosts"][relay]["ip_addr"]] = relay
    with open(os.path.join(output_path, "dictionaries", "hosts_by_address.json"), "w") as file:
        json.dump(hosts_by_address, file, indent=4)

    # Create dictionary of stream id by guard name
    print("Creating streams_by_guard dictionary...")
    streams_by_guard: dict = {}
    for stream_id in streams.keys():
        guard_name: str = streams[stream_id]["guard_name"]
        if guard_name not in streams_by_guard.keys():
            streams_by_guard[guard_name] = []
        streams_by_guard[guard_name].append(stream_id)
    with open(os.path.join(output_path, "dictionaries", "streams_by_guard.json"), "w") as file:
        json.dump(streams_by_guard, file, indent=4)

    # Create dictionary of stream id by destination address
    print("Creating streams_by_destination dictionary...")
    streams_by_destination: dict = {}
    for stream_id in streams.keys():
        destination_ip: str = streams[stream_id]["destination_ip"].split(":")[
            0]
        if destination_ip not in streams_by_destination.keys():
            streams_by_destination[destination_ip] = []
        streams_by_destination[destination_ip].append(stream_id)
    with open(os.path.join(output_path, "dictionaries", "streams_by_destination.json"), "w") as file:
        json.dump(streams_by_destination, file, indent=4)

    print("Parsing pcap for inflow files...")
    parse_pcap_inflow(client_paths, streams, streams_by_guard,
                      hosts_by_address, site_indexes, output_path)
    print("Parsing pcap for outflow files...")
    parse_pcap_outflow(data_path, streams, streams_by_destination,
                       site_indexes, output_path)
