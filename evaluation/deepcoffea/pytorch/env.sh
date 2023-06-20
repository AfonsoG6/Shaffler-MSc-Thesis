ENV_NAME="torch"

conda create -y --name $ENV_NAME
eval "$(conda shell.bash hook)"
conda activate $ENV_NAME
pip install numpy torch sklearn tqdm
conda install -y cudnn
mkdir -p $CONDA_PREFIX/etc/conda/activate.d
echo 'export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$CONDA_PREFIX/lib/' >> $CONDA_PREFIX/etc/conda/activate.d/env_vars.sh
source $CONDA_PREFIX/etc/conda/activate.d/env_vars.sh