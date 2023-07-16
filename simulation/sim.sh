while getopts d:n: flag
do
    case "${flag}" in
        d) dir=${OPTARG};;
        n) name=${OPTARG};;
    esac
done

if [ -z "$dir" ] || [ -z "$name" ];
then
    echo "Usage: ./sim.sh -d <dir> -n <name>"
    exit 1
fi

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