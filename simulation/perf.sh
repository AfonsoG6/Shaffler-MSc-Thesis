# Create a list of modes
modes="Uniform Normal Lognormal Exponential Poisson Markov"
for mode in $modes
do
    vanilla_sim=$(find . -maxdepth 1 -type d -name "sim_*_*_Vanilla")
    sims="$vanilla_sim"
    names="Vanilla"

    # Find all directories with the name sim_*_*_$mode
    for sim in $(find . -maxdepth 1 -type d -name "sim_*_*_$mode*")
    do
        # Extract name of simulation
        sims="$sims $sim"
        names="$names $(echo $sim | cut -d'_' -f4)"
    done

    # Plot the results
    if [ ${#names} -lt 2 ]
    then
        echo "No simulations found for mode $mode"
        continue
    fi

    echo "Plotting for mode $mode"
    tornettools plot ${sims} -a --pngs --prefix ${mode}_perf -l ${names}
done

