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
if [ $gpu -gt 0 ];
then
    conda run -n $ENV_NAME conda install -y cudatoolkit=10.0.130 cudnn=7.6.4=cuda10.0_0
fi
conda run -n $ENV_NAME pip install -r requirements.txt
conda run -n $ENV_NAME mkdir -p $CONDA_PREFIX/etc/conda/activate.d
conda run -n $ENV_NAME echo 'export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$CONDA_PREFIX/lib/' >> $CONDA_PREFIX/etc/conda/activate.d/env_vars.sh
conda run -n $ENV_NAME source $CONDA_PREFIX/etc/conda/activate.d/env_vars.sh