import time
import pathlib
import datetime
import argparse
import csv

import numpy as np

# pytorch version 1.13
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader
from sklearn.metrics.pairwise import cosine_similarity

from data_utils import DeepCoffeaDataset, TripletSampler, preprocess_dcf, partition_windows
from pdb import set_trace as bp

import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0,1,2,3"

class FeatureEmbeddingNetwork(nn.Module):

    def __init__(self, emb_size=64, input_size=1000):
        super().__init__()

        if input_size == 1000:
            emb_in = 1024
            self.last_pool = [8, 4, 3]
        elif input_size == 1600:
            emb_in = 1536
            self.last_pool = [8, 4, 3]
        elif input_size == 400:
            emb_in = 1024
            self.last_pool = [4, 2, 2]
        elif input_size == 600:
            emb_in = 1536
            self.last_pool = [4, 2, 2]
        else:
            raise ValueError(f"input_size: {input_size} is not supported")

        self.dropout = nn.Dropout(p=0.1)

        self.conv11 = nn.Conv1d(1, 32, 8, padding="same")
        self.conv12 = nn.Conv1d(32, 32, 8, padding="same")

        self.conv21 = nn.Conv1d(32, 64, 8, padding="same")
        self.conv22 = nn.Conv1d(64, 64, 8, padding="same")

        self.conv31 = nn.Conv1d(64, 128, 8, padding="same")
        self.conv32 = nn.Conv1d(128, 128, 8, padding="same")

        self.conv41 = nn.Conv1d(128, 256, 8, padding="same")
        self.conv42 = nn.Conv1d(256, 256, 8, padding="same")

        self.emb = nn.Linear(emb_in, emb_size)

    def forward(self, x):
        if len(x.size()) == 2:
            x = x.unsqueeze(1)

        x = F.elu(self.conv11(x))
        x = F.elu(self.conv12(x))
        x = F.max_pool1d(x, 8, 4, padding=2)
        x = self.dropout(x)

        x = F.relu(self.conv21(x))
        x = F.relu(self.conv22(x))
        x = F.max_pool1d(x, 8, 4, padding=3)
        x = self.dropout(x)

        x = F.relu(self.conv31(x))
        x = F.relu(self.conv32(x))
        x = F.max_pool1d(x, 8, 4, padding=3)
        x = self.dropout(x)

        x = F.relu(self.conv41(x))
        x = F.relu(self.conv42(x))
        x = F.max_pool1d(x, self.last_pool[0], self.last_pool[1], padding=self.last_pool[2])
        x = self.dropout(x)

        x = torch.reshape(x, (x.size(0), -1))
        x = torch.squeeze(self.emb(x))
        return x


def triplet_loss(a_out, p_out, n_out, dev, alpha=0.1):
    # cosine similarity is the default correlation function used in the paper
    #  other distance function such as softmax, kNN clustering can be used.
    # a_out.size() (or p_out/n_out): (batch_size, emb_size)
    pos_sim = F.cosine_similarity(a_out, p_out)     # (batch_size,)
    neg_sim = F.cosine_similarity(a_out, n_out)     # (batch_size,)

    zeros = torch.zeros(pos_sim.size(0), device=dev)           # (batch_size,)
    losses = torch.maximum(zeros, neg_sim - pos_sim + alpha)    # (batch_size,)
    return losses.mean()


@torch.no_grad()
def inference(anchor, pandn, loader, dev):
    loader.sampler.train = False
    anchor.eval()
    pandn.eval()

    tor_embs = []
    exit_embs = []
    for _, (xa_batch, xp_batch) in enumerate(loader):
        xa_batch, xp_batch = xa_batch.to(dev), xp_batch.to(dev)

        a_out = anchor(xa_batch)
        p_out = pandn(xp_batch)

        tor_embs.append(a_out.numpy(force=True))
        exit_embs.append(p_out.numpy(force=True))

    tor_embs = np.concatenate(tor_embs)     # (N, emb_size)
    exit_embs = np.concatenate(exit_embs)   # (N, emb_size)
    print(f"Inference {len(loader.dataset)} pairs done.")
    return tor_embs, exit_embs


