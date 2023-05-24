export CC=gcc
export CONTAINER=ubuntu:20.04
export BUILDTYPE=release

cp /vagrant/.ssh/id_ed25519 ~/.ssh
cp /vagrant/.ssh/id_ed25519.pub ~/.ssh
cp /vagrant/.ssh/id_ed25519 /root/.ssh
cp /vagrant/.ssh/id_ed25519.pub /root/.ssh
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub
chmod 600 /root/.ssh/id_ed25519
chmod 644 /root/.ssh/id_ed25519.pub

touch ~/.profile

apt update -y
apt upgrade -y
apt install -y dos2unix git vim
apt install -y python3 python3-pip

sysctl -w fs.nr_open=10485760
echo "fs.nr_open = 10485760" | tee -a /etc/sysctl.conf
sysctl -w fs.file-max=10485760
echo "fs.file-max = 10485760" | tee -a /etc/sysctl.conf
sysctl -p

sed -i 's/# End of file//g' /etc/security/limits.conf
echo "vagrant soft nofile 10485760" | tee -a /etc/security/limits.conf
echo "vagrant hard nofile 10485760" | tee -a /etc/security/limits.conf
echo "vagrant soft nproc unlimited" | tee -a /etc/security/limits.conf
echo "vagrant hard nproc unlimited" | tee -a /etc/security/limits.conf
echo "# End of file" | tee -a /etc/security/limits.conf

systemctl set-property user-$UID.slice TasksMax=infinity

sysctl -w vm.max_map_count=1073741824
echo "vm.max_map_count = 1073741824" | tee -a /etc/sysctl.conf
sysctl -p

sysctl -w kernel.pid_max=4194304
echo "kernel.pid_max = 4194304" | tee -a /etc/sysctl.conf
sysctl -p

sysctl -w kernel.threads-max=4194304
echo "kernel.threads-max = 4194304" | tee -a /etc/sysctl.conf
sysctl -p

# Install Shadow
cd ~
git clone https://github.com/shadow/shadow.git
cd ~/shadow
git checkout 5380a99b09cd25c5f93cac183c7f65bd706acbb7

find . -type f -exec dos2unix {} \;

ci/container_scripts/install_deps.sh

ci/container_scripts/install_extra_deps.sh

export PATH="$PATH:~/.cargo/bin"
echo "export PATH=\"\$PATH:~/.cargo/bin\"" | tee -a ~/.profile

source "$HOME/.cargo/env"
echo "source \"\$HOME/.cargo/env\"" | tee -a ~/.profile

ci/container_scripts/build_and_install.sh

export PATH="$PATH:~/.local/bin"

# Install TGen
cd ~
git clone https://github.com/shadow/tgen.git
cd ~/tgen
git checkout 30c95bbe723ebe5e4d068adfd975b094e00dbe10

apt install -y cmake libglib2.0-dev libigraph-dev

mkdir ~/tgen/build
cd ~/tgen/build
cmake .. -DCMAKE_INSTALL_PREFIX=~/.local
make
make install

pip install -r ~/tgen/tools/requirements.txt
pip install -I ~/tgen/tools

# Install OnionTrace
cd ~
git clone https://github.com/shadow/oniontrace.git
cd ~/oniontrace/
git checkout 3696db43288c8a116e8a1cff42a9c698d1d4ab33

apt install -y cmake libglib2.0-0 libglib2.0-dev

mkdir ~/oniontrace/build
cd ~/oniontrace/build
cmake .. -DCMAKE_INSTALL_PREFIX=~/.local
make
make install

pip install -r ~/oniontrace/tools/requirements.txt
pip install -I ~/oniontrace/tools

# Intall Rendezmix (Tor)
apt install -y openssl libssl-dev libevent-dev build-essential automake zlib1g zlib1g-dev

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
pip install -r requirements.txt

ln -s $(which tor) ~/.local/bin/tor

# Setup tornettools

cd ~
git clone https://github.com/shadow/tornettools.git
cd ~/tornettools
git checkout c0f2d5e28e6d6e005a559769c18fb4bff3d4ee8c

