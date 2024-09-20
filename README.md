# Shaffler (MSc Thesis)

## Start Docker container

1. Change to the docker directory: `cd docker`
2. Build the image: `docker-compose build`
3. Start the container: `docker-compose up`
4. Run the container: `docker-compose run rendezmix`

## Prepare base simulation

1. Inside the docker container, change directory to /root/rendezmix/simulation: `cd /root/rendezmix/simulation`
2. Choose the number of clients and duration for the simulation and run the script: `./prepare.sh <number of clients> <duration>`
3. Change directory to /part/simulation and do everything else there: `cd /part/simulation`

## (Optional) Prepare traffic modulation variants

1. (Optional) Change the simulation to the 'One circuit' mode: `python3 repatch.py -s <base sim path> --one-circuit`
2. Choose the distribution to use for the traffic modulation and its parameters:
    - Vanilla()
    - Markov()
    - Uniform(min, max)
    - [Normal(mu, sigma)](https://homepage.divms.uiowa.edu/~mbognar/applets/normal.html)
    - [Lognormal(mu, sigma)](https://homepage.divms.uiowa.edu/~mbognar/applets/lognormal.html)
    - [Poisson(lambda)](https://homepage.divms.uiowa.edu/~mbognar/applets/pois.html)
    - [Exponential(lambda)](https://homepage.divms.uiowa.edu/~mbognar/applets/exp-like.html)
3. Run the config_modul script with the \<choice\> in the format Distribution#Param1#Param2#Max: `./config_modul.sh <base sim path> <choice>`

## (Optional) Prepare cover traffic variants

1. Create duplicate of the config file: `cp <base sim path>/conf/cover-config.json ./variant1.json`
1. Edit the config file: `vim variant1.json`/`nano variant1.json`
2. Run the config_cover script: `./config_cover.sh <base sim path> <name to identify variant> variant1.json`

To create a variant of the same simulation but Vanilla, i.e. with cover traffic disabled, run: `./config_cover.sh <base sim path> Vanilla`

## Run simulation

1. Run the sim script: `./sim.sh <sim_path>`


## Example for two variants of cover traffic + Vanilla

```
cd docker
docker-compose build
docker-compose up
docker-compose run rendezmix
```

Then inside the container:

```
cd /root/rendezmix/simulation
./prepare.sh 200 2
cd /part/simulation
./config_cover.sh ./sim_200_2 Vanilla
cp ./sim_200_2/conf/cover-config.json ./Const#1MB#10s.json
cp ./sim_200_2/conf/cover-config.json ./Const#100KB#1s.json
```

Edit the config files to, for example:

- Const#1MB#10s.json:

    ```json
    {
        "app": {
            "bind_address": "127.0.0.1:8000",
            "mode": "Const",
            "size": 1000000,
            "page_name": "page1.html",
            "adjustable": true
        },
        "cclient": {
            "python_path" : "python",
            "rate" : 10000,
            "timeout" : 5000,
            "endpoint" : "/",
            "fail_limit" : -1
        }
    }
    ```

- Const#100KB#1s.json:

    ```json
    {
        "app": {
            "bind_address": "127.0.0.1:8000",
            "mode": "Const",
            "size": 1000,
            "page_name": "page1.html",
            "adjustable": true
        },
        "cclient": {
            "python_path" : "python",
            "rate" : 1000,
            "timeout" : 5000,
            "endpoint" : "/",
            "fail_limit" : -1
        }
    }
    ```

After editing the config files:

```
./config_cover.sh ./sim_200_2 Const#1MB#10s ./Const#1MB#10s.json
./config_cover.sh ./sim_200_2 Const#100KB#1s ./Const#100KB#1s.json
./sim.sh ./sim_200_2_Vanilla
./sim.sh ./sim_200_2_Const#1MB#10s
./sim.sh ./sim_200_2_Const#100KB#1s
```

To deattach from the container without stopping it, press `Ctrl + P` and `Ctrl + Q` in sequence.

After it is done, retrieve the files `Vanilla.zip`, `Const#1MB#10s.zip` and `Const#100KB#1s.zip` from the container to the NAS:

```sh
docker cp $(docker container list | grep "rendezmix.*Up" | awk '{print $1}'):/part/simulation/Vanilla.zip .
docker cp $(docker container list | grep "rendezmix.*Up" | awk '{print $1}'):/part/simulation/Const#1MB#10s.zip .
docker cp $(docker container list | grep "rendezmix.*Up" | awk '{print $1}'):/part/simulation/Const#100KB#1s.zip .
```

To re-attach the terminal to the docker container

```sh
docker attach $(docker container list | grep "rendezmix.*Up" | awk '{print $1}')
```
