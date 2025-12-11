#!/usr/bin/env python3
import requests
import time

API_URL = "http://127.0.0.1:8000"
USERNAME = f"simpleuser_{int(time.time())}"
PASSWORD = "password123"

# 1. Register
print(f"[1] Registering {USERNAME}...")
res = requests.post(f"{API_URL}/auth/register", json={
    "username": USERNAME,
    "email": f"{USERNAME}@test.com",
    "password": PASSWORD
})
print(f"    Status: {res.status_code}")
if res.status_code != 201:
    print(f"    ERROR: {res.text}")
    exit(1)

# 2. Login
print(f"[2] Logging in...")
res = requests.post(f"{API_URL}/auth/login", data={
    "username": USERNAME,
    "password": PASSWORD
})
print(f"    Status: {res.status_code}")
if res.status_code != 200:
    print(f"    ERROR: {res.text}")
    exit(1)

token = res.json()["access_token"]
print(f"    Token: {token[:30]}...")

# 3. Upload file
print(f"[3] Uploading file...")
files = {"file": ("test.txt", b"Hello World", "text/plain")}
headers = {"Authorization": f"Bearer {token}"}
data = {"tags": "test"}

res = requests.post(f"{API_URL}/files", files=files, data=data, headers=headers)
print(f"    Status: {res.status_code}")
if res.status_code == 200:
    print(f"    SUCCESS: {res.json()}")
else:
    print(f"    ERROR: {res.text}")
    exit(1)

print("\n✅ ALL TESTS PASSED!")
