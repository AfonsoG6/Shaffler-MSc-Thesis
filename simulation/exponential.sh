# ----------------------- NORMAL SIMULATION ----------------------- #
echo "Starting Exponential Simulation"
cd /root/rendezmix/tor
git pull
./autogen.sh
./configure --disable-asciidoc --disable-unittests
make
make install

cd /part/simulation
rm -rf sim_300_2_e/shadow.data sim_300_2_e/shadow.log
tornettools simulate sim_300_2_e
zip -r Exponential_sim.zip sim_300_2_e

cd /part/simulation/datasets/
python3 stage.py -s ../sim_300_2_e
python3 parse.py -s ../sim_300_2_e -o Exponential
python3 cleanup.py -d Exponential
rm -rf /part/simulation/sim_300_2_e/shadow.data /part/simulation/sim_300_2_e/shadow.log
zip -r Exponential_dataset.zip Exponential
rm -rf Exponential
echo "Done!"