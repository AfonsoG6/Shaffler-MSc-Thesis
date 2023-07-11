# ----------------------- NORMAL SIMULATION ----------------------- #
echo "Starting Poisson Simulation"
cd /root/rendezmix/tor
git pull
./autogen.sh
./configure --disable-asciidoc --disable-unittests
make
make install

cd /part/simulation
rm -rf sim_300_2_p/shadow.data sim_300_2_p/shadow.log
tornettools simulate sim_300_2_p
zip -r Poisson_sim.zip sim_300_2_p

cd /part/simulation/datasets/
python3 stage.py -s ../sim_300_2_p
python3 parse.py -s ../sim_300_2_p -o Poisson
python3 cleanup.py -d Poisson
rm -rf /part/simulation/sim_300_2_p/shadow.data /part/simulation/sim_300_2_p/shadow.log
zip -r Poisson_dataset.zip Poisson
rm -rf Poisson
echo "Done!"