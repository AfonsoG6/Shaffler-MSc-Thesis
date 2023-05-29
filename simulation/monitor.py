import time, os
from argparse import ArgumentParser

def read_last_line(filename: str):
    with open(filename, "rb") as file:
        file.seek(-2, os.SEEK_END)
        while file.read(1) != b'\n':
            file.seek(-2, os.SEEK_CUR)
        return file.readline().decode()

def get_simulation_time(logfile: str):
    return float(read_last_line(logfile).split(" ")[2])

def main():
    parser = ArgumentParser()
    parser.add_argument("-s", "--simulation", type=str, required=True)
    parser.add_argument("-i", "--interval", type=float, required=False, default=30)
    args = parser.parse_args()
    
    logfile = os.path.join(args.simulation, "shadow.log")
    
    t2 = get_simulation_time(logfile)
    while True:
        t1 = t2
        time.sleep(args.interval)
        t2 = get_simulation_time(logfile)
        print(f"Current speed: {(t2-t1)/args.interval}s /s", end="\r")
