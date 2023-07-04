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
echo "EnforceDelayPolicy 1" >> sim_300_4_n/conf/tor.client.torrc
echo "DelayMode 3" >> sim_300_4_n/conf/tor.client.torrc
echo "DelayParam1 0.5e5" >> sim_300_4_n/conf/tor.client.torrc
echo "DelayParam2 0.12e5" >> sim_300_4_n/conf/tor.client.torrc
echo "DelayMax 1e5" >> sim_300_4_n/conf/tor.client.torrc