# Ollama setup (host)

Ollama runs on the host, not in Docker. n8n reaches it at `http://host.docker.internal:11434`.

## Why not `0.0.0.0`?

Ollama listens on `127.0.0.1` by default, which containers cannot reach. Binding it to `0.0.0.0` would expose it on every network interface (LAN, Tailscale). Instead, bind it to the Docker bridge address only. Containers can reach that address, and nothing outside the machine can.

`host.docker.internal` is mapped by `extra_hosts: host.docker.internal:host-gateway`. Docker resolves `host-gateway` to the bridge address, `172.17.0.1` by default, on every compose network.

Check yours: `ip -4 addr show docker0`. If it is not `172.17.0.1`, use your address below.

## Steps

1. Set the bind address:
   ```
   sudo systemctl edit ollama
   ```
   ```
   [Service]
   Environment="OLLAMA_HOST=172.17.0.1:11434"
   ```
2. Restart:
   ```
   sudo systemctl daemon-reload
   sudo systemctl restart ollama
   ```
3. If `ufw` is active, allow only Docker networks to that address:
   ```
   sudo ufw allow from 172.16.0.0/12 to 172.17.0.1 port 11434 proto tcp
   ```
4. Pull the default models (the embedding model, and the model that extracts contracts, answers questions and writes the finance summary):
   ```
   ollama pull nomic-embed-text
   ollama pull llama3.1:8b
   ```
   Optional, clearly better answers about contracts (about 19 GB, fits a 24 GB GPU): `ollama pull qwen2.5:32b`, then set `ollama_extract_model` and `ollama_summary_model` in `app_config` to `qwen2.5:32b`.

## Verify

```
ss -ltn | grep 11434          # should show 172.17.0.1:11434, not 0.0.0.0
docker compose exec n8n wget -qO- http://host.docker.internal:11434
```
Expected output of the second command: `Ollama is running`.

The host's own `ollama` CLI talks to `127.0.0.1` by default. After this change, run `export OLLAMA_HOST=172.17.0.1:11434` in your shell if the CLI cannot connect.
