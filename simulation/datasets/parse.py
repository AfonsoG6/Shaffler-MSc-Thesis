from argparse import ArgumentParser
from subprocess import Popen
import pickle
import shutil
import os

def main():
    parser = ArgumentParser()
    parser.add_argument("-s", "--simulation", type=str, required=True)
    parser.add_argument("-o", "--output_path", type=str, required=False, default="dataset")
    parser.add_argument("-c", "--capture_interval", type=float, default=150)
    args = parser.parse_args()
    
    # Parse arguments
    simulation: str = args.simulation
    output_path: str = args.output_path
    capture_interval: float = args.capture_interval
    stage_path: str = "stage"
    
    if not os.path.exists(simulation):
        raise Exception(f"Simulation path is not valid: {os.path.abspath(simulation)}")
    if not os.path.exists(stage_path):
        raise Exception(f"Stage path is not valid: {os.path.abspath(stage_path)}")
    
    info_clients_path: str = os.path.join(stage_path, f"info_clients.pickle")
    print("Loading data...")
    with open(info_clients_path, "rb") as file:
        info_clients: dict = pickle.load(file)
    
    hostnames: set = set()
    for hostname in info_clients.keys():
        hostnames.add(hostname)
    for filename in os.listdir(os.path.join(simulation, "shadow.data", "hosts")):
        if filename.startswith("server"):
            hostnames.add(filename)

    processes: list = []
    for hostname in hostnames:
        processes.append(Popen(["python3", "parse_host.py",
            "-s", simulation,
            "-n", hostname,
            "-c", str(capture_interval),
            "-o", output_path]))
    for process in processes:
        process.wait()
    print("All processes finished.")
    
    outflow_path: str = os.path.join(output_path, "outflow")
    for flow in os.listdir(outflow_path):
        flow_path: str = os.path.join(outflow_path, flow)
        if os.path.isdir(flow_path):
            print(f"Merging {flow}...")
            data = []
            for host in os.listdir(flow_path):
                with open(os.path.join(flow_path, host), "r") as file:
                    for line in file.readlines():
                        timestamp: float = float(line.split("\t")[0])
                        length: int = int(line.split("\t")[1])
                        data.append((timestamp, length))
            data.sort(key=lambda x: x[0])
            shutil.rmtree(flow_path, ignore_errors=True)
            with open(flow_path, "w") as file:
                for timestamp, length in data:
                    file.write(f"{timestamp}\t{length}\n")
            print(f"Finished merging {flow}.")
    print("Done.")

if __name__ == "__main__":
    main()