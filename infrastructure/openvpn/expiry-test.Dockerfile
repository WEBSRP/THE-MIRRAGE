FROM mirrage-ctf:recovery-20261121
RUN apt-get update && apt-get install -y --no-install-recommends openvpn && rm -rf /var/lib/apt/lists/*
