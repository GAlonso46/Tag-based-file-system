import os
import time
import sys
import subprocess
import requests
import random
import string
import json

# Configuration
GATEWAY_URL = "http://localhost:8000"
USERNAME = f"tester_{int(time.time())}"
PASSWORD = "password123"
admin_token = None

def log(msg):
    print(f"[TEST] {msg}", flush=True)

def run_cmd(cmd):
    return subprocess.check_output(cmd, shell=True).decode('utf-8').strip()

def get_container_id(service_name_filter):
    """Get a list of container IDs for a given service filter"""
    cmd = f"docker ps --format '{{{{.ID}}}} {{{{.Names}}}}' | grep '{service_name_filter}' | awk '{{print $1}}'"
    ids = run_cmd(cmd).split('\n')
    return [i for i in ids if i]

def wait_for_service(retries=30, delay=2):
    log("Waiting for Gateway to be ready...")
    for i in range(retries):
        try:
            resp = requests.get(f"{GATEWAY_URL}/")
            if resp.status_code == 200:
                log("Gateway is ready!")
                return True
        except:
            pass
        time.sleep(delay)
    log("Gateway timed out!")
    return False

def register_and_login():
    global admin_token
    log(f"Registering user {USERNAME}...")
    
    # Register
    reg_data = {
        "username": USERNAME,
        "email": f"{USERNAME}@test.com",
        "password": PASSWORD
    }
    resp = requests.post(f"{GATEWAY_URL}/auth/register", json=reg_data)
    if resp.status_code not in [200, 201]:
        log(f"Registration failed: {resp.text}")
        return False
    
    # Login
    login_data = {"username": USERNAME, "password": PASSWORD}
    resp = requests.post(f"{GATEWAY_URL}/auth/login-json", json=login_data)
    if resp.status_code != 200:
        log(f"Login failed: {resp.text}")
        return False
    
    admin_token = resp.json()["access_token"]
    log(f"Logged in! Token: {admin_token[:10]}...")
    return True

def upload_file(filename, content, tags="test"):
    headers = {"Authorization": f"Bearer {admin_token}"}
    files = {'file': (filename, content)}
    data = {'tags': tags}
    
    log(f"Uploading {filename} ({len(content)} bytes)...")
    start = time.time()
    resp = requests.post(f"{GATEWAY_URL}/files", headers=headers, files=files, data=data)
    duration = time.time() - start
    
    if resp.status_code == 200:
        file_id = resp.json().get("url").split("/")[-1]
        log(f"Upload successful in {duration:.2f}s! File ID: {file_id}")
        return file_id
    else:
        log(f"Upload failed: {resp.text}")
        return None

def download_file(file_id, expected_content):
    headers = {"Authorization": f"Bearer {admin_token}"}
    log(f"Downloading file {file_id}...")
    
    start = time.time()
    resp = requests.get(f"{GATEWAY_URL}/files/{file_id}", headers=headers)
    duration = time.time() - start
    
    if resp.status_code == 200:
        content = resp.content
        if content == expected_content:
            log(f"Download successful in {duration:.2f}s! Content verified.")
            return True
        else:
            log(f"Download verified FAILED! Content mismatch.")
            log(f"Expected ({len(expected_content)}): {expected_content}")
            log(f"Received ({len(content)}): {content[:100]}")
            return False
    else:
        log(f"Download failed: {resp.status_code} {resp.text}")
        return False

def test_datanode_failure():
    log("\n=== TEST: DataNode Failure Tolerance ===")
    
    # 1. Upload a file
    content = b"DataNode reliability test content " + os.urandom(1024*10) # 10KB
    file_id = upload_file("resilience_test.bin", content, "resilience")
    if not file_id: return False
    
    # 2. Kill a DataNode
    datanodes = get_container_id("tagfs_datanode")
    if not datanodes:
        log("No DataNodes found!")
        return False
    
    victim = datanodes[0]
    log(f"Killing DataNode container: {victim}")
    run_cmd(f"docker kill {victim}")
    
    time.sleep(2) # Give a moment for connection drop
    
    # 3. Try to download (Should work via Quorum R=2)
    log("Attempting download with 1 DataNode down...")
    success = download_file(file_id, content)
    
    if success:
        log("PASS: System survived DataNode failure.")
    else:
        log("FAIL: System failed to serve file after DataNode failure.")
    
    # 4. Wait for Swarm to restart it (Self-healing)
    log("Waiting for Swarm to restart DataNode (approx 10-15s)...")
    time.sleep(15)
    current_nodes = get_container_id("tagfs_datanode")
    if len(current_nodes) >= 3:
         log("PASS: DataNode automatically restarted.")
    else:
         log(f"WARNING: DataNode count is {len(current_nodes)}, swarm might be slow.")
         
    return success

def test_metadata_leader_failure():
    log("\n=== TEST: Metadata Leader Election (Bully) ===")
    
    # We can't easily know who is leader from outside without querying logs or special endpoint.
    # But we can kill a random metadata node. If it was leader, election happens. If follower, nothing bad happens.
    # To be sure, we might need to kill 2 out of 3? Or just kill one and see if write still works.
    
    # 1. Upload file (Base check)
    log("Base upload check...")
    if not upload_file("pre_kill.txt", b"check", "check"): return False
    
    # 2. Kill a Metadata Node
    metadata_nodes = get_container_id("tagfs_metadata")
    if not metadata_nodes: return False
    
    victim = metadata_nodes[0]
    log(f"Killing Metadata Node: {victim}")
    run_cmd(f"docker kill {victim}")
    
    time.sleep(5) # Allow Bully election (timeout is usually 5-10s)
    
    # 3. Attempt Write Operation (requires Leader)
    log("Attempting upload after Metadata failure (expecting new leader or survivor)...")
    content = b"Post-election content"
    file_id = upload_file("post_kill.txt", content, "election")
    
    if file_id:
        log("PASS: Write operation successful after Metadata node failure.")
        return True
    else:
        log("FAIL: Write operation failed. Leader election exceeded timeout or failed.")
        return False

def main():
    log("Starting Robustness Check...")
    
    if not wait_for_service():
        sys.exit(1)
        
    if not register_and_login():
        sys.exit(1)
        
    # Basic Test
    log("\n=== TEST: Basic IO ===")
    content = b"Hello Distributed World"
    fid = upload_file("hello.txt", content, "intro")
    if not fid or not download_file(fid, content):
        log("Basic IO Failed!")
        sys.exit(1)
    log("PASS: Basic IO")
    
    # Fault Tolerance Tests
    if not test_datanode_failure():
        log("DataNode Failure Test FAILED")
        # Don't exit, try next
        
    if not test_metadata_leader_failure():
        log("Metadata Failure Test FAILED")
    
    log("\n=== Robustness Check Complete ===")

if __name__ == "__main__":
    main()
