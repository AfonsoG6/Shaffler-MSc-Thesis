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

# Intall Rendezmix (Tor)
RUN apt install -y openssl libssl-dev libevent-dev build-essential automake zlib1g zlib1g-dev

ADD "https://www.random.org/cgi-bin/randbyte?nbytes=10&format=h" skipcache
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

RUN ln -s /root/rendezmix/simulation /root

WORKDIR /root/simulation
RUN find . -type f -exec dos2unix {} \;

RUN alias sim="/root/simulation/run.sh"

WORKDIR /root/rendezmix/loop
RUN apt install -y python3
RUN pip install -r requirements.txt

WORKDIR /root