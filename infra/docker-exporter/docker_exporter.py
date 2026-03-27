"""
docker_exporter.py — Lightweight Docker stats → Prometheus exporter.
Reads /var/run/docker.sock and exposes per-container CPU, memory,
and network metrics compatible with Docker Desktop (Windows/Mac).
"""

import http.server
import json
import socket
import time
import threading

DOCKER_SOCKET = "/var/run/docker.sock"
PORT = 9417
SCRAPE_INTERVAL = 10

_metrics_cache = ""
_lock = threading.Lock()


def _docker_api(path):
    """Call Docker Engine API via Unix socket."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(DOCKER_SOCKET)
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: localhost\r\n"
        f"Connection: close\r\n\r\n"
    )
    sock.sendall(request.encode())
    response = b""
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        response += chunk
    sock.close()
    body = response.split(b"\r\n\r\n", 1)
    if len(body) < 2:
        return None
    raw = body[1]
    # Handle chunked transfer encoding
    header_part = response.split(b"\r\n\r\n", 1)[0].decode(errors="ignore")
    if "chunked" in header_part.lower():
        decoded = b""
        data = raw
        while data:
            line_end = data.find(b"\r\n")
            if line_end == -1:
                break
            size_str = data[:line_end].decode().strip()
            if not size_str:
                data = data[line_end + 2:]
                continue
            chunk_size = int(size_str, 16)
            if chunk_size == 0:
                break
            decoded += data[line_end + 2:line_end + 2 + chunk_size]
            data = data[line_end + 2 + chunk_size + 2:]
        raw = decoded
    return raw.decode(errors="ignore")


def _get_containers():
    """List running containers."""
    resp = _docker_api("/containers/json")
    if not resp:
        return []
    return json.loads(resp)


def _get_stats(container_id):
    """Get one-shot stats for a container."""
    resp = _docker_api(f"/containers/{container_id}/stats?stream=false")
    if not resp:
        return None
    return json.loads(resp)


def _calc_cpu_percent(stats):
    """Calculate CPU % from Docker stats."""
    cpu = stats.get("cpu_stats", {})
    precpu = stats.get("precpu_stats", {})
    cpu_delta = (
        cpu.get("cpu_usage", {}).get("total_usage", 0)
        - precpu.get("cpu_usage", {}).get("total_usage", 0)
    )
    system_delta = (
        cpu.get("system_cpu_usage", 0)
        - precpu.get("system_cpu_usage", 0)
    )
    n_cpus = cpu.get("online_cpus", 1)
    if system_delta > 0 and cpu_delta >= 0:
        return (cpu_delta / system_delta) * n_cpus * 100.0
    return 0.0


def _collect_metrics():
    """Collect metrics from all running containers."""
    lines = [
        "# HELP docker_container_cpu_percent CPU usage percent per container",
        "# TYPE docker_container_cpu_percent gauge",
        "# HELP docker_container_memory_usage_bytes Memory usage in bytes",
        "# TYPE docker_container_memory_usage_bytes gauge",
        "# HELP docker_container_memory_limit_bytes Memory limit in bytes",
        "# TYPE docker_container_memory_limit_bytes gauge",
        "# HELP docker_container_memory_percent Memory usage percent",
        "# TYPE docker_container_memory_percent gauge",
        "# HELP docker_container_network_rx_bytes Network bytes received",
        "# TYPE docker_container_network_rx_bytes gauge",
        "# HELP docker_container_network_tx_bytes Network bytes transmitted",
        "# TYPE docker_container_network_tx_bytes gauge",
        "# HELP docker_container_running Whether the container is running",
        "# TYPE docker_container_running gauge",
    ]

    containers = _get_containers()
    for c in containers:
        name = c.get("Names", ["/unknown"])[0].lstrip("/")
        image = c.get("Image", "unknown").split(":")[0].split("/")[-1]
        cid = c["Id"]
        labels = f'name="{name}",image="{image}"'

        stats = _get_stats(cid)
        if not stats:
            continue

        # CPU
        cpu_pct = _calc_cpu_percent(stats)
        lines.append(
            f"docker_container_cpu_percent{{{labels}}} {cpu_pct:.4f}"
        )

        # Memory
        mem = stats.get("memory_stats", {})
        mem_usage = mem.get("usage", 0)
        mem_limit = mem.get("limit", 0)
        mem_pct = (mem_usage / mem_limit * 100) if mem_limit > 0 else 0
        lines.append(
            f"docker_container_memory_usage_bytes{{{labels}}} {mem_usage}"
        )
        lines.append(
            f"docker_container_memory_limit_bytes{{{labels}}} {mem_limit}"
        )
        lines.append(
            f"docker_container_memory_percent{{{labels}}} {mem_pct:.2f}"
        )

        # Network
        networks = stats.get("networks", {})
        rx_total = sum(v.get("rx_bytes", 0) for v in networks.values())
        tx_total = sum(v.get("tx_bytes", 0) for v in networks.values())
        lines.append(
            f"docker_container_network_rx_bytes{{{labels}}} {rx_total}"
        )
        lines.append(
            f"docker_container_network_tx_bytes{{{labels}}} {tx_total}"
        )

        # Running
        lines.append(f"docker_container_running{{{labels}}} 1")

    return "\n".join(lines) + "\n"


def _background_collector():
    """Periodically collect metrics in background."""
    global _metrics_cache
    while True:
        try:
            data = _collect_metrics()
            with _lock:
                _metrics_cache = data
        except Exception as e:
            print(f"[docker-exporter] error: {e}", flush=True)
        time.sleep(SCRAPE_INTERVAL)


class MetricsHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            with _lock:
                body = _metrics_cache.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(200)
            body = b"Docker Exporter - /metrics\n"
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Silence access logs


if __name__ == "__main__":
    print(f"[docker-exporter] starting on :{PORT}", flush=True)
    # Initial collection
    _metrics_cache = _collect_metrics()
    # Background thread
    t = threading.Thread(target=_background_collector, daemon=True)
    t.start()
    server = http.server.HTTPServer(("0.0.0.0", PORT), MetricsHandler)
    print(
        f"[docker-exporter] serving metrics for "
        f"{len(_get_containers())} containers",
        flush=True,
    )
    server.serve_forever()
