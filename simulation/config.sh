name=$1
if [ -z "$name" ];
then
    echo "Usage: ./sim.sh <name>"
    exit 1
fi

mode=$(echo $name | cut -d'#' -f 1)
arg1=$(echo $name | cut -d'#' -f 2)
arg2=$(echo $name | cut -d'#' -f 3)
arg3=$(echo $name | cut -d'#' -f 4)

# Conver mode name to its number
if [ "$mode" = "Uniform" ];
then
    mode=2
    num_args=3
    param1=$arg1
    param2=$arg2
    max=$arg3
elif [ "$mode" = "Normal" ];
then
    mode=3
    num_args=3
    param1=$arg1
    param2=$arg2
    max=$arg3
elif [ "$mode" = "Lognormal" ];
then
    mode=4
    num_args=3
    param1=$arg1
    param2=$arg2
    max=$arg3
elif [ "$mode" = "Exponential" ];
then
    mode=5
    num_args=2
    param1=$arg1
    param2=0
    max=$arg2
elif [ "$mode" = "Poisson" ];
then
    mode=6
    num_args=2
    param1=$arg1
    param2=0
    max=$arg2
elif [ "$mode" = "Markov" ];
then
    mode=7
    num_args=1
    param1=0
    param2=0
    max=$arg1
elif [ "$mode" = "Vanilla" ] || [ -z "$mode" ];
then
    cp -r sim_300_2 ./sim_300_2_Vanilla
    exit 0
else
    echo "Mode is not valid"
    exit 1
fi

# Check if param1 and param2 are int or float, exit if not
if [[ $num_args -gt 1 ]] && [[ ! $param1 =~ ^[+-]?[0-9]+$ ]] && [[ ! $param1 =~ ^[+-]?[0-9]+\.?[0-9]*$ ]];
then
    echo "Param1 is not a number"
    exit 1
fi
if [[ $num_args -gt 2 ]] && [[ ! $param2 =~ ^[+-]?[0-9]+$ ]] && [[ ! $param2 =~ ^[+-]?[0-9]+\.?[0-9]*$ ]];
then
    echo "Param2 is not a number"
    exit 1
fi

# If max is blank, set it to 100, otherwise check if it is int or float, exit if not
if [ -z "$max" ];
then
    max=100
elif [[ ! $max =~ ^[+-]?[0-9]+$ ]] && [[ ! $max =~ ^[+-]?[0-9]+\.?[0-9]*$ ]];
then
    echo "Max is not a number"
    exit 1
fi

# Create a copy of the simulation
cp -r sim_300_2 ./sim_300_2_${name}
echo "EnforceDelayPolicy 1" >> sim_300_2_${name}/conf/tor.client.torrc
echo "DelayMode ${mode}" >> sim_300_2_${name}/conf/tor.client.torrc
echo "DelayParam1 ${param1}" >> sim_300_2_${name}/conf/tor.client.torrc
echo "DelayParam2 ${param2}" >> sim_300_2_${name}/conf/tor.client.torrc
echo "DelayMax ${max}" >> sim_300_2_${name}/conf/tor.client.torrc
