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

# Create the user
RUN useradd -m -s /bin/bash admin && \
    echo 'admin:admin123' | chpasswd

# Create persistent directories
RUN mkdir -p /opt/mirrage /var/log/mirrage && \
    chown -R admin:admin /opt/mirrage

# SSH configuration
RUN sed -i \
    -e 's/#PasswordAuthentication yes/PasswordAuthentication yes/' \
    -e 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' \
    /etc/ssh/sshd_config

EXPOSE 22

CMD ["/usr/sbin/sshd", "-D", "-e"]
