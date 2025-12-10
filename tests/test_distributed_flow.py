import requests
import sys
import os
import time

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")
USERNAME = f"testuser_{int(time.time())}"
PASSWORD = "password123"
EMAIL = f"{USERNAME}@example.com"

def log(msg):
    print(f"[TEST] {msg}")

def test_flow():
    session = requests.Session()
    
    # 1. Register
    log(f"Registering user {USERNAME}...")
    res = session.post(f"{API_URL}/auth/register", json={
        "username": USERNAME,
        "email": EMAIL,
        "password": PASSWORD
    })
    if res.status_code != 201:
        log(f"Registration failed: {res.text}")
        sys.exit(1)
        
    # 2. Login
    log("Logging in...")
    res = session.post(f"{API_URL}/auth/login", data={
        "username": USERNAME,
        "password": PASSWORD
    })
    if res.status_code != 200:
        log(f"Login failed: {res.text}")
        sys.exit(1)
    
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Upload File
    filename = "test_distributed.txt"
    content = b"Hello Distributed World! This is a test file."
    
    log("Uploading file...")
    files = {"file": (filename, content, "text/plain")}
    data = {"tags": "test,distributed,python"}
    
    res = session.post(f"{API_URL}/files", files=files, data=data, headers=headers)
    if res.status_code != 200:
        log(f"Upload failed: {res.text}")
        sys.exit(1)
    
    file_info = res.json()
    file_id = file_info["url"].split("/")[-1]
    log(f"Upload success! File ID: {file_id}")
    
    # 4. List Files
    log("Listing files...")
    res = session.get(f"{API_URL}/files", headers=headers)
    if res.status_code != 200:
        log(f"List failed: {res.text}")
        sys.exit(1)
        
    file_list = res.json()
    found = False
    for f in file_list:
        if f["name"] == filename:
            found = True
            log(f"Found file in list: {f}")
            break
            
    if not found:
        log("File not found in list!")
        sys.exit(1)
        
    # 5. Download File
    log(f"Downloading file {file_id}...")
    # Wait a bit for propagation if eventually consistent (not needed for quorum but good practice)
    time.sleep(1) 
    
    res = session.get(f"{API_URL}/files/{file_id}", headers=headers)
    if res.status_code != 200:
        log(f"Download failed: {res.text}")
        sys.exit(1)
        
    if res.content == content:
        log("Download content matches original!")
    else:
        log(f"Content mismatch! Got: {res.content}")
        sys.exit(1)

    log("\n✅ ALL TESTS PASSED!")

if __name__ == "__main__":
    try:
        test_flow()
    except Exception as e:
        log(f"Test Crashed: {e}")
        sys.exit(1)
