from stage import find_client_paths, find_exit_pcap_paths, find_pcap_path
from argparse import ArgumentParser
from subprocess import Popen

def main():
    parser = ArgumentParser()
    parser.add_argument("-d", "--data_path", type=str, required=True)
    parser.add_argument("-s", "--stage_path", type=str, required=False, default="stage")
    parser.add_argument("-o", "--output_path", type=str, required=False, default="temp")
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
               "-o", output_path,
               "-p", pcap_path,
               "-t", "inflow"]))
    for pcap_path in find_exit_pcap_paths(data_path):
        print(f"Parsing pcap file: {pcap_path}")
        processes.append(Popen(["python3", "parse_pcap.py",
               "-d", data_path,
               "-s", stage_path,
               "-o", output_path,
               "-p", pcap_path,
               "-t", "outflow"]))
    for process in processes:
        process.wait()
        print(f"Process {process.pid} finished")

if __name__ == "__main__":
    main()