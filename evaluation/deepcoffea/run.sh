ENV_NAME="tf"

while getopts t:i:w:a:g:r: flag
do
    case "${flag}" in
        t) threshold=${OPTARG};;
        i) interval=${OPTARG};;
        w) windows=${OPTARG};;
        a) addnum=${OPTARG};;
        g) gpu=${OPTARG};;
        r) redirect=${OPTARG};;
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

echo "threshold: $threshold | interval: $interval | windows: $windows | addnum: $addnum | use gpu: $gpu | redirect: $redirect"

if [ -z "$interval" ] || [ -z "$windows" ] || [ -z "$addnum" ];
then
    echo "Please enter all the arguments"
    exit 1
fi

mkdir -p data/
mkdir -p data/DeepCCA_model/
mkdir -p datasets/
mkdir -p datasets/new_dcf_data/

eval "$(conda shell.bash hook)"
conda activate $ENV_NAME

if [ ! -z "$threshold" ];
then
    if [ $redirect -gt 0 ];
    then
        python3 filter.py -t $threshold -i $interval -w $windows -a $addnum &> filter.txt
        python3 new_dcf_parse.py -i $interval -w $windows -a $addnum &> parse.txt
    else
        python3 filter.py -t $threshold -i $interval -w $windows -a $addnum
        python3 new_dcf_parse.py -i $interval -w $windows -a $addnum
    fi
fi

if [ $redirect -gt 0 ];
then
    python3 train_fens.py -i $interval -w $windows -a $addnum -g $gpu &> train.txt
else
    python3 train_fens.py -i $interval -w $windows -a $addnum -g $gpu
fi
