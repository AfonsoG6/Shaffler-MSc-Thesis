sudo apt update -y
sudo apt upgrade -y
sudo apt install -y dos2unix git vim

# Install Shadow
cd ~
git clone https://github.com/shadow/shadow.git
cd ~/shadow

find . -type f -exec dos2unix {} \;

ci/container_scripts/install_deps.sh

ci/container_scripts/install_extra_deps.sh

export PATH="~/.cargo/bin:${PATH}"

ci/container_scripts/build_and_install.sh

export PATH="~/.local/bin:${PATH}"

# Install TGen
cd ~
git clone https://github.com/shadow/tgen.git
cd ~/tgen

sudo apt install -y cmake libglib2.0-dev libigraph-dev

mkdir ~/tgen/build
cd ~/tgen/build
cmake .. -DCMAKE_INSTALL_PREFIX=~/.local
make
make install

# Install OnionTrace
cd ~
git clone https://github.com/shadow/oniontrace.git
cd ~/oniontrace/

sudo apt install -y cmake libglib2.0-0 libglib2.0-dev

mkdir ~/oniontrace/build
cd ~/oniontrace/build
cmake .. -DCMAKE_INSTALL_PREFIX=~/.local
make
make install

# Intall Rendezmix (Tor)
sudo apt install -y openssl libssl-dev libevent-dev build-essential automake zlib1g zlib1g-dev

cd ~
git clone git@github.com:AfonsoG6/rendezmix.git
cd ~/rendezmix

chmod 777 -R .

cd ~/rendezmix/tor
./autogen.sh
./configure --disable-asciidoc
make
make install

cd ~/simulation
find . -type f -exec dos2unix {} \;

cd ~/rendezmix/loop
sudo apt install -y python3
pip install -r requirements.txt

# Setup tornettools

cd ~
git clone https://github.com/shadow/tornettools.git

cd ~/tornettools
pip install -r requirements.txt
pip install --ignore-installed .

sudo apt install -y faketime dstat procps xz-utils wget

mkdir ~/tntdata
cd ~/tntdata

wget https://collector.torproject.org/archive/relay-descriptors/consensuses/consensuses-2020-11.tar.xz
wget https://collector.torproject.org/archive/relay-descriptors/server-descriptors/server-descriptors-2020-11.tar.xz
wget https://metrics.torproject.org/userstats-relay-country.csv
wget https://collector.torproject.org/archive/onionperf/onionperf-2020-11.tar.xz
wget -O bandwidth-2020-11.csv "https://metrics.torproject.org/bandwidth.csv?start=2020-11-01&end=2020-11-30"

tar xaf consensuses-2020-11.tar.xz
tar xaf server-descriptors-2020-11.tar.xz
tar xaf onionperf-2020-11.tar.xz

git clone https://github.com/tmodel-ccs2018/tmodel-ccs2018.github.io.git

export PATH="${PATH}:~/rendezmix/tor/src/core/or:~/rendezmix/tor/src/app:~/rendezmix/tor/src/tools"

cd ~