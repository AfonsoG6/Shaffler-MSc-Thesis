ENV_NAME="tf"

while getopts t:i:w:a:g:d:m: flag
do
    case "${flag}" in
        t) threshold=${OPTARG};;
        i) interval=${OPTARG};;
        w) windows=${OPTARG};;
        a) addnum=${OPTARG};;
        g) gpu=${OPTARG};;
        d) dataset=${OPTARG};;
        m) mode=${OPTARG};;
    esac
done

if [ -z "$gpu" ];
then
    gpu=0
fi

if [ -z "$mode" ];
then
    mode=0
fi

echo "mode: $mode | threshold: $threshold | interval: $interval | windows: $windows | addnum: $addnum | use gpu: $gpu | dataset: $dataset"

if [ -z "$interval" ] || [ -z "$windows" ] || [ -z "$addnum" ] || [ -z "$dataset" ];
then
    echo "Please enter all the arguments"
    exit 1
fi

if [ $mode -eq 0 ] && [ -z "$threshold" ];
then
    echo "Please enter threshold"
    exit 1
fi

mkdir -p data/
mkdir -p data/DeepCCA_model/
mkdir -p datasets/
mkdir -p datasets/new_dcf_data/

eval "$(conda shell.bash hook)"
conda activate $ENV_NAME

if [ $mode -lt 1 ];
then
    python3 filter.py -t $threshold -i $interval -w $windows -a $addnum -d $dataset
fi

if [ $mode -lt 2 ];
then
    python3 new_dcf_parse.py -i $interval -w $windows -a $addnum -d $dataset
fi

if [ $mode -lt 3 ];
then
    python3 train_fens.py -i $interval -w $windows -a $addnum -g $gpu -d $dataset
fi

if [ $mode -lt 4 ];
then
    python3 eval_dcf.py -i $interval -w $windows -a $addnum -g $gpu -d $dataset
fi