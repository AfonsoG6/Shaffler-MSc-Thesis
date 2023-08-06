from argparse import ArgumentParser
import yaml
import os

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-s", "--simulation", type=str, required=True)

    args = parser.parse_args()
    simulation: str = args.simulation

    config_path = os.path.join(simulation, "shadow.config.yaml")
    config = yaml.load(open(config_path, "r"), Loader=yaml.FullLoader)
    for host in config["hosts"].keys():
        if host.startswith("custom"):
            processes_to_rm: list = []
            for process in config["hosts"][host]["processes"]:
                if process["path"].endswith("python3"):
                    processes_to_rm.append(process)
                if process["path"].endswith("tor"):
                    process["args"] = process["args"].replace(" -f torrc", "")
            for process in processes_to_rm:
                config["hosts"][host]["processes"].remove(process)

    yaml.dump(config, open(config_path, "w"), default_flow_style=False, sort_keys=False)

    print("Done!")