def main(mode: str,
         delta: int,
         win_size: int,
         n_wins: int,
         threshold: int,
         tor_len: int,
         exit_len: int,
         n_test: int,
         alpha: float,
         emb_size: int,
         lr: float,
         max_ep: int,
         batch_size: int,
         data_root: str,
         ckpt: str):
    assert mode in set(["train", "test"]), f"mode: {mode} is not supported"

    # To ensure device-agnostic reproducibility
    torch.manual_seed(114)
    rng = np.random.default_rng(114)
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = False
        torch.use_deterministic_algorithms(False)   # If set to True, will throw error when encountering non-deterministic ops
        dev = torch.device("cuda")
    else:
        dev = torch.device("cpu")

    data_root = pathlib.Path(data_root)

    if mode == "train":

        anchor = FeatureEmbeddingNetwork(emb_size=emb_size, input_size=tor_len*2).to(dev)
        pandn = FeatureEmbeddingNetwork(emb_size=emb_size, input_size=exit_len*2).to(dev)

        if "dataset_21march_2022_3" in data_root.name:
            data_name = "21march"
        elif "20x15_29november_2022_v1" in data_root.name:
            data_name = "29november"
        elif "30november_2022_v1" in data_root.name:
            data_name = "30november"
        elif "CrawlE_Proc" in data_root.name:
            data_name = "deepcoffea"
        else:
            data_name = data_root.name
            #raise ValueError(f"data: {data_root.name} is not supported.")

        save_dir = pathlib.Path("./experiments") / f"deepcoffea_{data_name}_d{delta}_ws{win_size}_nw{n_wins}_thr{threshold}_tl{tor_len}_el{exit_len}_nt{n_test}_ap{alpha:.0e}_es{emb_size}_lr{lr:.0e}_mep{max_ep}_bs{batch_size}"
        if not save_dir.exists():
            save_dir.mkdir(parents=True)

        trainable_params = list(anchor.parameters()) + list(pandn.parameters())
        #optimizer = optim.SGD(trainable_params, lr=lr, weight_decay=1e-6, momentum=0.9, nesterov=True)
        optimizer = optim.Adam(trainable_params, lr=lr)

        train_set = DeepCoffeaDataset(data_root, delta, win_size, n_wins, threshold, tor_len, exit_len, n_test, True)
        train_sampler = TripletSampler(train_set, alpha, rng, True)
        train_loader = DataLoader(train_set, sampler=train_sampler, batch_size=batch_size)

        test_set = DeepCoffeaDataset(data_root, delta, win_size, n_wins, threshold, tor_len, exit_len, n_test, False)
        test_loader = DataLoader(test_set, batch_size=batch_size)

        best_loss_mean = 0.01

        for ep in range(max_ep):
            if ep != 0:
                # compute the cosine similarity table
                tor_embs, exit_embs = inference(anchor, pandn, train_loader, dev)
                train_set.sim_table = cosine_similarity(tor_embs, exit_embs)    # this is going to take a while

            tst = time.time()
            
            train_sampler.train = True
            losses = []
            anchor.train()
            pandn.train()
            for i, (xa_batch, xp_batch, xn_batch) in enumerate(train_loader):
                xa_batch, xp_batch, xn_batch = xa_batch.to(dev), xp_batch.to(dev), xn_batch.to(dev)          

                optimizer.zero_grad()
                a_out = anchor(xa_batch)
                p_out = pandn(xp_batch)
                n_out = pandn(xn_batch)

                loss = triplet_loss(a_out, p_out, n_out, dev, alpha)
                loss.backward()
                optimizer.step()
                
                losses.append(loss.item())

                if i % 100 == 0:
                    print(f"[{ep+1:03d}/{max_ep}] [{i:04d}/{len(train_loader):04d}] Loss: {loss.item():.4f}")

            tdur = time.time() - tst
            print(f"[{ep+1:03d}/{max_ep}] (Training) Loss μ: {np.mean(losses):.4f}, σ: {np.std(losses):.4f}, dur: {str(datetime.timedelta(seconds=tdur))}")

            # generate the corr_matrix and save it, evaluate it while generating the plots
            tor_embs, exit_embs = inference(anchor, pandn, test_loader, dev)
            corr_matrix = cosine_similarity(tor_embs, exit_embs)

            if np.mean(losses) < best_loss_mean:
                best_loss_mean = np.mean(losses)
                print("Best training loss (avg) so far.\n")

                # save the metrics
                # np.savez_compressed(save_dir / f"ep-{ep+1:03d}_loss{best_loss_mean:.5f}_metrics", corr_matrix=corr_matrix, loss_mean=best_loss_mean)

                # save the model snapshot
                torch.save({
                    "ep": ep+1,
                    "anchor_state_dict": anchor.state_dict(),
                    "pandn_state_dict": pandn.state_dict(),
                    "optim_state_dict": optimizer.state_dict(),
                    "loss": loss.item()
                }, save_dir / f"best_loss.pth")

            if np.mean(losses) < 0.003:
                break

    else:
        if ckpt is None:
            raise ValueError("ckpt is not set!")
        
        ckpt = pathlib.Path(ckpt).resolve()
        results_path = os.path.splitext(ckpt.as_posix())[0] + "_results.csv"
        fields = ckpt.parent.name.split("_")

        delta = int(fields[-12].split("d")[-1])
        win_size = int(fields[-11].split("ws")[-1])
        n_wins = int(fields[-10].split("nw")[-1])
        threshold = int(fields[-9].split("thr")[-1])
        tor_len = int(fields[-8].split("tl")[-1])
        exit_len = int(fields[-7].split("el")[-1])
        n_test = int(fields[-6].split("nt")[-1])
        emb_size = int(fields[-4].split("es")[-1])
        batch_size = int(fields[-1].split("bs")[-1])
        #ep = int(ckpt.name.split("_")[0].split("-")[1])
        
        rank_thr_list = [60, 50, 47, 43, 40, 37, 33, 28, 24, 20, 16.667, 14, 12.5, 11, 10, 9, 8.333, 7, 6.25, 5, 4.545, 3.846, 2.941, 1.667, 1.6, 1.5, 1.4, 1.3, 1.2, 1.1, 1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2]
        minimum_windows_positive = 1 + n_wins // 2
        if n_wins == 7:
            minimum_windows_positive = 6
        elif n_wins == 9:
            minimum_windows_positive = 7
        elif n_wins == 11:
            minimum_windows_positive = 9
            
        rank_multi_output = []
        for i in range(0, len(rank_thr_list)):
            rank_multi_output.append([(rank_thr_list[i])])
            
        activated_windows = []
        for i in range(n_wins):
            activated_windows.append(i)
        last_activated_window = activated_windows[-1]
        
        pth_content = torch.load(ckpt)

        anchor = FeatureEmbeddingNetwork(emb_size=emb_size, input_size=tor_len*2).to(dev)
        anchor.load_state_dict(pth_content["anchor_state_dict"])
        pandn = FeatureEmbeddingNetwork(emb_size=emb_size, input_size=exit_len*2).to(dev)
        pandn.load_state_dict(pth_content["pandn_state_dict"])
        print(f"Snapshot: '{ckpt}' loaded")
        test_set = DeepCoffeaDataset(data_root, delta, win_size, n_wins, threshold, tor_len, exit_len, n_test, False)
        test_loader = DataLoader(test_set, batch_size=batch_size)
        tor_embs, exit_embs = inference(anchor, pandn, test_loader, dev)
        
        for epoch_idx in range(len(rank_thr_list)):
            thr = rank_thr_list[epoch_idx]
            print(f"~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ We are in thr {thr} ({epoch_idx}/{len(rank_thr_list)}) ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")
            multi_output_list = rank_multi_output[epoch_idx]
            single_output = []
            for win in range(n_wins):
                print(f"~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ We are in window {win} ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~")

                if win == 0:
                    ini_cosine_output(single_output, tor_embs.shape[0])
                corr_matrix = cosine_similarity(tor_embs, exit_embs)
                threshold_result = threshold_finder(corr_matrix, thr)

                if win in activated_windows:
                    Cosine_Similarity_eval(tor_embs, exit_embs, threshold_result, single_output, win, last_activated_window, minimum_windows_positive, corr_matrix, multi_output_list, n_test)
        with open(results_path, "w", newline="") as rank_f:
            writer = csv.writer(rank_f)
            writer.writerow(["Threshold", "TPR", "FPR", "BDR"])
            writer.writerows(rank_multi_output)

