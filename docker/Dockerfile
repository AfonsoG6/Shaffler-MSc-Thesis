FROM ubuntu:20.04

ENV CC gcc
ENV CONTAINER ubuntu:20.04
ENV BUILDTYPE release

RUN apt update -y
RUN apt upgrade -y
RUN apt install -y dos2unix git

# Install Shadow
RUN git clone https://github.com/shadow/shadow.git
WORKDIR /shadow

RUN find . -type f -exec dos2unix {} \;

RUN ci/container_scripts/install_deps.sh

RUN ci/container_scripts/install_extra_deps.sh

ENV PATH "/root/.cargo/bin:${PATH}"

RUN ci/container_scripts/build_and_install.sh

ENV PATH "/root/.local/bin:${PATH}"

WORKDIR /

# Install TGen
RUN git clone https://github.com/shadow/tgen.git

RUN apt install -y cmake libglib2.0-dev libigraph-dev

RUN mkdir tgen/build
WORKDIR /tgen/build
RUN cmake .. -DCMAKE_INSTALL_PREFIX=/root/.local
RUN make
RUN make install

WORKDIR /

# Intall Rendezmix (Tor)
RUN apt install -y openssl libssl-dev libevent-dev build-essential automake zlib1g zlib1g-dev

COPY ./.ssh /root/.ssh
RUN chmod 600 /root/.ssh/*
# GIT_SSH_COMMAND="ssh -vvv"
ADD "https://www.random.org/cgi-bin/randbyte?nbytes=10&format=h" skipcache
RUN git clone git@github.com:AfonsoG6/rendezmix.git

WORKDIR /rendezmix
RUN git checkout cellcmd
RUN chmod 777 -R .

RUN ./autogen.sh
RUN ./configure --disable-asciidoc
RUN make
RUN make install

COPY ./simulation /simulation

WORKDIR /simulation
RUN find . -type f -exec dos2unix {} \;
