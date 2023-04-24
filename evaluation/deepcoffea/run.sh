ENV_NAME="tf"

while getopts t:i:w:a:g:r:m: flag
do
    case "${flag}" in
        t) threshold=${OPTARG};;
        i) interval=${OPTARG};;
        w) windows=${OPTARG};;
        a) addnum=${OPTARG};;
        g) gpu=${OPTARG};;
        r) redirect=${OPTARG};;
        m) mode=${OPTARG};;
    esac
done

if [ -z "$gpu" ];
then
    gpu=0
fi

if [ -z "$redirect" ];
then
    redirect=0
fi

if [ -z "$mode" ];
then
    mode=1
fi

mode = $mode - 1

echo "mode: $mode | threshold: $threshold | interval: $interval | windows: $windows | addnum: $addnum | use gpu: $gpu | redirect: $redirect"

if [ -z "$interval" ] || [ -z "$windows" ] || [ -z "$addnum" ];
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
    if [ $redirect -gt 0 ];
    then
        python3 filter.py -t $threshold -i $interval -w $windows -a $addnum &> filter.txt
    else
        python3 filter.py -t $threshold -i $interval -w $windows -a $addnum
    fi
fi

if [ $mode -lt 2 ];
then
    if [ $redirect -gt 0 ];
    then
        python3 new_dcf_parse.py -i $interval -w $windows -a $addnum &> parse.txt
    else
        python3 new_dcf_parse.py -i $interval -w $windows -a $addnum
    fi
fi

if [ $mode -lt 3 ];
then
    if [ $redirect -gt 0 ];
    then
        python3 train_fens.py -i $interval -w $windows -a $addnum -g $gpu &> train.txt
    else
        python3 train_fens.py -i $interval -w $windows -a $addnum -g $gpu
    fi
fi

if [ $mode -lt 4 ];
then
    if [ $redirect -gt 0 ];
    then
        python3 eval_dcf.py -i $interval -w $windows -a $addnum -g $gpu &> eval.txt
    else
        python3 eval_dcf.py -i $interval -w $windows -a $addnum -g $gpu
    fi
fi