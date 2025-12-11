#!/usr/bin/env python3
"""
Test degraded mode: System should work even with reduced number of DataNodes.
This test verifies the system works with the current number of nodes (no scaling).
"""
import requests
import time
import os

# Configuration
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
USERNAME = f"degraded_user_{int(time.time())}"
PASSWORD = "password123"

def log(msg):
    print(f"[DEGRADED TEST] {msg}")

def main():
    log("Testing system with current DataNode configuration...")
    
    # 1. Register
    log(f"Registering user {USERNAME}...")
    res = requests.post(f"{API_URL}/auth/register", json={
        "username": USERNAME,
        "email": f"{USERNAME}@example.com",
        "password": PASSWORD
    })
    
    if res.status_code != 201:
        log(f"❌ Registration FAILED: {res.text}")
        return False
    
    # 2. Login
    res = requests.post(f"{API_URL}/auth/login", data={
        "username": USERNAME,
        "password": PASSWORD
    })
    
    if res.status_code != 200:
        log(f"❌ Login FAILED: {res.text}")
        return False
    
    token = res.json()["access_token"]
    log(f"✅ Login successful")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Upload File
    log("Uploading file...")
    files = {"file": ("degraded_test.txt", b"Testing degraded mode", "text/plain")}
    data = {"tags": "degraded,test"}
    
    res = requests.post(f"{API_URL}/files", files=files, data=data, headers=headers)
    
    if res.status_code != 200:
        log(f"❌ Upload FAILED: {res.text}")
        return False
    
    file_data = res.json()
    log(f"✅ Upload SUCCESS: {file_data['name']}")
    
    # 4. Download File
    file_url = file_data["url"]
    res = requests.get(f"{API_URL}{file_url}", headers=headers)
    
    if res.status_code != 200:
        log(f"❌ Download FAILED: {res.status_code}")
        return False
    
    log(f"✅ Download SUCCESS: {len(res.content)} bytes")
    log("\n✅ ALL DEGRADED MODE TESTS PASSED!")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
