# Utility functions for evaluation (taken from the original implementation of DeepCoFFEA)

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

def Cosine_Similarity_eval(tor_embs, exit_embs, similarity_threshold, single_output_l, evaluating_window, last_window, correlated_shreshold, cosine_similarity_all_list, multi_output_list, flow):
    number_of_lines = tor_embs.shape[0]
    for tor_emb_index in range(0, number_of_lines):
        t = similarity_threshold[tor_emb_index]
        constant_num = int(tor_emb_index * number_of_lines)
        for exit_emb_index in range(0, number_of_lines):
            if cosine_similarity_all_list[tor_emb_index][exit_emb_index] >= t:
                single_output_l[constant_num + exit_emb_index] = single_output_l[constant_num + exit_emb_index] + 1

    if evaluating_window == last_window:
        TP = 0
        TN = 0
        FP = 0
        FN = 0

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

        multi_output_list.append(TP)
        multi_output_list.append(FP)
        multi_output_list.append(TN)
        multi_output_list.append(FN)
        multi_output_list.append(TPR)
        multi_output_list.append(FPR)
        multi_output_list.append(calculate_bdr(TPR, FPR, flow))
        print(TP, FP, TN, FN, TPR, FPR, calculate_bdr(TPR, FPR, flow))

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