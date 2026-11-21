# Test-only image. Build the CTF smoke-test image first; never deploy this gateway.
FROM mirrage-ctf:shared-flags-check
RUN apt-get update && apt-get install -y --no-install-recommends nftables && rm -rf /var/lib/apt/lists/*
