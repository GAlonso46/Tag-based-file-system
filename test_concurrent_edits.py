#!/usr/bin/env python3
"""
Test de Edición Concurrente con Optimistic Locking

Simula múltiples clientes/frontends editando el mismo archivo
simultáneamente para validar el manejo de conflictos.

Escenarios:
1. Dos usuarios editan mismo archivo → uno obtiene 409 Conflict
2. Usuario refresca y reintenta → actualización exitosa
3. Sin version → actualización siempre exitosa (sin validación)
"""

import requests
import time
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://localhost:8080"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

def get_token(username=ADMIN_USER, password=ADMIN_PASS):
    """Obtener JWT token"""
    resp = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": username, "password": password}
    )
    if resp.status_code == 200:
        return resp.json()["access_token"]
    raise Exception(f"Login failed: {resp.text}")

def upload_file(token, filename, tags="test"):
    """Subir archivo de prueba"""
    files = {"file": (filename, io.BytesIO(b"test content"), "text/plain")}
    data = {"tags": tags}
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = requests.post(
        f"{BASE_URL}/upload",
        files=files,
        data=data,
        headers=headers
    )
    return resp

def get_file_info(token, filename):
    """Obtener info del archivo incluyendo version"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/files", headers=headers)
    
    if resp.status_code == 200:
        files = resp.json()
        for f in files:
            if f["filename"] == filename:
                return f
    return None

def update_tags(token, filename, new_tags, version=None):
    """Actualizar tags con optimistic locking opcional"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {"tags": new_tags}
    if version is not None:
        payload["version"] = version
    
    resp = requests.put(
        f"{BASE_URL}/files/{filename}/tags",
        json=payload,
        headers=headers
    )
    return resp

