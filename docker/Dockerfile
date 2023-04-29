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

# Intall Rendezmix (Tor)
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
RUN ./configure --disable-asciidoc
RUN make
RUN make install

WORKDIR /root/simulation
RUN find . -type f -exec dos2unix {} \;

WORKDIR /root/rendezmix/loop
RUN apt install -y python3
RUN pip install -r requirements.txt

# Setup tornettools

WORKDIR /root
RUN git clone https://github.com/shadow/tornettools.git

WORKDIR /root/tornettools
RUN pip install -r requirements.txt
RUN pip install --ignore-installed .

RUN apt install -y faketime dstat procps xz-utils wget

RUN mkdir /root/tntdata
WORKDIR /root/tntdata

RUN wget https://collector.torproject.org/archive/relay-descriptors/consensuses/consensuses-2020-11.tar.xz
RUN wget https://collector.torproject.org/archive/relay-descriptors/server-descriptors/server-descriptors-2020-11.tar.xz
RUN wget https://metrics.torproject.org/userstats-relay-country.csv
RUN wget https://collector.torproject.org/archive/onionperf/onionperf-2020-11.tar.xz
RUN wget -O bandwidth-2020-11.csv "https://metrics.torproject.org/bandwidth.csv?start=2020-11-01&end=2020-11-30"

RUN tar xaf consensuses-2020-11.tar.xz
RUN tar xaf server-descriptors-2020-11.tar.xz
RUN tar xaf onionperf-2020-11.tar.xz

RUN git clone https://github.com/tmodel-ccs2018/tmodel-ccs2018.github.io.git


ENV PATH "${PATH}:/root/rendezmix/tor/src/core/or:/root/rendezmix/tor/src/app:/root/rendezmix/tor/src/tools"

WORKDIR /root