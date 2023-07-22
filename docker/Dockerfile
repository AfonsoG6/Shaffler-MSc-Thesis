FROM ubuntu:20.04

ENV CC gcc
ENV CONTAINER ubuntu:20.04
ENV BUILDTYPE release

RUN apt update -y
RUN apt upgrade -y
RUN apt install -y dos2unix git vim

# Install Shadow
WORKDIR /root
RUN git clone https://github.com/shadow/shadow.git
WORKDIR /root/shadow
RUN git checkout tags/v3.0.0

RUN find . -type f -exec dos2unix {} \;

RUN ci/container_scripts/install_deps.sh

RUN ci/container_scripts/install_extra_deps.sh

ENV PATH "/root/.cargo/bin:${PATH}"

RUN ci/container_scripts/build_and_install.sh

ENV PATH "/root/.local/bin:${PATH}"


# Install TGen
WORKDIR /root
RUN git clone https://github.com/shadow/tgen.git
WORKDIR /root/tgen

RUN apt install -y cmake libglib2.0-dev libigraph-dev

RUN mkdir /root/tgen/build
WORKDIR /root/tgen/build
RUN cmake .. -DCMAKE_INSTALL_PREFIX=/root/.local
RUN make
RUN make install

WORKDIR /root/tgen/tools
RUN apt install -y python3 python3-dev python3-pip libxml2 libxml2-dev libxslt1.1 libxslt1-dev libpng16-16 libpng-dev libfreetype6 libfreetype6-dev libblas-dev liblapack-dev
RUN pip install -r requirements.txt
RUN pip install -I .

# Install OnionTrace
WORKDIR /root
RUN git clone https://github.com/shadow/oniontrace.git
WORKDIR /root/oniontrace/

RUN apt install -y cmake libglib2.0-0 libglib2.0-dev

RUN mkdir /root/oniontrace/build
WORKDIR /root/oniontrace/build
RUN cmake .. -DCMAKE_INSTALL_PREFIX=/root/.local
RUN make
RUN make install

WORKDIR /root/oniontrace/tools
RUN apt install -y python3 python3-dev python3-pip libxml2 libxml2-dev libxslt1.1 libxslt1-dev libpng16-16 libpng16-16 libfreetype6 libfreetype6-dev libblas-dev liblapack-dev
RUN pip install -r requirements.txt
RUN pip install -I .

# Install Rendezmix (Tor)
RUN apt install -y openssl libssl-dev libevent-dev build-essential automake zlib1g zlib1g-dev

# Uncomment next line to force everything from here onwards to be rebuilt
# ADD "https://www.random.org/cgi-bin/randbyte?nbytes=10&format=h" skipcache
COPY ./.ssh /root/.ssh
RUN dos2unix /root/.ssh/*
RUN chmod 600 /root/.ssh/*
RUN chmod 644 /root/.ssh/*.pub

WORKDIR /root
RUN git clone git@github.com:AfonsoG6/rendezmix.git
WORKDIR /root/rendezmix

RUN chmod 777 -R .

WORKDIR /root/rendezmix/tor
RUN ./autogen.sh
RUN ./configure --disable-asciidoc --disable-unittests
RUN make
RUN make install

WORKDIR /root/rendezmix/simulation/datasets
RUN pip install -r requirements.txt

# Install Vanilla Tor
WORKDIR /root
RUN git clone git@github.com:torproject/tor.git
WORKDIR /root/tor
RUN git checkout tags/tor-0.4.7.13

RUN chmod 777 -R .

RUN ./autogen.sh
RUN ./configure --disable-asciidoc
RUN make
#RUN make install

RUN ln -s $(which tor) ~/.local/bin/tor

# Setup tornettools

WORKDIR /root
RUN git clone https://github.com/shadow/tornettools.git

WORKDIR /root/tornettools
RUN pip install -r requirements.txt
RUN pip install --ignore-installed .

RUN apt install -y faketime dstat procps xz-utils wget

RUN mkdir /root/rendezmix/simulation/data
WORKDIR /root/rendezmix/simulation/data

RUN chmod 777 -R .

RUN wget https://collector.torproject.org/archive/relay-descriptors/consensuses/consensuses-2023-04.tar.xz
RUN wget https://collector.torproject.org/archive/relay-descriptors/server-descriptors/server-descriptors-2023-04.tar.xz
RUN wget https://metrics.torproject.org/userstats-relay-country.csv
RUN wget https://collector.torproject.org/archive/onionperf/onionperf-2023-04.tar.xz
RUN wget -O bandwidth-2023-04.csv "https://metrics.torproject.org/bandwidth.csv?start=2023-04-01&end=2023-04-30"


RUN tar xafv consensuses-2023-04.tar.xz
RUN tar xafv server-descriptors-2023-04.tar.xz
RUN tar xafv onionperf-2023-04.tar.xz

RUN git clone https://github.com/tmodel-ccs2018/tmodel-ccs2018.github.io.git

RUN alias stage="cd /part/simulation/data; tornettools stage \
    consensuses-2023-04 \
    server-descriptors-2023-04 \
    userstats-relay-country.csv \
    tmodel-ccs2018.github.io \
    --onionperf_data_path onionperf-2023-04 \
    --bandwidth_data_path bandwidth-2023-04.csv \
    --geoip_path ~/tor/src/config/geoip"

RUN alias generate="cd /part/simulation; tornettools generate \
    data/relayinfo_staging_2023-04-01--2023-04-30.json \
    data/userinfo_staging_2023-04-01--2023-04-30.json \
    data/networkinfo_staging.gml \
    data/tmodel-ccs2018.github.io \
    -r -e BW,CIRC,STREAM \
    --network_scale 0.005 \
    --torperf_num_exit 0 \
    --prefix tornet-0.005"

RUN alias simulate="cd /part/simulation; tornettools simulate tornet-0.005"

RUN alias parse="cd /part/simulation; tornettools parse tornet-0.005"

RUN alias plot="cd /part/simulation; tornettools plot \
    tornet-0.005 \
    --tor_metrics_path data/tor_metrics_2023-04-01--2023-04-30.json \
    --prefix pdfs"

RUN alias archive="cd /part/simulation; tornettools archive tornet-0.005"


ENV PATH "${PATH}:/root/tor/src/core/or:/root/tor/src/app:/root/tor/src/tools"

WORKDIR /