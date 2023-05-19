from stage import find_client_paths, find_exit_pcap_paths, find_pcap_path
from argparse import ArgumentParser
from subprocess import Popen
import shutil
import os

def main():
    parser = ArgumentParser()
    parser.add_argument("-d", "--data_path", type=str, required=True)
    parser.add_argument("-s", "--stage_path", type=str, required=False, default="stage")
    parser.add_argument("-o", "--output_path", type=str, required=False, default="dataset")
    args = parser.parse_args()
    
    # Parse arguments
    data_path: str = args.data_path
    stage_path: str = args.stage_path
    output_path: str = args.output_path
    
    # Find all client paths
    aux_client_paths: list = find_client_paths(data_path)
    client_paths: list = []
    for client_path in aux_client_paths:
        try:
            find_pcap_path(client_path)
            client_paths.append(client_path)
        except:
            continue
    
    processes: list = []
    for client_path in client_paths:
        pcap_path: str = find_pcap_path(client_path)
        print(f"Parsing pcap file: {pcap_path}")
        processes.append(Popen(["python3", "parse_pcap.py",
               "-d", data_path,
               "-s", stage_path,
               "-o", "temp",
               "-p", pcap_path,
               "-t", "inflow"]))
    for pcap_path in find_exit_pcap_paths(data_path):
        print(f"Parsing pcap file: {pcap_path}")
        processes.append(Popen(["python3", "parse_pcap.py",
               "-d", data_path,
               "-s", stage_path,
               "-o", "temp",
               "-p", pcap_path,
               "-t", "outflow"]))
    for process in processes:
        process.wait()
    print("All processes finished.")
    
    ids_inflow: set = set()
    paths_inflow: dict = {}
    for host_dir in os.listdir(os.path.join("temp", "inflow")):
        for file_name in os.listdir(os.path.join("temp", "inflow", host_dir)):
            ids_inflow.add(file_name)
            if file_name not in paths_inflow:
                paths_inflow[file_name] = []
            paths_inflow[file_name].append(os.path.join("temp", "inflow", host_dir, file_name))

    ids_outflow: set = set()
    paths_outflow: dict = {}
    for host_dir in os.listdir(os.path.join("temp", "outflow")):
        for file_name in os.listdir(os.path.join("temp", "outflow", host_dir)):
            ids_outflow.add(file_name)
            if file_name not in paths_outflow:
                paths_outflow[file_name] = []
            paths_outflow[file_name].append(os.path.join("temp", "inflow", host_dir, file_name))
    
    for file_name in ids_inflow:
        with open(os.path.join(output_path, "inflow", file_name), 'wb') as wfd:
            for f in paths_inflow[file_name]:
                with open(f, 'rb') as rfd:
                    shutil.copyfileobj(rfd, wfd)
        print(f"File {file_name} saved. (inflow)")
    
    for file_name in ids_outflow:
        with open(os.path.join(output_path, "outflow", file_name), 'wb') as wfd:
            for f in paths_outflow[file_name]:
                with open(f, 'rb') as rfd:
                    shutil.copyfileobj(rfd, wfd)
        print(f"File {file_name} saved. (outflow)")

if __name__ == "__main__":
    main()