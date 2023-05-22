from argparse import ArgumentParser
from subprocess import Popen
import pickle
import os

def main():
    parser = ArgumentParser()
    parser.add_argument("-s", "--simulation", type=str, required=True)
    parser.add_argument("-o", "--output_path", type=str, required=False, default="dataset")
    args = parser.parse_args()
    
    # Parse arguments
    simulation: str = args.simulation
    output_path: str = args.output_path
    stage_path: str = "stage"
    
    if not os.path.exists(simulation):
        raise Exception(f"Simulation path is not valid: {os.path.abspath(simulation)}")
    if not os.path.exists(stage_path):
        raise Exception(f"Stage path is not valid: {os.path.abspath(stage_path)}")
    
    print("Loading data...")
    with open(os.path.join(stage_path, "info_clients.pickle"), "rb") as file:
        info_clients: dict = pickle.load(file)
    with open(os.path.join(stage_path, "info_servers.pickle"), "rb") as file:
        info_servers: dict = pickle.load(file)
    
    hostnames: set = set()
    for hostname in info_clients.keys():
        hostnames.add(hostname)
    for hostname in info_servers.keys():
        hostnames.add(hostname)

    processes: list = []
    for hostname in hostnames:
        processes.append(Popen(["python3", "parse_host.py",
            "-s", simulation,
            "-n", hostname,
            "-o", output_path]))
    for process in processes:
        process.wait()

    print("All processes finished.")

if __name__ == "__main__":
    main()