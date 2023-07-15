cd /root/rendezmix
git reset --hard HEAD
git checkout master
git pull
cp -r /root/rendezmix/simulation /part

# Generate the simulation configuration files
cd /part/simulation/data
tornettools stage consensuses-2023-04 server-descriptors-2023-04 userstats-relay-country.csv tmodel-ccs2018.github.io --onionperf_data_path onionperf-2023-04 --bandwidth_data_path bandwidth-2023-04.csv --geoip_path ~/tor/src/config/geoip
cd /part/simulation
tornettools generate data/relayinfo_staging_2023-04-01--2023-04-30.json data/userinfo_staging_2023-04-01--2023-04-30.json data/networkinfo_staging.gml data/tmodel-ccs2018.github.io -r -e BW,CIRC,STREAM --server_scale 0.5 --network_scale 0.005 --prefix sim_300_2
python3 patch.py -s sim_300_2 -c 300 -d 2 -m
zip -r sim_300_2.zip sim_300_2

# Create a copy of the simulation for the uniform simulation
cp -r sim_300_2 ./sim_300_2_u
echo "EnforceDelayPolicy 1" >> sim_300_2_u/conf/tor.client.torrc
echo "DelayMode 2" >> sim_300_2_u/conf/tor.client.torrc
echo "DelayParam1 0" >> sim_300_2_u/conf/tor.client.torrc
echo "DelayParam2 100" >> sim_300_2_u/conf/tor.client.torrc
echo "DelayMax 100" >> sim_300_2_u/conf/tor.client.torrc

# Create a copy of the simulation for the normal simulation
cp -r sim_300_2 ./sim_300_2_n
echo "EnforceDelayPolicy 1" >> sim_300_2_n/conf/tor.client.torrc
echo "DelayMode 3" >> sim_300_2_n/conf/tor.client.torrc
echo "DelayParam1 50" >> sim_300_2_n/conf/tor.client.torrc
echo "DelayParam2 12" >> sim_300_2_n/conf/tor.client.torrc
echo "DelayMax 100" >> sim_300_2_n/conf/tor.client.torrc

# Create a copy of the simulation for the lognormal simulation
cp -r sim_300_2 ./sim_300_2_l
echo "EnforceDelayPolicy 1" >> sim_300_2_l/conf/tor.client.torrc
echo "DelayMode 4" >> sim_300_2_l/conf/tor.client.torrc
echo "DelayParam1 3.5" >> sim_300_2_l/conf/tor.client.torrc
echo "DelayParam2 0.5" >> sim_300_2_l/conf/tor.client.torrc
echo "DelayMax 100" >> sim_300_2_l/conf/tor.client.torrc

# Create a copy of the simulation for the poisson simulation
cp -r sim_300_2 ./sim_300_2_p
echo "EnforceDelayPolicy 1" >> sim_300_2_p/conf/tor.client.torrc
echo "DelayMode 6" >> sim_300_2_p/conf/tor.client.torrc
echo "DelayParam1 70" >> sim_300_2_p/conf/tor.client.torrc
echo "DelayMax 100" >> sim_300_2_p/conf/tor.client.torrc

# Create a copy of the simulation for the exponential simulation
cp -r sim_300_2 ./sim_300_2_e
echo "EnforceDelayPolicy 1" >> sim_300_2_e/conf/tor.client.torrc
echo "DelayMode 5" >> sim_300_2_e/conf/tor.client.torrc
echo "DelayParam1 30e-3" >> sim_300_2_e/conf/tor.client.torrc
echo "DelayMax 100" >> sim_300_2_e/conf/tor.client.torrc

# Create a copy of the simulation for the markov simulation
cp -r sim_300_2 ./sim_300_2_m
echo "EnforceDelayPolicy 1" >> sim_300_2_m/conf/tor.client.torrc
echo "DelayMode 7" >> sim_300_2_m/conf/tor.client.torrc
echo "DelayMax 100" >> sim_300_2_m/conf/tor.client.torrc