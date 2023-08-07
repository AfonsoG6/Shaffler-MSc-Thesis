from argparse import ArgumentParser
import yaml
import os

def disable_cover(hosts_path: str, config: dict):
    for host in config["hosts"].keys():
        if host.startswith("customclient"):
            processes_to_rm: list = []
            for process in config["hosts"][host]["processes"]:
                if process["path"].endswith("python3"):
                    processes_to_rm.append(process)
                if process["path"].endswith("tor"):
                    process["args"] = process["args"].replace(" -f torrc", "")
            for process in processes_to_rm:
                config["hosts"][host]["processes"].remove(process)
    for host in os.listdir(hosts_path):
        if host.startswith("customclient"):
            torrc_path = os.path.join(hosts_path, host, "torrc")
            open(torrc_path, 'w').close() # clear file
            
def enable_cover(hosts_path: str, config: dict, templates_path: str):
    for host in config["hosts"].keys():
        if host.startswith("customclient"):
            cover_processes = yaml.load(open(os.path.join(templates_path, "cover_processes.yaml"), "r"), Loader=yaml.FullLoader)
            config["hosts"][host]["processes"] += cover_processes
            
    for host in os.listdir(hosts_path):
        if host.startswith("customclient"):
            dest_torrc_path = os.path.join(hosts_path, host, "torrc")
            with open(dest_torrc_path, 'w') as o:
                o.write(f"%include ../../../conf/tor.os.torrc")

def enable_one_circuit(hosts_path: str):
    for host in os.listdir(hosts_path):
        if host.startswith("customclient"):
            dest_torrc_path = os.path.join(hosts_path, host, "torrc")
            with open(dest_torrc_path, 'w') as o:
                o.write(f"%include ./torrc-circ")

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-s", "--simulation", type=str, required=True)
    parser.add_argument("--cover-on", action="store_true", required=False, default=False)
    parser.add_argument("--cover-off", action="store_true", required=False, default=False)
    parser.add_argument("--config", type=str, required=False, default="")
    parser.add_argument("--one-circuit", action="store_true", required=False, default=False)

    args = parser.parse_args()
    simulation: str = args.simulation
    if args.cover_on and args.one_circuit:
        print("One circuit mode is not compatible with cover traffic mode")

    hosts_path = os.path.join(simulation, "shadow.data.template", "hosts")
    config_path = os.path.join(simulation, "shadow.config.yaml")
    templates_path = "templates"
    config = yaml.load(open(config_path, "r"), Loader=yaml.FullLoader)
    if args.cover_on:
        enable_cover(hosts_path, config, templates_path)
    if args.cover_off:
        disable_cover(hosts_path, config)
    if args.config != "" and os.path.exists(args.config):
        orig_config_path = args.config
        dest_config_path = os.path.join(simulation, "conf", "cover-config.json")
        with open(orig_config_path, 'r') as i:
            data = i.read()
        with open(dest_config_path, 'w') as o:
            o.write(data)
    if args.one_circuit:
        enable_one_circuit(hosts_path)

    yaml.dump(config, open(config_path, "w"), default_flow_style=False, sort_keys=False)

    print("Done!")