# Every tor flow will have a unique threshold
def threshold_finder(input_similarity_list, thres_seed):
    output_threshold_list = []
    for simi_list_index in range(0, len(input_similarity_list)):
        temp = list(input_similarity_list[simi_list_index])
        temp.sort(reverse=True)

        cut_point = int((len(input_similarity_list[simi_list_index]) - 1) * ((thres_seed) / 100))
        output_threshold_list.append(temp[cut_point])
    return output_threshold_list

def ini_cosine_output(single_output_l, input_number):
    for pairs in range(0, (input_number * input_number)):
        single_output_l.append(0)

def Cosine_Similarity_eval(tor_embs, exit_embs, similarity_threshold, single_output_l, evaluating_window, last_window, correlated_shreshold, cosine_similarity_all_list, muti_output_list, flow):
    global total_vot
    # print('single_output_l ',np.array(single_output_l).shape)
    number_of_lines = tor_embs.shape[0]
    start_emd = time.time()
    for tor_emb_index in range(0, number_of_lines):
        t = similarity_threshold[tor_emb_index]
        constant_num = int(tor_emb_index * number_of_lines)
        for exit_emb_index in range(0, number_of_lines):
            if cosine_similarity_all_list[tor_emb_index][exit_emb_index] >= t:
                # print('single_output_l[constant_num + exit_emb_index] ',single_output_l[constant_num + exit_emb_index])
                single_output_l[constant_num + exit_emb_index] = single_output_l[constant_num + exit_emb_index] + 1

    if evaluating_window == last_window:
        TP = 0
        TN = 0
        FP = 0
        FN = 0

        # now begin to evaluate
        # print("evaluating .......")
        for tor_eval_index in range(0, tor_embs.shape[0]):
            for exit_eval_index in range(0, tor_embs.shape[0]):
                cos_condithon_a = tor_eval_index == exit_eval_index
                number_of_ones = single_output_l[(tor_eval_index * (tor_embs.shape[0])) + exit_eval_index]
                cos_condition_b = number_of_ones >= correlated_shreshold
                cos_condition_c = number_of_ones < correlated_shreshold

                if cos_condithon_a and cos_condition_b:
                    TP = TP + 1
                if cos_condithon_a and cos_condition_c:
                    FN = FN + 1
                if (not (cos_condithon_a)) and cos_condition_b:
                    FP = FP + 1
                if (not (cos_condithon_a)) and cos_condition_c:
                    TN = TN + 1

        print("TP: ", TP, "FN: ", FN, "FP: ", FP, "TN: ", TN)
        if (TP + FN) != 0:
            TPR = (float)(TP) / (TP + FN)
        else:
            TPR = -1

        if (FP + TN) != 0:
            FPR = (float)(FP) / (FP + TN)
        else:
            FPR = -1

        muti_output_list.append(TPR)
        muti_output_list.append(FPR)
        muti_output_list.append(calculate_bdr(TPR, FPR, flow))
        print(TPR, FPR, calculate_bdr(TPR, FPR, flow))

    # print(".....done!")
    end_time = time.time()
    total_vot = total_vot + (end_time - start_emd)


