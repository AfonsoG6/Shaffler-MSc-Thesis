sim=$1
name=$2
config=$3
if [ -z "$sim" ] || [ -z "$name" ];
then
    echo "Usage: ./config_cover.sh <sim> <name> (config)"
    exit 1
fi

sim_name=$(basename $sim)
name=$(basename $name)

if [ "$name" = "Vanilla" ];
then
    cp -r ${sim} ./${sim_name}_${name}
    python3 ./repatch.py --cover-off -s ./${sim_name}_${name}
    exit 0
fi

if [ -z "$config" ];
then
    echo "When creating a non-vanilla simulation, a config file must be specified."
    echo "Usage: ./config.sh ${sim} ${name} <config>"
    exit 1
fi

cp -r ${sim} ./${sim_name}_${name}
python3 ./repatch.py --cover-on -s ./${sim_name}_${name} --config ${config}