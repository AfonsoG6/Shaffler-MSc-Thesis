# ----------------------- VANILLA SIMULATION ----------------------- #
echo "Starting Vanilla Simulation"
cd /root/tor
make
make install

cd /part/simulation
rm -rf sim_300_4/shadow.data sim_300_4/shadow.log
tornettools simulate sim_300_4
zip -r Vanilla_sim.zip sim_300_4

cd /part/simulation/datasets/
python3 stage.py -s ../sim_300_4
python3 parse.py -s ../sim_300_4 -o Vanilla
python3 cleanup.py -d Vanilla
zip -r Vanilla_dataset.zip Vanilla
rm -rf Vanilla
echo "Done!"