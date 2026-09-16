FROM debian:13-slim

# Install required packages
RUN apt-get update && \
    apt-get install -y \
        openssh-server \
        sudo \
        bash \
        procps \
        iproute2 \
        net-tools \
    && rm -rf /var/lib/apt/lists/*

# SSH runtime directory
RUN mkdir -p /run/sshd

# Create CTF user
RUN useradd -m -s /bin/bash player && \
    echo 'player:player123' | chpasswd

# Create persistent directories
RUN mkdir -p /opt/ctf /var/log/ctf && \
    chown -R player:player /opt/ctf

# SSH configuration
RUN sed -i \
    -e 's/#PasswordAuthentication yes/PasswordAuthentication yes/' \
    -e 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' \
    /etc/ssh/sshd_config

RUN sed -i 's/^#Port 22/Port 2222/' /etc/ssh/sshd_config

EXPOSE 2222

CMD ["/usr/sbin/sshd", "-D", "-e","-p","2222"]
