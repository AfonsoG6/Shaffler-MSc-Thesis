import os
from argparse import ArgumentParser       

def main():
    parser = ArgumentParser()
    parser.add_argument("-d", "--dataset_path", type=str, required=False, default="dataset")
    args = parser.parse_args()
    
    dataset_path: str = args.dataset_path
    inflow_path: str = os.path.join(dataset_path, "inflow")
    outflow_path: str = os.path.join(dataset_path, "outflow")
    
    inflow_files: list = os.listdir(inflow_path)
    outflow_files: list = os.listdir(outflow_path)

    for filename in inflow_files:
        if filename not in outflow_files:
            os.remove(os.path.join(inflow_path, filename))
            print(f"Removed {filename} from inflow")
    for filename in outflow_files:
        if filename not in inflow_files:
            os.remove(os.path.join(outflow_path, filename))
            print(f"Removed {filename} from outflow")

if __name__ == "__main__":
    main()