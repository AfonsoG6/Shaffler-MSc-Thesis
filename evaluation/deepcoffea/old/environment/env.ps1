conda create -y --name tf python=3.6.8
conda activate tf
conda install -y cudatoolkit=10.0.130 cudnn=7.6.4=cuda10.0_0
pip install -r requirements.txt
mkdir -p $env:CONDA_PREFIX/etc/conda/activate.d
echo 'set LD_LIBRARY_PATH $env:CONDA_PREFIX\lib\' >> $env:CONDA_PREFIX/etc/conda/activate.d/env_vars.sh
set LD_LIBRARY_PATH $env:CONDA_PREFIX\lib\