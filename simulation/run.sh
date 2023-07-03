cd /root/rendezmix
git reset --hard HEAD
git checkout master
git pull
cp -r /root/rendezmix/simulation /part

# Generate the simulation configuration files
cd /part/simulation/data
tornettools stage consensuses-2023-04 server-descriptors-2023-04 userstats-relay-country.csv tmodel-ccs2018.github.io --onionperf_data_path onionperf-2023-04 --bandwidth_data_path bandwidth-2023-04.csv --geoip_path ~/tor/src/config/geoip
cd /part/simulation
tornettools generate data/relayinfo_staging_2023-04-01--2023-04-30.json data/userinfo_staging_2023-04-01--2023-04-30.json data/networkinfo_staging.gml data/tmodel-ccs2018.github.io -r -e BW,CIRC,STREAM --server_scale 0.5 --network_scale 0.005 --prefix sim_300_4
python3 patch.py -s sim_300_4 -c 300 -d 4
zip -r sim_300_4.zip sim_300_4

# Create a copy of the simulation for the normal simulation
cp -r sim_300_4 ./sim_300_4_n
echo "DelayMode 2" >> sim_300_4_n/conf/tor.client.torrc

# ----------------------- VANILLA SIMULATION ----------------------- #
echo "Starting Vanilla Simulation"
cd /root/tor
make
make install

cd /part/simulation
tornettools simulate sim_300_4
zip -r Vanilla_sim.zip sim_300_4

cd /part/simulation/datasets/
python3 stage.py -s ../sim_300_4
python3 parse.py -s ../sim_300_4 -o Vanilla
python3 cleanup.py -d Vanilla
zip -r Vanilla_dataset.zip Vanilla
rm -rf Vanilla

# ----------------------- NORMAL SIMULATION ----------------------- #
echo "Starting Normal Simulation"
cd /root/rendezmix/tor
./autogen.sh
./configure --disable-asciidoc --disable-unittests
make
make install

cd /part/simulation
tornettools simulate sim_300_4_n
zip -r Normal_sim.zip sim_300_4_n

cd /part/simulation/datasets/
python3 stage.py -s ../sim_300_4_n
python3 parse.py -s ../sim_300_4_n -o Normal
python3 cleanup.py -d Normal
zip -r Normal_dataset.zip Normal
rm -rf Normal
echo "Done!"