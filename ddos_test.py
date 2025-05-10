import subprocess
import time
import matplotlib.pyplot as plt
import numpy as np
import threading
import socket
import requests
import uuid

def send_tcp_connections(rate, duration, target_host, target_port):
    start = time.time()
    count = 0
    errors = 0
    latencies = []
    while time.time() - start < duration:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            connect_start = time.time()
            s.connect((target_host, target_port))
            connect_end = time.time()
            latencies.append(connect_end - connect_start)
            count += 1
            s.close()
        except Exception as e:
            errors += 1
            print(f"TCP Connection failed: {e}")
        time.sleep(max(0.001, 1 / rate))

    avg_latency = np.mean(latencies) if latencies else 0
    return count, errors, 0, avg_latency, time.time() - start

def send_http_requests(rate, duration, target_url):
    start = time.time()
    count = 0
    errors = 0
    rate_limited_errors = 0
    latencies = []
    while time.time() - start < duration:
        try:
            unique_url = f"{target_url}?nocache={uuid.uuid4()}"
            request_start = time.time()
            response = requests.get(unique_url, headers={'Connection': 'close'}, timeout=5)
            latency = time.time() - request_start
            
            if response.status_code == 429:
                rate_limited_errors += 1
                errors += 1
            else:
                response.raise_for_status()
                latencies.append(latency)
                count += 1
        except Exception as e:
            if '429' in str(e):
                rate_limited_errors += 1
            errors += 1
            print(f"HTTP Request failed: {e}")
        time.sleep(max(0.001, 1 / rate))

    avg_latency = np.mean(latencies) if latencies else 0
    return count, errors, rate_limited_errors, avg_latency, time.time() - start

def run_test(rate, duration, target_host, target_port, test_type="tcp"):
    threads = []
    results = []
    for _ in range(4):
        if test_type == "tcp":
            t = threading.Thread(
                target=lambda: results.append(
                    send_tcp_connections(rate // 4, duration, target_host, target_port)
                )
            )
        else:
            target_url = f"http://{target_host}:{target_port}/"
            t = threading.Thread(
                target=lambda: results.append(
                    send_http_requests(rate // 4, duration, target_url)
                )
            )
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()

    total_connections = sum(r[0] for r in results)
    total_errors = sum(r[1] for r in results)
    total_rate_limited = sum(r[2] for r in results)
    avg_latency = np.mean([r[3] for r in results]) 
    total_time = max(r[4] for r in results)
    
    return total_connections, total_errors, total_rate_limited, avg_latency, total_time

def measure_latency(with_protection=True, test_type="tcp"):
    target_host = "localhost"
    target_port = 3000
    rates = [100, 200, 500, 1000]
    duration = 30
    latencies = []
    error_rates = []
    rate_limit_rates = []

    policy_path = "/home/danil/projectSecurity/kubernetes/cilium-policy.yaml"
    
    if with_protection:
        subprocess.run(f"kubectl apply -f {policy_path}", shell=True, check=True)
    else:
        subprocess.run(f"kubectl delete -f {policy_path}", shell=True, check=True)
    time.sleep(5)

    for rate in rates:
        print(f"\n=== Running {test_type.upper()} test: {rate} RPS ===")
        connections, errors, rate_limited, latency, test_duration = run_test(
            rate, duration, target_host, target_port, test_type
        )
        
        total_requests = connections + errors
        error_rate = errors / total_requests if total_requests > 0 else 0
        rate_limit_rate = rate_limited / total_requests if total_requests > 0 else 0
        
        print(f"Sent: {total_requests} | Successful: {connections}")
        print(f"Errors: {errors} (Rate: {error_rate:.2%})")
        if test_type == "http":
            print(f"Rate Limited (429): {rate_limited} (Rate: {rate_limit_rate:.2%})")
        print(f"Avg latency: {latency:.4f}s")
        
        latencies.append(latency)
        error_rates.append(error_rate)
        rate_limit_rates.append(rate_limit_rate)
        time.sleep(10)

    return rates, latencies, error_rates, rate_limit_rates

if __name__ == "__main__":
    # TCP tests
    print("\n==== Testing TCP Flood with Protection ====")
    tcp_protected_rates, tcp_protected_lat, tcp_protected_err, _ = measure_latency(True, "tcp")
    
    print("\n==== Testing TCP Flood without Protection ====")
    tcp_unprotected_rates, tcp_unprotected_lat, tcp_unprotected_err, _ = measure_latency(False, "tcp")

    # HTTP tests
    print("\n==== Testing HTTP GET Flood with Protection ====")
    http_protected_rates, http_protected_lat, http_protected_err, http_protected_rl = measure_latency(True, "http")
    
    print("\n==== Testing HTTP GET Flood without Protection ====")
    http_unprotected_rates, http_unprotected_lat, http_unprotected_err, _ = measure_latency(False, "http")

    # TCP Plots (только >=500 RPS, без error rate)
    plt.figure(figsize=(12, 6))
    
    # Фильтруем данные для >=500 RPS
    tcp_protected_filtered = [(r, l) for r, l in zip(tcp_protected_rates, tcp_protected_lat) if r >= 500]
    tcp_unprotected_filtered = [(r, l) for r, l in zip(tcp_unprotected_rates, tcp_unprotected_lat) if r >= 500]
    
    if tcp_protected_filtered:
        plt.plot(*zip(*tcp_protected_filtered), 'b-o', label='With Protection')
    if tcp_unprotected_filtered:
        plt.plot(*zip(*tcp_unprotected_filtered), 'r--x', label='No Protection')
    
    plt.xlabel('Connections per Second (500+ RPS)')
    plt.ylabel('Latency (seconds)')
    plt.title('TCP Flood: Latency Comparison (500+ RPS)')
    plt.legend()
    plt.grid(True)
    plt.savefig('tcp_latency_high_rps.png')

    # HTTP Plots (только >=500 RPS, без error rate)
    plt.figure(figsize=(12, 6))
    
    # Фильтруем данные для >=500 RPS
    http_protected_filtered = [(r, l) for r, l in zip(http_protected_rates, http_protected_lat) if r >= 500]
    http_unprotected_filtered = [(r, l) for r, l in zip(http_unprotected_rates, http_unprotected_lat) if r >= 500]
    
    if http_protected_filtered:
        plt.plot(*zip(*http_protected_filtered), 'g-o', label='With Protection')
    if http_unprotected_filtered:
        plt.plot(*zip(*http_unprotected_filtered), 'k--x', label='No Protection')
    
    plt.xlabel('Requests per Second (500+ RPS)')
    plt.ylabel('Latency (seconds)')
    plt.title('HTTP GET Flood: Latency Comparison (500+ RPS)')
    plt.legend()
    plt.grid(True)
    plt.savefig('http_latency_high_rps.png')
    plt.close()