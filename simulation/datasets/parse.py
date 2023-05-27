from argparse import ArgumentParser
from subprocess import Popen
import pickle
import os
import re

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
    
    data_pattern: re.Pattern = re.compile(r"shadow\.data\.\d")
    for element in os.listdir(simulation):
        if data_pattern.search(element):
            batch_id: int = int(element.split(".")[-1])
            info_clients_path: str = os.path.join(stage_path, f"info_clients_{batch_id}.pickle")
            print("Loading data...")
            with open(info_clients_path, "rb") as file:
                info_clients: dict = pickle.load(file)
            
            hostnames: set = set()
            for hostname in info_clients.keys():
                hostnames.add(hostname)
            for filename in os.listdir(os.path.join(simulation, element, "hosts")):
                if filename.startswith("server"):
                    hostnames.add(filename)

            processes: list = []
            for hostname in hostnames:
                processes.append(Popen(["python3", "parse_host.py",
                    "-s", simulation,
                    "-b", str(batch_id),
                    "-n", hostname,
                    "-o", output_path]))
            for process in processes:
                process.wait()

    print("All processes finished.")

if __name__ == "__main__":
    main()