def delete_file(token, filename):
    """Eliminar archivo"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.delete(f"{BASE_URL}/files/{filename}", headers=headers)
    return resp

def test_concurrent_update_with_locking():
    """
    Test 1: Dos usuarios intentan actualizar simultáneamente CON version.
    El segundo debe recibir 409 Conflict.
    """
    print("\n[TEST 1] Edición concurrente CON optimistic locking")
    print("-" * 60)
    
    token = get_token()
    filename = "concurrent_test_1.txt"
    
    # Limpiar archivo si existe
    delete_file(token, filename)
    
    # Subir archivo inicial
    print(f"  Subiendo {filename}...")
    resp = upload_file(token, filename, "tag1,tag2")
    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    
    # Obtener versión inicial
    file_info = get_file_info(token, filename)
    initial_version = file_info["version"]
    print(f"  ✓ Archivo subido con version={initial_version}")
    
    # Simular 2 clientes que leen el archivo simultáneamente
    client1_version = initial_version
    client2_version = initial_version
    
    def client1_update():
        """Cliente 1 intenta actualizar"""
        time.sleep(0.1)  # Pequeño delay
        resp = update_tags(token, filename, ["tag1", "tag2", "client1"], client1_version)
        return ("Client 1", resp)
    
    def client2_update():
        """Cliente 2 intenta actualizar (ligeramente después)"""
        time.sleep(0.15)  # Delay mayor para que client1 gane
        resp = update_tags(token, filename, ["tag1", "tag2", "client2"], client2_version)
        return ("Client 2", resp)
    
    # Ejecutar updates concurrentes
    print(f"  Ejecutando updates concurrentes con version={initial_version}...")
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(client1_update), executor.submit(client2_update)]
        results = [f.result() for f in as_completed(futures)]
    
    # Analizar resultados
    success_count = sum(1 for _, r in results if r.status_code == 200)
    conflict_count = sum(1 for _, r in results if r.status_code == 409)
    
    print(f"\n  Resultados:")
    for client, resp in results:
        if resp.status_code == 200:
            print(f"    ✓ {client}: SUCCESS (200) - version={resp.json()['version']}")
        elif resp.status_code == 409:
            detail = resp.json()["detail"]
            print(f"    ✗ {client}: CONFLICT (409) - {detail['message']}")
        else:
            print(f"    ? {client}: {resp.status_code} - {resp.text}")
    
    print(f"\n  Resumen: {success_count} éxito, {conflict_count} conflictos")
    
    # Validación
    assert success_count == 1, f"Expected 1 success, got {success_count}"
    assert conflict_count == 1, f"Expected 1 conflict, got {conflict_count}"
    
    # Verificar versión final
    final_info = get_file_info(token, filename)
    print(f"  ✓ Versión final: {final_info['version']} (tags: {final_info['tags']})")
    
    # Limpiar
    delete_file(token, filename)
    print("  ✓ Test completado exitosamente")

def test_retry_after_conflict():
    """
    Test 2: Cliente recibe 409, refresca versión y reintenta.
    El segundo intento debe ser exitoso.
    """
    print("\n[TEST 2] Retry después de conflict")
    print("-" * 60)
    
    token = get_token()
    filename = "retry_test.txt"
    
    # Limpiar y subir
    delete_file(token, filename)
    upload_file(token, filename, "initial")
    
    # Cliente 1 lee versión
    file_info = get_file_info(token, filename)
    v1 = file_info["version"]
    print(f"  Cliente lee archivo con version={v1}")
    
    # Cliente 2 actualiza primero
    print(f"  Otro usuario actualiza el archivo...")
    resp = update_tags(token, filename, ["updated_by_other"], v1)
    assert resp.status_code == 200
    v2 = resp.json()["version"]
    print(f"  ✓ Actualizado a version={v2}")
    
    # Cliente 1 intenta actualizar con versión obsoleta
    print(f"  Cliente 1 intenta actualizar con version={v1} (obsoleta)...")
    resp = update_tags(token, filename, ["client1_attempt"], v1)
    assert resp.status_code == 409, "Expected 409 Conflict"
    print(f"  ✓ Recibió 409 Conflict como esperado")
    
    # Cliente 1 refresca y obtiene nueva versión
    file_info = get_file_info(token, filename)
    current_version = file_info["version"]
    print(f"  Cliente refresca y obtiene version={current_version}")
    
    # Cliente 1 reintenta con versión correcta
    print(f"  Cliente reintenta con version={current_version}...")
    resp = update_tags(token, filename, ["client1_retry"], current_version)
    assert resp.status_code == 200, f"Retry failed: {resp.text}"
    final_version = resp.json()["version"]
    print(f"  ✓ Actualización exitosa, nueva version={final_version}")
    
    # Limpiar
    delete_file(token, filename)
    print("  ✓ Test completado exitosamente")

def test_without_version():
    """
    Test 3: Actualización SIN enviar version (retrocompatibilidad).
    Debe permitir actualización sin validación.
    """
    print("\n[TEST 3] Actualización sin optimistic locking (sin version)")
    print("-" * 60)
    
    token = get_token()
    filename = "no_version_test.txt"
    
    # Limpiar y subir
    delete_file(token, filename)
    upload_file(token, filename, "initial")
    
    file_info = get_file_info(token, filename)
    print(f"  Archivo con version={file_info['version']}")
    
    # Actualizar SIN enviar version
    print(f"  Actualizando tags SIN enviar version...")
    resp = update_tags(token, filename, ["no_version_check"], version=None)
    assert resp.status_code == 200, f"Update failed: {resp.text}"
    
    new_version = resp.json()["version"]
    print(f"  ✓ Actualización exitosa, nueva version={new_version}")
    print(f"  ✓ Modo retrocompatible funciona correctamente")
    
    # Limpiar
    delete_file(token, filename)
    print("  ✓ Test completado exitosamente")

def test_high_concurrency():
    """
    Test 4: 10 clientes intentan actualizar simultáneamente.
    Solo 1 debe tener éxito, los otros 9 deben recibir 409.
    """
    print("\n[TEST 4] Alta concurrencia (10 clientes simultáneos)")
    print("-" * 60)
    
    token = get_token()
    filename = "high_concurrency.txt"
    
    # Limpiar y subir
    delete_file(token, filename)
    upload_file(token, filename, "initial")
    
    file_info = get_file_info(token, filename)
    initial_version = file_info["version"]
    print(f"  Archivo inicial con version={initial_version}")
    
    def concurrent_update(client_id):
        """Cada cliente intenta actualizar con la misma versión"""
        resp = update_tags(
            token, 
            filename, 
            [f"client_{client_id}"], 
            initial_version
        )
        return (client_id, resp.status_code, resp.json() if resp.status_code in [200, 409] else resp.text)
    
    # Ejecutar 10 updates concurrentes
    print(f"  Lanzando 10 updates concurrentes con version={initial_version}...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(concurrent_update, i) for i in range(10)]
        results = [f.result() for f in as_completed(futures)]
    
    # Contar resultados
    success = [r for r in results if r[1] == 200]
    conflicts = [r for r in results if r[1] == 409]
    
    print(f"\n  Resultados:")
    print(f"    ✓ Éxitos (200): {len(success)}")
    print(f"    ✗ Conflictos (409): {len(conflicts)}")
    
    if len(success) > 0:
        winner = success[0]
        print(f"    🏆 Ganador: Client {winner[0]} (version final: {winner[2].get('version', 'N/A')})")
    
    # Validación
    assert len(success) == 1, f"Expected exactly 1 success, got {len(success)}"
    assert len(conflicts) == 9, f"Expected 9 conflicts, got {len(conflicts)}"
    
    # Limpiar
    delete_file(token, filename)
    print("  ✓ Test completado exitosamente")

if __name__ == "__main__":
    print("=" * 60)
    print("  TESTS DE CONCURRENCIA - OPTIMISTIC LOCKING")
    print("=" * 60)
    print(f"  API: {BASE_URL}")
    print("=" * 60)
    
    try:
        # Obtener token para verificar conexión
        token = get_token()
        print("✓ Conectado exitosamente\n")
        
        # Ejecutar tests
        test_concurrent_update_with_locking()
        test_retry_after_conflict()
        test_without_version()
        test_high_concurrency()
        
        print("\n" + "=" * 60)
        print("  ✓ TODOS LOS TESTS PASARON")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
