ENV_NAME="tf"

while getopts g: flag
do
    case "${flag}" in
        g) gpu=${OPTARG};;
    esac
done

if [ -z "$gpu" ];
then
    gpu=0
fi

conda create -y --name $ENV_NAME python=3.6.8
eval "$(conda shell.bash hook)"
conda activate $ENV_NAME
if [ $gpu -lt 1 ];
then
    pip install tensorflow=1.13.0
fi
pip install -r requirements.txt
if [ $gpu -gt 0 ];
then
    conda install -y cudatoolkit=10.0.130 cudnn=7.6.4=cuda10.0_0
    mkdir -p $CONDA_PREFIX/etc/conda/activate.d
    echo 'export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$CONDA_PREFIX/lib/' >> $CONDA_PREFIX/etc/conda/activate.d/env_vars.sh
    source $CONDA_PREFIX/etc/conda/activate.d/env_vars.sh
fi