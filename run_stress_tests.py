#!/usr/bin/env python3
"""
Suite Completa de Tests de Estrés con Gráficos
"""

import requests
import time
import json
import subprocess
import matplotlib
matplotlib.use('Agg')  # Backend sin GUI
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

API_URL = "http://localhost:8080"
COMPOSE_FILE = "/home/vboxuser/Tag-based-file-system/docker-compose-test.yml"
RESULTS_DIR = Path("/home/vboxuser/Tag-based-file-system/test_results")
RESULTS_DIR.mkdir(exist_ok=True)

def run_docker_cmd(cmd):
    full_cmd = f"sudo docker-compose -f {COMPOSE_FILE} {cmd}"
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0

def register_and_login(username):
    try:
        requests.post(f"{API_URL}/auth/register", json={
            "username": username,
            "email": f"{username}@test.com",
            "password": "test123"
        }, timeout=5)
    except:
        pass
    
    try:
        response = requests.post(
            f"{API_URL}/auth/login",
            data={"username": username, "password": "test123"},
            timeout=5
        )
        
        if response.status_code == 200:
            return response.json()['access_token']
    except:
        pass
    return None

def upload_file(token, filename, tags):
    files = {'file': (filename, f'Test content {filename}\n{datetime.now()}')}
    data = {'tags': tags}
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.post(f"{API_URL}/upload", files=files, data=data, headers=headers, timeout=10)
        return response.status_code == 200
    except:
        return False

def list_files(token):
    headers = {'Authorization': f'Bearer {token}'}
    try:
        response = requests.get(f"{API_URL}/files", headers=headers, timeout=10)
        return response.json() if response.status_code == 200 else []
    except:
        return []

print("="*60)
print("  SUITE DE TESTS DE ESTRÉS")
print("="*60)

# TEST 1: ESCALABILIDAD
print("\n[TEST 1] Escalabilidad: 1 → 3 → 1 backends")

scalability_results = {
    'backends': [],
    'upload_time': [],
    'throughput': []
}

for num_backends in [1, 3, 1]:
    print(f"\n  Config {num_backends} backend(s)...")
    
    if num_backends == 1:
        run_docker_cmd("stop backend-2 backend-3")
    else:
        run_docker_cmd("start backend-1 backend-2 backend-3")
    
    time.sleep(10)  # Más tiempo para que los servicios se estabilicen
    
    token = register_and_login(f"scale_user_{num_backends}_{int(time.time())}")
    if not token:
        print("    ✗ Login falló")
        continue
    
    num_files = 30
    start = time.time()
    successes = 0
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(upload_file, token, f"scale_{num_backends}_{i}.txt", f"scale,test{num_backends}")
            for i in range(num_files)
        ]
        
        for future in as_completed(futures):
            if future.result():
                successes += 1
    
    duration = time.time() - start
    throughput = successes / duration if duration > 0 else 0
    
    scalability_results['backends'].append(num_backends)
    scalability_results['upload_time'].append(duration)
    scalability_results['throughput'].append(throughput)
    
    print(f"    ✓ {successes}/{num_files}, {duration:.2f}s, {throughput:.2f} arch/s")

# Restaurar 3 backends
run_docker_cmd("start backend-1 backend-2 backend-3")
time.sleep(5)

# TEST 2: RENDIMIENTO BAJO CARGA
print("\n[TEST 2] Rendimiento: Carga incremental")

performance_results = {
    'load': [],
    'avg_time': [],
    'success_rate': []
}

token = register_and_login(f"perf_user_{int(time.time())}")

for load in [10, 30, 50, 75, 100]:
    print(f"\n  Cargando {load} archivos...")
    
    start = time.time()
    successes = 0
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [
            executor.submit(upload_file, token, f"perf_{load}_{i}.txt", f"perf,load{load}")
            for i in range(load)
        ]
        
        for future in as_completed(futures):
            if future.result():
                successes += 1
    
    duration = time.time() - start
    avg_time = duration / load if load > 0 else 0
    success_rate = (successes / load) * 100 if load > 0 else 0
    
    performance_results['load'].append(load)
    performance_results['avg_time'].append(avg_time)
    performance_results['success_rate'].append(success_rate)
    
    print(f"    ✓ {successes}/{load} ({success_rate:.1f}%), avg: {avg_time:.3f}s")

# TEST 3: CONSISTENCIA
print("\n[TEST 3] Consistencia durante fallos")

consistency_results = {
    'phase': [],
    'files_uploaded': [],
    'files_verified': []
}

token = register_and_login(f"cons_user_{int(time.time())}")

print("\n  Fase 1: 3 backends activos")
successes = 0
with ThreadPoolExecutor(max_workers=15) as executor:
    futures = [
        executor.submit(upload_file, token, f"cons_phase1_{i}.txt", "consistency,phase1")
        for i in range(40)
    ]
    for future in as_completed(futures):
        if future.result():
            successes += 1

time.sleep(2)
files = list_files(token)
phase1_count = len([f for f in files if 'phase1' in f['name']])
consistency_results['phase'].append('3 backends')
consistency_results['files_uploaded'].append(successes)
consistency_results['files_verified'].append(phase1_count)
print(f"    ✓ Subidos: {successes}, Verificados: {phase1_count}")

print("\n  Fase 2: Matando backend-1...")
run_docker_cmd("stop backend-1")
time.sleep(2)

successes = 0
with ThreadPoolExecutor(max_workers=15) as executor:
    futures = [
        executor.submit(upload_file, token, f"cons_phase2_{i}.txt", "consistency,phase2")
        for i in range(40)
    ]
    for future in as_completed(futures):
        if future.result():
            successes += 1

