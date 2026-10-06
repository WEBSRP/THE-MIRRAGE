FROM debian:13-slim

RUN apt-get update && \
    apt-get install -y \
        nginx \
        openssh-server \
        sudo \
        bash \
        procps \
        iproute2 \
        iputils-ping \
        curl \
        nano \
        netcat-openbsd \
        ca-certificates \
        python3  \
        cron && \
    rm -rf /var/lib/apt/lists/*

#ctf user
RUN useradd -m -s /bin/bash player 


#SSH configuration
RUN mkdir -p /run/sshd && \
    echo 'player:player123' | chpasswd && \
    sed -i \
        -e 's/#PasswordAuthentication yes/PasswordAuthentication yes/' \
        -e 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' \
        /etc/ssh/sshd_config

# CTF directories
RUN mkdir -p /opt/ctf/backend /var/www/html /home/player

COPY nginx/default /etc/nginx/sites-available/default
RUN ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

COPY web/ /var/www/html/
COPY backend/ /opt/ctf/backend/

RUN chown -R www-data:www-data /var/www/html /opt/ctf/backend && \
    chmod +x /opt/ctf/backend/server.py && \
    chown -R player:player /home/player

#HTTP
EXPOSE 80

#SSH
EXPOSE 22

RUN echo "MIRRAGE{web_test_flag}" > /var/www/html/flag.txt && \
    echo "MIRRAGE{user_test_flag}" > /home/player/flag.txt && \
    echo "MIRRAGE{root_test_flag}" > /root/flag.txt && \
    chown www-data:www-data /var/www/html/flag.txt && \
    chown player:player /home/player/flag.txt && \
    chown root:root /root/flag.txt && \
    chmod 600 /var/www/html/flag.txt && \
    chmod 600 /home/player/flag.txt && \
    chmod 600 /root/flag.txt

#player and www-data maintenance group
RUN groupadd maintenance && \
    usermod -aG maintenance player && \
    usermod -aG maintenance www-data

# The intended exploitable script
RUN mkdir -p /opt/mirrage

COPY challenge/maintenance.sh /opt/mirrage/maintenance.sh

RUN chown player:maintenance /opt/mirrage/maintenance.sh && \
    chmod 775 /opt/mirrage/maintenance.sh

# Cron job creation
RUN cat > /etc/cron.d/mirrage-maintenance <<'EOF'
*/1 * * * * player /opt/mirrage/maintenance.sh >> /var/log/mirrage-maintenance.log 2>&1
EOF

RUN touch /var/log/mirrage-maintenance.log && \
    chown player:player /var/log/mirrage-maintenance.log



CMD ["/bin/bash", "-c", "cron; /usr/sbin/sshd; sudo -u www-data python3 -u /opt/ctf/backend/server.py & nginx; exec tail -f /dev/null"]