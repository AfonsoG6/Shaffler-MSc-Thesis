# ----------------------- NORMAL SIMULATION ----------------------- #
echo "Starting Lognormal Simulation"
cd /root/rendezmix/tor
git pull
./autogen.sh
./configure --disable-asciidoc --disable-unittests
make
make install

cd /part/simulation
rm -rf sim_300_2_l/shadow.data sim_300_2_l/shadow.log
tornettools simulate sim_300_2_l
zip -r Lognormal_sim.zip sim_300_2_l

cd /part/simulation/datasets/
python3 stage.py -s ../sim_300_2_l
python3 parse.py -s ../sim_300_2_l -o Lognormal
python3 cleanup.py -d Lognormal
rm -rf /part/simulation/sim_300_2_l/shadow.data /part/simulation/sim_300_2_l/shadow.log
zip -r Lognormal_dataset.zip Lognormal
rm -rf Lognormal
echo "Done!"