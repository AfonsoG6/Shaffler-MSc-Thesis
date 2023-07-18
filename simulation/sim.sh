dir=$1
if [ -z "$dir" ];
then
    echo "Usage: ./sim.sh <dir>"
    exit 1
fi

name=$(echo $dir | cut -d'_' -f 4)

echo "Starting ${name} Simulation"
cd /root/rendezmix/tor
git pull
./autogen.sh
./configure --disable-asciidoc --disable-unittests
make
make install

cd /part/simulation
rm -rf ${dir}/shadow.data ${dir}/shadow.log
tornettools simulate ${dir}
zip -r ${name}_sim.zip ${dir}

cd /part/simulation/datasets/
python3 stage.py -s ../${dir}
python3 parse.py -s ../${dir} -o ${name}
python3 cleanup.py -d ${name}
rm -rf ../${dir}/shadow.data ../${dir}/shadow.log
zip -r ${name}_dataset.zip ${name}
rm -rf ${name}
echo "Done!"