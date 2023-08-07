clients=$1
duration=$2
if [ -z "$clients" ] || [ -z "$duration" ];
then
    echo "Usage: ./prepare.sh <clients> <duration>"
    echo "Recommended for traffic modulation: 300 2"
    echo "Recommended for cover traffic: 200 2"
    exit 1
fi

if [[ ! $clients =~ ^[+-]?[0-9]+$ ]];
then
    echo "Number of clients is not an integer"
    exit 1
fi
if [[ ! $duration =~ ^[+-]?[0-9]+$ ]] && [[ ! $duration =~ ^[+-]?[0-9]+\.?[0-9]*$ ]];
then
    echo "Duration is not a number"
    exit 1
fi

cd /root/rendezmix
git reset --hard HEAD
git checkout master
git pull
cp -r /root/rendezmix/simulation /part

# Generate the simulation configuration files
cd /part/simulation/data
tornettools stage consensuses-2023-04 server-descriptors-2023-04 userstats-relay-country.csv tmodel-ccs2018.github.io --onionperf_data_path onionperf-2023-04 --bandwidth_data_path bandwidth-2023-04.csv --geoip_path /root/tor/src/config/geoip
cd /part/simulation
tornettools generate data/relayinfo_staging_2023-04-01--2023-04-30.json data/userinfo_staging_2023-04-01--2023-04-30.json data/networkinfo_staging.gml data/tmodel-ccs2018.github.io -r -e BW,CIRC,STREAM --server_scale 0.5 --network_scale 0.005 --prefix sim_${clients}_${duration}
python3 patch.py -s sim_${clients}_${duration} -c ${clients} -d ${duration}
zip -r sim_${clients}_${duration}.zip sim_${clients}_${duration}