def calculate_bdr(tpr, fpr, flow):
    TPR = tpr
    FPR = fpr
    c = 1 / int(flow)
    u = (int(flow) - 1) / int(flow)
    if ((TPR * c) + (FPR * u)) != 0:
        BDR = (TPR * c) / ((TPR * c) + (FPR * u))
    else:
        BDR = -1
    return BDR

total_emb = 0
total_vot = 0
total_cos = 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deep Coffea.")
    parser.add_argument("--mode", default="train", type=str, help="To train or test.")
    parser.add_argument("--delta", default=3, type=float, help="For window partition (see data_utils.py).")
    parser.add_argument("--win_size", default=5, type=float, help="For window partition (see data_utils.py).")
    parser.add_argument("--n_wins", default=11, type=int, help="For window partition (see data_utils.py).")
    parser.add_argument("--threshold", default=20, type=int, help="For window partition (see data_utils.py).")
    parser.add_argument("--tor_len", default=500, type=int, help="Flow size for the tor pairs.")
    parser.add_argument("--exit_len", default=800, type=int, help="Flow size for the exit pairs.")
    parser.add_argument("--n_test", default=1000, type=int, help="Number of testing flow pairs.")
    parser.add_argument("--alpha", default=0.1, type=float, help="For triplet loss.")
    parser.add_argument("--emb_size", default=64, type=int, help="Feature embedding size.")
    parser.add_argument("--lr", default=0.001, type=float, help="Learning rate.")
    parser.add_argument("--ep", default=100000, type=int, help="Epochs to train.")
    parser.add_argument("--batch_size", default=256, type=int, help="Batch size.")
    
    
    parser.add_argument("--data_root", required=True, type=str, help="Path to preprocessed .npz.")
    parser.add_argument("--ckpt", default=None, type=str, help="Load path for the checkpoint model.")
    args = parser.parse_args()
    
    if "process" in args.mode:
        partition_windows(args.delta, args.win_size, args.n_wins, args.threshold, args.data_root)
        preprocess_dcf(args.delta, args.win_size, args.n_wins, args.threshold, args.tor_len, args.exit_len, args.n_test, args.data_root)
    else:
        main(args.mode, args.delta, args.win_size, args.n_wins, args.threshold, args.tor_len, args.exit_len, args.n_test, args.alpha, args.emb_size, args.lr, args.ep, args.batch_size, args.data_root, args.ckpt)
