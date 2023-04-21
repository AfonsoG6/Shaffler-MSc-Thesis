import numpy as np
import pickle
import os
import random
import argparse


def get_params():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', '-d', type=str,
                        default='./datasets/CrawlE_Proc/')
    parser.add_argument('--out', '-o', type=str,
                        default='./data/CrawlE_Proc_files.txt')
    parser.add_argument('--threshold', '-t', type=int, default=10)
    parser.add_argument('--interval', '-i', type=int, default=5)
    parser.add_argument('--windows', '-w', type=int, default=11)
    parser.add_argument('--addnum', '-a', type=int, default=2)
    args = parser.parse_args()
    return args


def find_key(input_dict, value):
    return {k for k, v in input_dict.items() if v == value}


def parse_csv(csv_path, interval, final_names, threshold):  # option: 'sonly', 'tonly', 'both'
    # fw=open('/data/seoh/greaterthan50.txt','w+')
    HERE_PATH = csv_path+'inflow'
    THERE_PATH = csv_path+'outflow'
    print(HERE_PATH, THERE_PATH, interval)
    # here
    here = []
    there = []
    here_len = []
    there_len = []
    h_cnt = 0
    t_cnt = 0
    flow_cnt = 0
    file_names = []
    for txt_file in os.listdir(HERE_PATH):
        file_names.append(txt_file)

    # for txt_file in open('/data/seoh/greaterthan50.txt','r').readlines():
    #    file_names.append(txt_file.strip())

    for i in range(len(file_names)):
        here_seq = []
        there_seq = []
        num_here_big_pkt_cnt = []
        num_there_big_pkt_cnt = []

        with open(HERE_PATH+'/'+file_names[i]) as f:
            # print(HERE_PATH+'/'+file_names[i])
            h_lines = []
            full_lines = f.readlines()
            for line in full_lines:
                time = float(line.split('\t')[0])
                if float(time) > interval[1]:
                    break
                if float(time) < interval[0]:
                    continue
                h_lines.append(line)

        with open(THERE_PATH + '/' + file_names[i]) as f:

            t_lines = []
            full_lines = f.readlines()
            for line in full_lines:
                time = float(line.split('\t')[0])
                if float(time) > interval[1]:
                    break
                if float(time) < interval[0]:
                    continue
                t_lines.append(line)
        if (len(h_lines) > threshold) and (len(t_lines) > threshold):
            if file_names[i] in final_names.keys():
                final_names[file_names[i]] += 1
            else:
                final_names[file_names[i]] = 1

    for x in final_names:
        print(x, final_names[x])


def create_overlap_window_csv(csv_path, out_path, threshold, interval, num_windows, addnum):
    global final_names
    final_names = {}
    fw = open(out_path, 'w+')
    for win in range(num_windows):
        parse_csv(csv_path, [win*addnum, win*addnum +
                  interval], final_names, threshold)
        # np.savez_compressed('/project/hoppernj/research/seoh/new_dcf_data/new_overlap_interval' + str(interval) + '_win' + str(win) + '_addn' + str(addnum) + '.npz',
        #         tor=here, exit=there)
    for name in list(find_key(final_names, num_windows)):

        fw.write(name)
        fw.write('\n')
    fw.close()


if __name__ == '__main__':
    args = get_params()

    data_path = args.data
    out_file_path = args.out
    # min number of packets per window in both ends, used  30 for 500
    threshold = args.threshold
    interval = args.interval  # window size in seconds
    windows = args.windows  # number of windows
    addnum = args.addnum  # number of seconds to add to the window each time
    # That is, we drop the flow pairs if either of them has pkt count < threshold.
    create_overlap_window_csv(data_path, out_file_path,
                              threshold, interval, windows, addnum)
