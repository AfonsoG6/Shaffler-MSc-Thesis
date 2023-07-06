# ----------------------- NORMAL SIMULATION ----------------------- #
echo "Starting Uniform Simulation"
cd /root/rendezmix/tor
git pull
./autogen.sh
./configure --disable-asciidoc --disable-unittests
make
make install

cd /part/simulation
rm -rf sim_300_2_u/shadow.data sim_300_2_u/shadow.log
tornettools simulate sim_300_2_u
zip -r Uniform_sim.zip sim_300_2_u

cd /part/simulation/datasets/
python3 stage.py -s ../sim_300_2_u
python3 parse.py -s ../sim_300_2_u -o Uniform
python3 cleanup.py -d Uniform
rm -rf sim_300_2_u/shadow.data sim_300_2_u/shadow.log
zip -r Uniform_dataset.zip Uniform
rm -rf Uniform
echo "Done!"