import time, os
from datetime import datetime, timedelta
from argparse import ArgumentParser


def read_last_line(filename: str):
    with open(filename, "rb") as file:
        file.seek(-2, os.SEEK_END)
        while file.read(1) != b'\n':
            file.seek(-2, os.SEEK_CUR)
        line = file.readline().decode()
        while "shadow-worker" not in line:
            file.seek(-len(line)-2, os.SEEK_CUR)
            while file.read(1) != b'\n':
                file.seek(-2, os.SEEK_CUR)
            line = file.readline().decode()
        return line

def get_simulation_time(logfile: str):
    return convert_time(read_last_line(logfile).split(" ")[2])

def convert_time(time_str: str):
    if len(time_str) > 15:
        time_str = time_str[:15]
    time_obj = datetime.strptime(time_str, "%H:%M:%S.%f")
    duration = timedelta(hours=time_obj.hour, minutes=time_obj.minute, seconds=time_obj.second, microseconds=time_obj.microsecond)
    return duration.total_seconds()

def main():
    parser = ArgumentParser()
    parser.add_argument("-s", "--simulation", type=str, required=True)
    parser.add_argument("-i", "--interval", type=float, required=False, default=30)
    args = parser.parse_args()
    
    logfile = os.path.join(args.simulation, "shadow.log")
    
    prev_speed = 0
    t2 = get_simulation_time(logfile)
    while True:
        t1 = t2
        time.sleep(args.interval)
        t2 = get_simulation_time(logfile)
        curr_speed = round((t2-t1)/args.interval, 6)
        print(f"Previous SPD: {'{:.6f}'.format(prev_speed)}s /s     Current SPD: {'{:.6f}'.format(curr_speed)}s /s", end="\r")
        prev_speed = curr_speed

if __name__ == "__main__":
    main()