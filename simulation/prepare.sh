cd /root/rendezmix
git reset --hard HEAD
git checkout cover
git pull
cp -r /root/rendezmix/simulation /part/cover
cd /part/cover

# Generate the simulation configuration files
cd /part/cover
cp -r /part/simulation/data .
tornettools generate data/relayinfo_staging_2023-04-01--2023-04-30.json data/userinfo_staging_2023-04-01--2023-04-30.json data/networkinfo_staging.gml data/tmodel-ccs2018.github.io -r -e BW,CIRC,STREAM --server_scale 0.5 --network_scale 0.005 --prefix sim_300_2
python3 patch.py -s sim_300_2 -c 50 -d 2