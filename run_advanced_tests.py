#!/usr/bin/env python3
"""
Tests Adicionales de Distribución y Recuperación
"""

import requests
import time
import subprocess
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

API_URL = "http://localhost:8080"
COMPOSE_FILE = "/home/vboxuser/Tag-based-file-system/docker-compose-test.yml"
RESULTS_DIR = Path("/home/vboxuser/Tag-based-file-system/test_results")

def run_docker_cmd(cmd):
    full_cmd = f"sudo docker-compose -f {COMPOSE_FILE} {cmd}"
    subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    return True

def register_login(username):
    try:
        requests.post(f"{API_URL}/auth/register", json={
            "username": username,
            "email": f"{username}@test.com",
            "password": "test123"
        }, timeout=5)
    except:
        pass
    
    response = requests.post(
        f"{API_URL}/auth/login",
        data={"username": username, "password": "test123"},
        timeout=5
    )
    return response.json()['access_token']

def upload_to_specific_backend(token, filename, port):
    """Subir a un backend específico"""
    files = {'file': (filename, f'Test {filename}')}
    data = {'tags': f'backend{port},recovery'}
    headers = {'Authorization': f'Bearer {token}'}
    
    url = f"http://localhost:{port}/upload"
    try:
        response = requests.post(url, files=files, data=data, headers=headers, timeout=10)
        return response.status_code == 200
    except:
        return False

def verify_file_exists(token, filename):
    """Verificar que un archivo existe a través del load balancer"""
    headers = {'Authorization': f'Bearer {token}'}
    try:
        response = requests.get(f"{API_URL}/files", headers=headers, timeout=10)
        if response.status_code == 200:
            files = response.json()
            return any(f['filename'] == filename for f in files)
    except:
        pass
    return False

def measure_latency(token, num_requests):
    """Medir latencia de requests"""
    headers = {'Authorization': f'Bearer {token}'}
    latencies = []
    
    for i in range(num_requests):
        start = time.time()
        try:
            response = requests.get(f"{API_URL}/files", headers=headers, timeout=10)
            if response.status_code == 200:
                latencies.append((time.time() - start) * 1000)  # ms
        except:
            pass
    
    return latencies

print("="*60)
print("  TESTS DE DISTRIBUCIÓN Y RECUPERACIÓN")
print("="*60)

# TEST 1: RECUPERACIÓN
print("\n[TEST 1] Recuperación: Upload → Kill → Verify")

recovery_results = []

token = register_login(f"recovery_user_{int(time.time())}")

# Subir archivo a backend-1
print("\n  Subiendo 10 archivos a backend-1 (puerto 8001)...")
uploaded = []
for i in range(10):
    filename = f"recovery_b1_{i}.txt"
    if upload_to_specific_backend(token, filename, 8001):
        uploaded.append(filename)
        print(f"    ✓ {filename}")

time.sleep(2)

# Matar backend-1
print("\n  💀 Matando backend-1...")
run_docker_cmd("stop backend-1")
time.sleep(3)

# Verificar archivos en backend-2/3 a través del load balancer
print("\n  Verificando archivos en backend-2/3...")
verified = 0
for filename in uploaded:
    if verify_file_exists(token, filename):
        verified += 1
        print(f"    ✓ {filename} encontrado")

recovery_results.append({
    'scenario': 'Backend-1 caído',
    'uploaded': len(uploaded),
    'verified': verified
})

# Restaurar backend-1
print("\n  🔄 Restaurando backend-1...")
run_docker_cmd("start backend-1")
time.sleep(5)

# Ahora subir a backend-2
print("\n  Subiendo 10 archivos a backend-2 (puerto 8002)...")
uploaded2 = []
for i in range(10):
    filename = f"recovery_b2_{i}.txt"
    if upload_to_specific_backend(token, filename, 8002):
        uploaded2.append(filename)

time.sleep(2)

# Matar backend-2
print("\n  💀 Matando backend-2...")
run_docker_cmd("stop backend-2")
time.sleep(3)

# Verificar en backend-1/3
verified2 = 0
for filename in uploaded2:
    if verify_file_exists(token, filename):
        verified2 += 1

recovery_results.append({
    'scenario': 'Backend-2 caído',
    'uploaded': len(uploaded2),
    'verified': verified2
})

print(f"\n    Recuperación total: {verified + verified2}/{len(uploaded) + len(uploaded2)}")

# Restaurar todo
run_docker_cmd("start backend-2")
time.sleep(5)

# TEST 2: LATENCIA BAJO DIFERENTES BACKENDS
print("\n[TEST 2] Latencia: 1, 2, 3 backends")

latency_results = {
    'backends': [],
    'avg_latency': [],
    'p95_latency': [],
    'p99_latency': []
}

