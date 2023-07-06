# ----------------------- NORMAL SIMULATION ----------------------- #
echo "Starting Normal Simulation"
cd /root/rendezmix/tor
git pull
./autogen.sh
./configure --disable-asciidoc --disable-unittests
make
make install

cd /part/simulation
rm -rf sim_300_2_n/shadow.data sim_300_2_n/shadow.log
tornettools simulate sim_300_2_n
zip -r Normal_sim.zip sim_300_2_n

cd /part/simulation/datasets/
python3 stage.py -s ../sim_300_2_n
python3 parse.py -s ../sim_300_2_n -o Normal
python3 cleanup.py -d Normal
rm -rf sim_300_2_n/shadow.data sim_300_2_n/shadow.log
zip -r Normal_dataset.zip Normal
rm -rf Normal
echo "Done!"