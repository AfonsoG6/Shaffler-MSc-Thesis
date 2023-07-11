# ----------------------- NORMAL SIMULATION ----------------------- #
echo "Starting Markov Simulation"
cd /root/rendezmix/tor
git pull
./autogen.sh
./configure --disable-asciidoc --disable-unittests
make
make install

cd /part/simulation
rm -rf sim_300_2_e/shadow.data sim_300_2_e/shadow.log
tornettools simulate sim_300_2_e
zip -r Markov_sim.zip sim_300_2_e

cd /part/simulation/datasets/
python3 stage.py -s ../sim_300_2_e
python3 parse.py -s ../sim_300_2_e -o Markov
python3 cleanup.py -d Markov
rm -rf /part/simulation/sim_300_2_e/shadow.data /part/simulation/sim_300_2_e/shadow.log
zip -r Markov_dataset.zip Markov
rm -rf Markov
echo "Done!"