for config, backends_to_stop in [
    (1, ['backend-2', 'backend-3']),
    (2, ['backend-3']),
    (3, [])
]:
    print(f"\n  Config: {config} backend(s)...")
    
    # Configurar backends
    if backends_to_stop:
        run_docker_cmd(f"stop {' '.join(backends_to_stop)}")
        time.sleep(5)
    else:
        run_docker_cmd("start backend-1 backend-2 backend-3")
        time.sleep(5)
    
    # Medir latencias
    latencies = measure_latency(token, 50)
    
    if latencies:
        avg_lat = sum(latencies) / len(latencies)
        p95_lat = sorted(latencies)[int(len(latencies) * 0.95)]
        p99_lat = sorted(latencies)[int(len(latencies) * 0.99)]
        
        latency_results['backends'].append(config)
        latency_results['avg_latency'].append(avg_lat)
        latency_results['p95_latency'].append(p95_lat)
        latency_results['p99_latency'].append(p99_lat)
        
        print(f"    Avg: {avg_lat:.2f}ms, P95: {p95_lat:.2f}ms, P99: {p99_lat:.2f}ms")

# Restaurar todo
run_docker_cmd("start backend-1 backend-2 backend-3")
time.sleep(5)

# TEST 3: DISTRIBUCIÓN DE CARGA
print("\n[TEST 3] Distribución de carga entre backends")

distribution_results = {
    'backend': [],
    'requests': []
}

token2 = register_login(f"dist_user_{int(time.time())}")

# Enviar 90 requests y ver cómo se distribuyen
print("\n  Enviando 90 requests al load balancer...")

def upload_and_track():
    import random
    filename = f"dist_{random.randint(1000,9999)}.txt"
    files = {'file': (filename, 'distribution test')}
    data = {'tags': 'distribution'}
    headers = {'Authorization': f'Bearer {token2}'}
    
    try:
        response = requests.post(f"{API_URL}/upload", files=files, data=data, headers=headers, timeout=10)
        return response.status_code == 200
    except:
        return False

with ThreadPoolExecutor(max_workers=15) as executor:
    results = list(executor.map(lambda x: upload_and_track(), range(90)))

successes = sum(results)
print(f"    ✓ {successes}/90 requests exitosos")

# GENERAR GRÁFICOS ADICIONALES
print("\n[GENERANDO GRÁFICOS]")

# Gráfico 1: Recuperación
plt.figure(figsize=(10, 6))
scenarios = [r['scenario'] for r in recovery_results]
uploaded_counts = [r['uploaded'] for r in recovery_results]
verified_counts = [r['verified'] for r in recovery_results]

x = range(len(scenarios))
width = 0.35

plt.bar([i - width/2 for i in x], uploaded_counts, width, label='Subidos', color='lightblue', edgecolor='blue')
plt.bar([i + width/2 for i in x], verified_counts, width, label='Verificados tras fallo', color='lightgreen', edgecolor='green')

plt.xlabel('Escenario', fontsize=12)
plt.ylabel('Número de Archivos', fontsize=12)
plt.title('Recuperación: Persistencia tras Fallos de Backend', fontsize=14, fontweight='bold')
plt.xticks(x, scenarios, rotation=15, ha='right')
plt.legend()
plt.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
plt.savefig(RESULTS_DIR / 'recovery.png', dpi=150)
print(f"  ✓ recovery.png")
plt.close()

# Gráfico 2: Latencia
if latency_results['backends']:
    plt.figure(figsize=(10, 6))
    
    x = latency_results['backends']
    
    plt.plot(x, latency_results['avg_latency'], 'o-', label='Promedio', linewidth=2, markersize=10)
    plt.plot(x, latency_results['p95_latency'], 's-', label='P95', linewidth=2, markersize=10)
    plt.plot(x, latency_results['p99_latency'], '^-', label='P99', linewidth=2, markersize=10)
    
    plt.xlabel('Número de Backends Activos', fontsize=12)
    plt.ylabel('Latencia (ms)', fontsize=12)
    plt.title('Latencia de Respuesta vs Backends Activos', fontsize=14, fontweight='bold')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / 'latency.png', dpi=150)
    print(f"  ✓ latency.png")
    plt.close()

# REPORTE
print("\n" + "="*60)
print("  REPORTE ADICIONAL")
print("="*60)

print("\n[RECUPERACIÓN]")
total_up = sum(r['uploaded'] for r in recovery_results)
total_ver = sum(r['verified'] for r in recovery_results)
print(f"  Tasa de recuperación: {(total_ver/total_up)*100:.1f}%")

if latency_results['backends']:
    print("\n[LATENCIA]")
    min_lat = min(latency_results['avg_latency'])
    max_lat = max(latency_results['avg_latency'])
    print(f"  Mejor latencia: {min_lat:.2f}ms")
    print(f"  Peor latencia: {max_lat:.2f}ms")
    print(f"  Mejora con 3 backends: {((max_lat-min_lat)/max_lat)*100:.1f}%")

print(f"\n  📊 Gráficos guardados en: {RESULTS_DIR}")
print("\n" + "="*60)
print("  ✅ TESTS ADICIONALES COMPLETADOS")
print("="*60)