time.sleep(2)
files = list_files(token)
phase2_count = len([f for f in files if 'phase2' in f['name']])
consistency_results['phase'].append('2 backends')
consistency_results['files_uploaded'].append(successes)
consistency_results['files_verified'].append(phase2_count)
print(f"    ✓ Subidos: {successes}, Verificados: {phase2_count}")

print("\n  Fase 3: Matando backend-2...")
run_docker_cmd("stop backend-2")
time.sleep(2)

successes = 0
with ThreadPoolExecutor(max_workers=15) as executor:
    futures = [
        executor.submit(upload_file, token, f"cons_phase3_{i}.txt", "consistency,phase3")
        for i in range(40)
    ]
    for future in as_completed(futures):
        if future.result():
            successes += 1

time.sleep(2)
files = list_files(token)
phase3_count = len([f for f in files if 'phase3' in f['name']])
consistency_results['phase'].append('1 backend')
consistency_results['files_uploaded'].append(successes)
consistency_results['files_verified'].append(phase3_count)
print(f"    ✓ Subidos: {successes}, Verificados: {phase3_count}")

# Restaurar
run_docker_cmd("start backend-1 backend-2")
time.sleep(5)

# GENERAR GRÁFICOS
print("\n[GENERANDO GRÁFICOS]")

# Gráfico 1: Escalabilidad
plt.figure(figsize=(12, 5))

plt.subplot(1, 2, 1)
plt.plot(scalability_results['backends'], scalability_results['upload_time'], 'o-', linewidth=2, markersize=10)
plt.xlabel('Número de Backends', fontsize=12)
plt.ylabel('Tiempo Total (s)', fontsize=12)
plt.title('Escalabilidad: Tiempo vs Backends', fontsize=14, fontweight='bold')
plt.grid(True, alpha=0.3)

plt.subplot(1, 2, 2)
plt.plot(scalability_results['backends'], scalability_results['throughput'], 's-', color='green', linewidth=2, markersize=10)
plt.xlabel('Número de Backends', fontsize=12)
plt.ylabel('Throughput (archivos/s)', fontsize=12)
plt.title('Escalabilidad: Throughput vs Backends', fontsize=14, fontweight='bold')
plt.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(RESULTS_DIR / 'scalability.png', dpi=150)
print(f"  ✓ scalability.png")
plt.close()

# Gráfico 2: Rendimiento
plt.figure(figsize=(12, 5))

plt.subplot(1, 2, 1)
plt.bar(range(len(performance_results['load'])), performance_results['avg_time'], color='skyblue', edgecolor='navy')
plt.xlabel('Carga Concurrente', fontsize=12)
plt.ylabel('Tiempo Promedio (s)', fontsize=12)
plt.title('Rendimiento: Latencia vs Carga', fontsize=14, fontweight='bold')
plt.xticks(range(len(performance_results['load'])), performance_results['load'])
plt.grid(True, alpha=0.3, axis='y')

plt.subplot(1, 2, 2)
plt.plot(performance_results['load'], performance_results['success_rate'], 'o-', color='red', linewidth=2, markersize=10)
plt.xlabel('Carga Concurrente', fontsize=12)
plt.ylabel('Tasa de Éxito (%)', fontsize=12)
plt.title('Rendimiento: Éxito vs Carga', fontsize=14, fontweight='bold')
plt.ylim([90, 101])
plt.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(RESULTS_DIR / 'performance.png', dpi=150)
print(f"  ✓ performance.png")
plt.close()

# Gráfico 3: Consistencia
plt.figure(figsize=(10, 6))

x = np.arange(len(consistency_results['phase']))
width = 0.35

plt.bar(x - width/2, consistency_results['files_uploaded'], width, label='Subidos', color='lightgreen', edgecolor='green')
plt.bar(x + width/2, consistency_results['files_verified'], width, label='Verificados', color='lightcoral', edgecolor='red')

plt.xlabel('Fase del Test', fontsize=12)
plt.ylabel('Número de Archivos', fontsize=12)
plt.title('Consistencia: Archivos Subidos vs Verificados', fontsize=14, fontweight='bold')
plt.xticks(x, consistency_results['phase'])
plt.legend()
plt.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
plt.savefig(RESULTS_DIR / 'consistency.png', dpi=150)
print(f"  ✓ consistency.png")
plt.close()

# REPORTE FINAL
print("\n" + "="*60)
print("  REPORTE FINAL")
print("="*60)

print("\n[ESCALABILIDAD]")
max_throughput = max(scalability_results['throughput'])
max_idx = scalability_results['throughput'].index(max_throughput)
print(f"  Mejor throughput: {max_throughput:.2f} archivos/s con {scalability_results['backends'][max_idx]} backends")

print("\n[RENDIMIENTO]")
avg_success = sum(performance_results['success_rate'])/len(performance_results['success_rate'])
print(f"  Máxima carga: {max(performance_results['load'])} archivos concurrentes")
print(f"  Tasa éxito promedio: {avg_success:.1f}%")

print("\n[CONSISTENCIA]")
total_up = sum(consistency_results['files_uploaded'])
total_ver = sum(consistency_results['files_verified'])
print(f"  Total subidos: {total_up}")
print(f"  Total verificados: {total_ver}")
print(f"  Integridad: {(total_ver/total_up)*100:.1f}%")

print(f"\n  📊 Gráficos guardados en: {RESULTS_DIR}")
print("\n" + "="*60)
print("  ✅ TESTS COMPLETADOS")
print("="*60)