pip install -r requirements.txt
pip install --ignore-installed .

apt install -y faketime dstat procps xz-utils wget

mkdir -p ~/rendezmix/simulation/data
cd ~/rendezmix/simulation/data

chmod 777 -R .

wget https://collector.torproject.org/archive/relay-descriptors/consensuses/consensuses-2023-04.tar.xz
wget https://collector.torproject.org/archive/relay-descriptors/server-descriptors/server-descriptors-2023-04.tar.xz
wget https://metrics.torproject.org/userstats-relay-country.csv
wget https://collector.torproject.org/archive/onionperf/onionperf-2023-04.tar.xz
wget -O bandwidth-2023-04.csv "https://metrics.torproject.org/bandwidth.csv?start=2023-04-01&end=2023-04-30"

tar xafv consensuses-2023-04.tar.xz
tar xafv server-descriptors-2023-04.tar.xz
tar xafv onionperf-2023-04.tar.xz

git clone https://github.com/tmodel-ccs2018/tmodel-ccs2018.github.io.git

export PATH="$PATH:~/tor/src/core/or:~/tor/src/app:~/tor/src/tools"
echo "export PATH=\"\$PATH:~/tor/src/core/or:~/tor/src/app:~/tor/src/tools\"" | tee -a ~/.profile

alias stage="cd ~/rendezmix/simulation/data; tornettools stage \
consensuses-2023-04 \
server-descriptors-2023-04 \
userstats-relay-country.csv \
tmodel-ccs2018.github.io \
--onionperf_data_path onionperf-2023-04 \
--bandwidth_data_path bandwidth-2023-04.csv \
--geoip_path ~/rendezmix/tor/src/config/geoip"

echo "alias stage=\"cd ~/rendezmix/simulation/data; tornettools stage \
consensuses-2023-04 \
server-descriptors-2023-04 \
userstats-relay-country.csv \
tmodel-ccs2018.github.io \
--onionperf_data_path onionperf-2023-04 \
--bandwidth_data_path bandwidth-2023-04.csv \
--geoip_path ~/rendezmix/tor/src/config/geoip\"" | tee -a ~/.profile

alias generate="cd ~/rendezmix/simulation; tornettools generate \
data/relayinfo_staging_2023-04-01--2023-04-30.json \
data/userinfo_staging_2023-04-01--2023-04-30.json \
data/networkinfo_staging.gml \
data/tmodel-ccs2018.github.io \
-r -e BW,CIRC,STREAM \
--network_scale 0.01 \
--prefix tornet-0.01"

echo "alias generate=\"cd ~/rendezmix/simulation; tornettools generate \
data/relayinfo_staging_2023-04-01--2023-04-30.json \
data/userinfo_staging_2023-04-01--2023-04-30.json \
data/networkinfo_staging.gml \
data/tmodel-ccs2018.github.io \
-r -e BW,CIRC,STREAM \
--network_scale 0.01 \
--prefix tornet-0.01\"" | tee -a ~/.profile

alias simulate="cd ~/rendezmix/simulation; tornettools simulate tornet-0.01"

echo "alias simulate=\"cd ~/rendezmix/simulation; tornettools simulate tornet-0.01\"" | tee -a ~/.profile

alias parse="cd ~/rendezmix/simulation; tornettools parse tornet-0.01"

echo "alias parse=\"cd ~/rendezmix/simulation; tornettools parse tornet-0.01\"" | tee -a ~/.profile

alias plot="cd ~/rendezmix/simulation; tornettools plot \
tornet-0.01 \
--tor_metrics_path data/tor_metrics_2023-04-01--2023-04-30.json \
--prefix pdfs"

echo "alias plot=\"cd ~/rendezmix/simulation; tornettools plot \
tornet-0.01 \
--tor_metrics_path data/tor_metrics_2023-04-01--2023-04-30.json \
--prefix pdfs\"" | tee -a ~/.profile

alias archive="cd ~/rendezmix/simulation; tornettools archive tornet-0.01"

echo "alias archive=\"cd ~/rendezmix/simulation; tornettools archive tornet-0.01\"" | tee -a ~/.profile

cd ~