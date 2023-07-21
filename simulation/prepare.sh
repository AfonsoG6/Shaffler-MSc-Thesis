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
python3 patch.py -s sim_300_2 -c 300 -d 2
zip -r sim_300_2.zip sim_300_2

# Create a copy of the simulation for the uniform simulation
cp -r sim_300_2 ./sim_300_2_Uniform#0#100
echo "EnforceDelayPolicy 1" >> sim_300_2_Uniform#0#100/conf/tor.client.torrc
echo "DelayMode 2" >> sim_300_2_Uniform#0#100/conf/tor.client.torrc
echo "DelayParam1 0" >> sim_300_2_Uniform#0#100/conf/tor.client.torrc
echo "DelayParam2 100" >> sim_300_2_Uniform#0#100/conf/tor.client.torrc
echo "DelayMax 100" >> sim_300_2_Uniform#0#100/conf/tor.client.torrc

# Create a copy of the simulation for the normal simulation
cp -r sim_300_2 ./sim_300_2_Normal#50#12
echo "EnforceDelayPolicy 1" >> sim_300_2_Normal#50#12/conf/tor.client.torrc
echo "DelayMode 3" >> sim_300_2_Normal#50#12/conf/tor.client.torrc
echo "DelayParam1 50" >> sim_300_2_Normal#50#12/conf/tor.client.torrc
echo "DelayParam2 12" >> sim_300_2_Normal#50#12/conf/tor.client.torrc
echo "DelayMax 100" >> sim_300_2_Normal#50#12/conf/tor.client.torrc

# Create a copy of the simulation for the normal simulation
cp -r sim_300_2 ./sim_300_2_Normal#25#6
echo "EnforceDelayPolicy 1" >> sim_300_2_Normal#25#6/conf/tor.client.torrc
echo "DelayMode 3" >> sim_300_2_Normal#25#6/conf/tor.client.torrc
echo "DelayParam1 25" >> sim_300_2_Normal#25#6/conf/tor.client.torrc
echo "DelayParam2 6" >> sim_300_2_Normal#25#6/conf/tor.client.torrc
echo "DelayMax 100" >> sim_300_2_Normal#25#6/conf/tor.client.torrc

# Create a copy of the simulation for the normal simulation
cp -r sim_300_2 ./sim_300_2_Normal#25#3
echo "EnforceDelayPolicy 1" >> sim_300_2_Normal#25#3/conf/tor.client.torrc
echo "DelayMode 3" >> sim_300_2_Normal#25#3/conf/tor.client.torrc
echo "DelayParam1 25" >> sim_300_2_Normal#25#3/conf/tor.client.torrc
echo "DelayParam2 3" >> sim_300_2_Normal#25#3/conf/tor.client.torrc
echo "DelayMax 50" >> sim_300_2_Normal#25#3/conf/tor.client.torrc

# Create a copy of the simulation for the normal simulation
cp -r sim_300_2 ./sim_300_2_Normal#50#6
echo "EnforceDelayPolicy 1" >> sim_300_2_Normal#50#6/conf/tor.client.torrc
echo "DelayMode 3" >> sim_300_2_Normal#50#6/conf/tor.client.torrc
echo "DelayParam1 50" >> sim_300_2_Normal#50#6/conf/tor.client.torrc
echo "DelayParam2 6" >> sim_300_2_Normal#50#6/conf/tor.client.torrc
echo "DelayMax 100" >> sim_300_2_Normal#50#6/conf/tor.client.torrc

# Create a copy of the simulation for the normal simulation
cp -r sim_300_2 ./sim_300_2_Normal#75#6
echo "EnforceDelayPolicy 1" >> sim_300_2_Normal#75#6/conf/tor.client.torrc
echo "DelayMode 3" >> sim_300_2_Normal#75#6/conf/tor.client.torrc
echo "DelayParam1 75" >> sim_300_2_Normal#75#6/conf/tor.client.torrc
echo "DelayParam2 6" >> sim_300_2_Normal#75#6/conf/tor.client.torrc
echo "DelayMax 100" >> sim_300_2_Normal#75#6/conf/tor.client.torrc

# Create a copy of the simulation for the lognormal simulation
cp -r sim_300_2 ./sim_300_2_Lognormal#2#0.5
echo "EnforceDelayPolicy 1" >> sim_300_2_Lognormal#2#0.5/conf/tor.client.torrc
echo "DelayMode 4" >> sim_300_2_Lognormal#2#0.5/conf/tor.client.torrc
echo "DelayParam1 2" >> sim_300_2_Lognormal#2#0.5/conf/tor.client.torrc
echo "DelayParam2 0.5" >> sim_300_2_Lognormal#2#0.5/conf/tor.client.torrc
echo "DelayMax 50" >> sim_300_2_Lognormal#2#0.5/conf/tor.client.torrc

# Create a copy of the simulation for the poisson simulation
cp -r sim_300_2 ./sim_300_2_Poisson#70
echo "EnforceDelayPolicy 1" >> sim_300_2_Poisson#70/conf/tor.client.torrc
echo "DelayMode 6" >> sim_300_2_Poisson#70/conf/tor.client.torrc
echo "DelayParam1 70" >> sim_300_2_Poisson#70/conf/tor.client.torrc
echo "DelayMax 100" >> sim_300_2_Poisson#70/conf/tor.client.torrc

# Create a copy of the simulation for the exponential simulation
cp -r sim_300_2 ./sim_300_2_Exponential#30e-3
echo "EnforceDelayPolicy 1" >> sim_300_2_Exponential#30e-3/conf/tor.client.torrc
echo "DelayMode 5" >> sim_300_2_Exponential#30e-3/conf/tor.client.torrc
echo "DelayParam1 30e-3" >> sim_300_2_Exponential#30e-3/conf/tor.client.torrc
echo "DelayMax 100" >> sim_300_2_Exponential#30e-3/conf/tor.client.torrc

# Create a copy of the simulation for the markov simulation
cp -r sim_300_2 ./sim_300_2_Markov
echo "EnforceDelayPolicy 1" >> sim_300_2_Markov/conf/tor.client.torrc
echo "DelayMode 7" >> sim_300_2_Markov/conf/tor.client.torrc
echo "DelayMax 100" >> sim_300_2_Markov/conf/tor.client.torrc