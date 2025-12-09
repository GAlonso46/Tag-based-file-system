import os
import time
import requests

API_URLS = [
    "http://localhost:8001",  # backend-1
    "http://localhost:8002",  # backend-2
    "http://localhost:8003",  # backend-3
]
FRONT_URLS = [
    "http://localhost:3001",  # frontend-1
    "http://localhost:3002",  # frontend-2
]

TEST_FILENAME = "resilience_test.txt"
TEST_CONTENT = b"Prueba de resiliencia"
TEST_TAGS = "test,resilience"

def docker_cmd(cmd):
    print(f"Ejecutando: {cmd}")
    os.system(cmd)

def wait_for_service(url, timeout=30):
    for _ in range(timeout):
        try:
            r = requests.get(url + "/")
            if r.status_code == 200:
                print(f"Servicio {url} listo")
                return True
        except Exception:
            pass
        time.sleep(1)
    print(f"Timeout esperando {url}")
    return False

def upload_file(api_url, token):
    files = {'file': (TEST_FILENAME, TEST_CONTENT)}
    data = {'tags': TEST_TAGS}
    headers = {'Authorization': f'Bearer {token}'}
    r = requests.post(api_url + "/upload", files=files, data=data, headers=headers)
    print(f"Upload: {r.status_code} {r.text}")
    return r.status_code == 200

def download_file(api_url, token):
    headers = {'Authorization': f'Bearer {token}'}
    r = requests.get(api_url + f"/download/{TEST_FILENAME}", headers=headers)
    print(f"Download: {r.status_code}")
    return r.status_code == 200 and r.content == TEST_CONTENT

def get_token(api_url):
    # Cambia usuario/clave si es necesario
    r = requests.post(api_url + "/auth/login", json={"username": "admin", "password": "admin"})
    if r.status_code == 200:
        return r.json()["access_token"]
    print("No se pudo obtener token")
    return None

def test_cycle():
    # 1. Levanta todos los servicios
    docker_cmd("docker compose up -d --scale backend=3 --scale frontend=2")
    for url in API_URLS + FRONT_URLS:
        wait_for_service(url)

    # 2. Sube archivo en backend-1
    token = get_token(API_URLS[0])
    assert token, "No se obtuvo token"
    assert upload_file(API_URLS[0], token), "Error subiendo archivo"

    # 3. Mata backend-1 y frontend-1
    docker_cmd("docker compose stop backend-1 frontend-1")
    time.sleep(5)

    # 4. Verifica archivo en backend-2 y backend-3
    token2 = get_token(API_URLS[1])
    token3 = get_token(API_URLS[2])
    assert token2 and token3, "No se obtuvo token en otros backends"
    assert download_file(API_URLS[1], token2), "Archivo perdido en backend-2"
    assert download_file(API_URLS[2], token3), "Archivo perdido en backend-3"

    # 5. Sube archivo en backend-2
    assert upload_file(API_URLS[1], token2), "Error subiendo archivo en backend-2"

    # 6. Mata backend-2, levanta backend-1
    docker_cmd("docker compose stop backend-2")
    docker_cmd("docker compose start backend-1")
    wait_for_service(API_URLS[0])

    # 7. Verifica archivo en backend-1 y backend-3
    token1 = get_token(API_URLS[0])
    assert download_file(API_URLS[0], token1), "Archivo perdido en backend-1"
    assert download_file(API_URLS[2], token3), "Archivo perdido en backend-3"

    # 8. Levanta todos los servicios
    docker_cmd("docker compose start backend-2 frontend-1")
    for url in API_URLS + FRONT_URLS:
        wait_for_service(url)

    print("\n✅ Test de resiliencia completado sin pérdida de datos.")

if __name__ == "__main__":
    test_cycle()