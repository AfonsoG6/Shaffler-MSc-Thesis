#!/usr/bin/bash

while getopts t:i:w:a:g: flag
do
    case "${flag}" in
        t) threshold=${OPTARG};;
        i) interval=${OPTARG};;
        w) windows=${OPTARG};;
        a) addnum=${OPTARG};;
        g) gpu=${OPTARG};;
    esac
done

echo "threshold: $threshold | interval: $interval | windows: $windows | addnum: $addnum"

if [ -z "$interval" ] || [ -z "$windows" ] || [ -z "$addnum" ];
then
    echo "Please enter all the arguments"
    exit 1
fi

if [ -z "$gpu" ];
then
    gpu=0
fi

mkdir -p data/
mkdir -p data/DeepCCA_model/
mkdir -p datasets/
mkdir -p datasets/new_dcf_data/

if [ ! -z "$threshold" ];
then
    python3 filter.py -t $threshold -i $interval -w $windows -a $addnum
    python3 new_dcf_parse.py -i $interval -w $windows -a $addnum
fi

python3 train_fens.py -i $interval -w $windows -a $addnum -g $gpu