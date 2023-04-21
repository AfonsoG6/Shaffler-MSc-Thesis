conda create -y --name tf python=3.6.8
conda activate tf
conda install -y cudatoolkit=10.1.*
conda install -y cudnn=7.6.4=cuda10.1_0
pip install tensorflow==2.2.3 tensorflow-gpu==2.2.3
mkdir -p $CONDA_PREFIX/etc/conda/activate.d
echo 'export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$CONDA_PREFIX/lib/' >> $CONDA_PREFIX/etc/conda/activate.d/env_vars.sh
source $CONDA_PREFIX/etc/conda/activate.d/env_vars.sh
# Verify install:
python3 -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))"