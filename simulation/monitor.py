import time, os
from datetime import datetime, timedelta
from argparse import ArgumentParser


def read_last_line(filename: str):
    with open(filename, "rb") as file:
        file.seek(-2, os.SEEK_END)
        while file.read(1) != b'\n':
            file.seek(-2, os.SEEK_CUR)
        return file.readline().decode()

def get_simulation_time(logfile: str):
    return convert_time(read_last_line(logfile).split(" ")[2])

def convert_time(time_str: str):
    time_obj = datetime.strptime(time_str, "%H:%M:%S.%f")
    duration = timedelta(hours=time_obj.hour, minutes=time_obj.minute, seconds=time_obj.second, microseconds=time_obj.microsecond)
    return duration.total_seconds()

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
        print(f"Current speed: {(t2-t1)/args.interval}s /s\t\t", end="\r")

if __name__ == "__main__":
    main()