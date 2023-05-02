export CC=gcc
export CONTAINER=ubuntu:20.04
export BUILDTYPE=release

ln -s /shared/id_ed25519 ~/.ssh/id_ed25519
ln -s /shared/id_ed25519.pub ~/.ssh/id_ed25519.pub

touch ~/.profile

apt update -y
apt upgrade -y
apt install -y dos2unix git vim

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

find . -type f -exec dos2unix {} \;

ci/container_scripts/install_deps.sh

ci/container_scripts/install_extra_deps.sh

export PATH="~/.cargo/bin:$PATH"

ci/container_scripts/build_and_install.sh

export PATH="~/.local/bin:$PATH"

# Install TGen
cd ~
git clone https://github.com/shadow/tgen.git
cd ~/tgen

apt install -y cmake libglib2.0-dev libigraph-dev

mkdir ~/tgen/build
cd ~/tgen/build
cmake .. -DCMAKE_INSTALL_PREFIX=~/.local
make
make install

# Install OnionTrace
cd ~
git clone https://github.com/shadow/oniontrace.git
cd ~/oniontrace/

apt install -y cmake libglib2.0-0 libglib2.0-dev

mkdir ~/oniontrace/build
cd ~/oniontrace/build
cmake .. -DCMAKE_INSTALL_PREFIX=~/.local
make
make install

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
apt install -y python3 python3-pip
pip install -r requirements.txt

# Setup tornettools

cd ~
git clone https://github.com/shadow/tornettools.git

cd ~/tornettools
pip install -r requirements.txt
pip install --ignore-installed .

apt install -y faketime dstat procps xz-utils wget

mkdir ~/tntdata
cd ~/tntdata

wget https://collector.torproject.org/archive/relay-descriptors/consensuses/consensuses-2020-11.tar.xz
wget https://collector.torproject.org/archive/relay-descriptors/server-descriptors/server-descriptors-2020-11.tar.xz
wget https://metrics.torproject.org/userstats-relay-country.csv
wget https://collector.torproject.org/archive/onionperf/onionperf-2020-11.tar.xz
wget -O bandwidth-2020-11.csv "https://metrics.torproject.org/bandwidth.csv?start=2020-11-01&end=2020-11-30"

tar xafv consensuses-2020-11.tar.xz
tar xafv server-descriptors-2020-11.tar.xz
tar xafv onionperf-2020-11.tar.xz

git clone https://github.com/tmodel-ccs2018/tmodel-ccs2018.github.io.git

export PATH="$PATH:~/rendezmix/tor/src/core/or:~/rendezmix/tor/src/app:~/rendezmix/tor/src/tools"
echo "export PATH=\"\$PATH:~/rendezmix/tor/src/core/or:~/rendezmix/tor/src/app:~/rendezmix/tor/src/tools\"" | tee -a ~/.profile

cd ~