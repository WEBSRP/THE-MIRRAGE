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
        python3 \
        cron && \
    rm -rf /var/lib/apt/lists/*

# CTF user
RUN useradd -m -s /bin/bash player

# SSH configuration
RUN mkdir -p /run/sshd && \
    echo 'player:player123' | chpasswd && \
    sed -i \
        -e 's/#PasswordAuthentication yes/PasswordAuthentication yes/' \
        -e 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' \
        /etc/ssh/sshd_config

# CTF directories
RUN mkdir -p \
        /opt/ctf/backend \
        /var/www/html \
        /home/player \
        /opt/mirrage

# Nginx configuration
COPY nginx/default /etc/nginx/sites-available/default

RUN ln -sf \
    /etc/nginx/sites-available/default \
    /etc/nginx/sites-enabled/default

# Web interface
COPY web/ /var/www/html/

# Backend
COPY backend/ /opt/ctf/backend/

RUN chown -R www-data:www-data \
        /var/www/html \
        /opt/ctf/backend && \
    chmod +x /opt/ctf/backend/server.py && \
    chown -R player:player /home/player

# HTTP
EXPOSE 80

# SSH
EXPOSE 22

# CTF flags
RUN echo "MIRRAGE{web_test_flag}" > /var/www/html/flag.txt && \
    echo "MIRRAGE{user_test_flag}" > /home/player/flag.txt && \
    echo "MIRRAGE{root_test_flag}" > /root/flag.txt && \
    chown www-data:www-data /var/www/html/flag.txt && \
    chown player:player /home/player/flag.txt && \
    chown root:root /root/flag.txt && \
    chmod 600 /var/www/html/flag.txt && \
    chmod 600 /home/player/flag.txt && \
    chmod 600 /root/flag.txt

# Player and www-data maintenance group
RUN groupadd maintenance && \
    usermod -aG maintenance player && \
    usermod -aG maintenance www-data

# Intended exploitable script
COPY challenge/maintenance.sh /opt/mirrage/maintenance.sh

RUN chown player:maintenance /opt/mirrage/maintenance.sh && \
    chmod 775 /opt/mirrage/maintenance.sh

# Cron job
RUN cat > /etc/cron.d/mirrage-maintenance <<'EOF'
*/1 * * * * player /opt/mirrage/maintenance.sh >> /var/log/mirrage-maintenance.log 2>&1
EOF

RUN touch /var/log/mirrage-maintenance.log && \
    chown player:player /var/log/mirrage-maintenance.log


#root privesec challenge using cron
COPY challenge/root-maintenance.sh /usr/local/sbin/mirrage-backup

RUN chown root:root /usr/local/sbin/mirrage-backup && \
    chmod 755 /usr/local/sbin/mirrage-backup && \
    printf '%s\n' 'BACKUP_DIR=/var/backups/mirrage' \
      > /opt/mirrage/backup.conf && \
    chown player:player /opt/mirrage/backup.conf && \
    chmod 644 /opt/mirrage/backup.conf && \
    mkdir -p /var/backups/mirrage && \
    touch /var/log/mirrage-root-backup.log && \
    chown root:root /var/log/mirrage-root-backup.log && \
    chmod 644 /var/log/mirrage-root-backup.log

RUN cat > /etc/cron.d/mirrage-root-backup <<'EOF'
* * * * * root /usr/local/sbin/mirrage-backup >> /var/log/mirrage-root-backup.log 2>&1
EOF

RUN chown root:root /etc/cron.d/mirrage-root-backup && \
    chmod 644 /etc/cron.d/mirrage-root-backup

# Start all CTF services
CMD ["/bin/bash", "-c", "cron; /usr/sbin/sshd; sudo -u www-data python3 -u /opt/ctf/backend/server.py & nginx; exec tail -f /dev/null"]