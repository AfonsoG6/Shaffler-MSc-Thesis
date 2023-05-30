import time, os
from datetime import datetime, timedelta
from argparse import ArgumentParser


def read_last_line(filename: str):
    with open(filename, "rb") as file:
        file.seek(-2, os.SEEK_END)
        while file.read(1) != b"\n":
            file.seek(-2, os.SEEK_CUR)
        line = file.readline().decode()
        while "shadow-worker" not in line:
            file.seek(-len(line) - 2, os.SEEK_CUR)
            while file.read(1) != b"\n":
                file.seek(-2, os.SEEK_CUR)
            line = file.readline().decode()
        return line


def get_simulation_time(logfile: str):
    return dtstr_to_sec(read_last_line(logfile).split(" ")[2])


def dtstr_to_sec(time_str: str):
    if len(time_str) > 15:
        time_str = time_str[:15]
    time_obj = datetime.strptime(time_str, "%H:%M:%S.%f")
    duration = timedelta(hours=time_obj.hour, minutes=time_obj.minute, seconds=time_obj.second, microseconds=time_obj.microsecond)
    return duration.total_seconds()


def sec_to_dtstr(time_sec: float):
    hours = int(time_sec // 3600)
    minutes = int((time_sec % 3600) // 60)
    seconds = int(time_sec % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def main():
    parser = ArgumentParser()
    parser.add_argument("-s", "--simulation", type=str, required=True)
    parser.add_argument("-i", "--interval", type=float, required=False, default=30)
    parser.add_argument("-d", "--duration", type=float, default=3)
    args = parser.parse_args()

    logfile = os.path.join(args.simulation, "shadow.log")

    avg_speed = 0
    t2 = get_simulation_time(logfile)
    while True:
        if not os.path.exists(logfile):
            time.sleep(args.interval)
            continue
        t1 = t2
        time.sleep(args.interval)
        t2 = get_simulation_time(logfile)
        curr_speed = round((t2 - t1) / args.interval, 6)
        if avg_speed == 0:
            avg_speed = curr_speed
        else:
            avg_speed = avg_speed*3/4 + curr_speed*1/4
        eta = sec_to_dtstr((args.duration * 3600 - t2) / avg_speed)
        with open("monitor.log", "a") as file:
            file.write(f"{datetime.now()},{curr_speed},{avg_speed},{eta}\n")
        print(f"Average SPD: {'{:.6f}'.format(avg_speed)}s /s   Current SPD: {'{:.6f}'.format(curr_speed)}s /s   ETA: {eta}......", end="\r")


if __name__ == "__main__":
    main()
