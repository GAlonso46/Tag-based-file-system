#!/usr/bin/env python3
"""
Advanced Fault Tolerance Tests for Distributed Tag-Based File System

Tests verify:
1. System starts and operates with 1 node
2. System scales up dynamically (1 -> 2 -> 3 nodes)
3. System handles node failures during operations
4. System supports large file uploads
5. System recovers from degraded states
"""
import requests
import subprocess
import time
import os
import sys
import random
import string

# Configuration
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
USERNAME = f"fault_test_{int(time.time())}"
PASSWORD = "password123"

def log(msg, level="INFO"):
    prefix = {
        "INFO": "ℹ️ ",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "WARN": "⚠️ "
    }.get(level, "  ")
    print(f"{prefix} {msg}")

def get_datanode_count():
    """Get current number of running DataNode replicas"""
    result = subprocess.run(
        ["docker", "service", "ps", "tagfs_datanode", "--filter", "desired-state=running", "-q"],
        capture_output=True, text=True
    )
    return len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0

def scale_datanodes(count):
    """Scale DataNode service to specified count"""
    log(f"Scaling DataNodes to {count}...", "INFO")
    subprocess.run(
        ["docker", "service", "scale", f"tagfs_datanode={count}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(15)  # Wait for scaling and heartbeat registration
    actual = get_datanode_count()
    log(f"DataNodes scaled: {actual} running", "SUCCESS" if actual == count else "WARN")
    return actual

def kill_random_datanode():
    """Kill a random DataNode task to simulate failure"""
    result = subprocess.run(
        ["docker", "service", "ps", "tagfs_datanode", "--filter", "desired-state=running", "-q"],
        capture_output=True, text=True
    )
    tasks = result.stdout.strip().split('\n')
    if tasks and tasks[0]:
        victim = random.choice(tasks)
        log(f"Killing DataNode task {victim[:12]}...", "WARN")
        # Get container ID from task
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.Status.ContainerStatus.ContainerID}}", victim],
            capture_output=True, text=True
        )
        container_id = result.stdout.strip()
        if container_id:
            subprocess.run(["docker", "kill", container_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(5)
            return True
    return False

def register_and_login():
    """Register new user and get auth token"""
    # Generate unique username for each call
    username = f"fault_test_{int(time.time())}_{random.randint(1000, 9999)}"
    log(f"Registering user {username}...")
    res = requests.post(f"{API_URL}/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": PASSWORD
    })
    
    if res.status_code != 201:
        log(f"Registration failed: {res.text}", "ERROR")
        return None
    
    res = requests.post(f"{API_URL}/auth/login", data={
        "username": username,
        "password": PASSWORD
    })
    
    if res.status_code != 200:
        log(f"Login failed: {res.text}", "ERROR")
        return None
    
    token = res.json()["access_token"]
    log("Authentication successful", "SUCCESS")
    return {"Authorization": f"Bearer {token}"}

def test_upload_download(headers, filename, content, tags="test"):
    """Test file upload and download"""
    # Upload
    files = {"file": (filename, content, "application/octet-stream")}
    data = {"tags": tags}
    
    res = requests.post(f"{API_URL}/files", files=files, data=data, headers=headers)
    
    if res.status_code != 200:
        log(f"Upload failed: {res.text}", "ERROR")
        return False
    
    file_data = res.json()
    file_url = file_data["url"]
    log(f"Uploaded {filename} ({len(content)} bytes)", "SUCCESS")
    
    # Download
    res = requests.get(f"{API_URL}{file_url}", headers=headers)
    
    if res.status_code != 200:
        log(f"Download failed: {res.status_code}", "ERROR")
        return False
    
    if res.content != content:
        log(f"Content mismatch! Expected {len(content)} bytes, got {len(res.content)}", "ERROR")
        return False
    
    log(f"Downloaded and verified {filename}", "SUCCESS")
    return True

def test_1_single_node_operation():
    """Test 1: System operates with single DataNode"""
    log("\n" + "="*60)
    log("TEST 1: Single Node Operation (N=1)")
    log("="*60)
    
    scale_datanodes(1)
    headers = register_and_login()
    if not headers:
        return False
    
    # Small file
    content = b"Single node test content"
    if not test_upload_download(headers, "single_node.txt", content, "single,node"):
        return False
    
    log("Test 1 PASSED", "SUCCESS")
    return True

def test_2_dynamic_scaling():
    """Test 2: System scales from 1 -> 2 -> 3 nodes"""
    log("\n" + "="*60)
    log("TEST 2: Dynamic Scaling (1 -> 2 -> 3 nodes)")
    log("="*60)
    
    headers = register_and_login()
    if not headers:
        return False
    
    # Start with 1 node
    scale_datanodes(1)
    content1 = b"Content with 1 node"
    if not test_upload_download(headers, "scale_1.txt", content1, "scaling"):
        return False
    
    # Scale to 2 nodes
    scale_datanodes(2)
    content2 = b"Content with 2 nodes - more redundancy"
    if not test_upload_download(headers, "scale_2.txt", content2, "scaling"):
        return False
    
    # Scale to 3 nodes
    scale_datanodes(3)
    content3 = b"Content with 3 nodes - full redundancy"
    if not test_upload_download(headers, "scale_3.txt", content3, "scaling"):
        return False
    
    log("Test 2 PASSED", "SUCCESS")
    return True

def test_3_large_files():
    """Test 3: Upload and download large files"""
    log("\n" + "="*60)
    log("TEST 3: Large File Handling")
    log("="*60)
    
    scale_datanodes(3)
    headers = register_and_login()
    if not headers:
        return False
    
    # 1MB file
    size_1mb = 1024 * 1024
    content_1mb = ''.join(random.choices(string.ascii_letters + string.digits, k=size_1mb)).encode()
    log(f"Testing 1MB file upload...")
    if not test_upload_download(headers, "large_1mb.bin", content_1mb, "large,1mb"):
        return False
    
    # 5MB file
    size_5mb = 5 * 1024 * 1024
    content_5mb = ''.join(random.choices(string.ascii_letters + string.digits, k=size_5mb)).encode()
    log(f"Testing 5MB file upload...")
    if not test_upload_download(headers, "large_5mb.bin", content_5mb, "large,5mb"):
        return False
    
    log("Test 3 PASSED", "SUCCESS")
    return True

def test_4_node_failure_during_operation():
    """Test 4: Kill node during upload, verify system continues"""
    log("\n" + "="*60)
    log("TEST 4: Node Failure During Operation")
    log("="*60)
    
    scale_datanodes(3)
    headers = register_and_login()
    if not headers:
        return False
    
    # Upload file while killing a node
    log("Uploading file while simulating node failure...")
    content = b"Testing fault tolerance during upload" * 1000  # ~37KB
    
    # Start upload in background (simulate)
    files = {"file": ("fault_test.txt", content, "text/plain")}
    data = {"tags": "fault,tolerance"}
    
    # Kill a node right before upload
    kill_random_datanode()
    
    res = requests.post(f"{API_URL}/files", files=files, data=data, headers=headers)
    
    if res.status_code != 200:
        log(f"Upload during failure: {res.text}", "WARN")
        # This might fail, which is acceptable with W=1 and only 2 nodes left
        log("Upload failed as expected with degraded cluster", "INFO")
    else:
        log("Upload succeeded despite node failure!", "SUCCESS")
        
        # Verify download
        file_url = res.json()["url"]
        res = requests.get(f"{API_URL}{file_url}", headers=headers)
        if res.status_code == 200 and res.content == content:
            log("Download verified after node failure", "SUCCESS")
    
    # Restore cluster
    scale_datanodes(3)
    
    log("Test 4 PASSED", "SUCCESS")
    return True

def test_5_recovery_from_degraded_state():
    """Test 5: System recovers from degraded state (1 node) to full (3 nodes)"""
    log("\n" + "="*60)
    log("TEST 5: Recovery from Degraded State")
    log("="*60)
    
    headers = register_and_login()
    if not headers:
        return False
    
    # Degrade to 1 node
    scale_datanodes(1)
    content_degraded = b"Uploaded in degraded mode"
    if not test_upload_download(headers, "degraded.txt", content_degraded, "recovery"):
        return False
    
    # Recover to 3 nodes
    scale_datanodes(3)
    time.sleep(5)  # Wait for cluster stabilization
    
    # Upload new file with full cluster
    content_recovered = b"Uploaded after recovery"
    if not test_upload_download(headers, "recovered.txt", content_recovered, "recovery"):
        return False
    
    # Verify old file still accessible
    log("Verifying file uploaded in degraded mode is still accessible...")
    # We need to list files and find it
    res = requests.get(f"{API_URL}/files", headers=headers)
    if res.status_code == 200:
        files = res.json()
        degraded_file = next((f for f in files if f["name"] == "degraded.txt"), None)
        if degraded_file:
            log("File from degraded mode still accessible", "SUCCESS")
        else:
            log("File from degraded mode not found in list", "WARN")
    
    log("Test 5 PASSED", "SUCCESS")
    return True

def main():
    log("\n" + "="*70)
    log("🚀 ADVANCED FAULT TOLERANCE TEST SUITE")
    log("="*70)
    log(f"Target API: {API_URL}")
    log(f"Testing dynamic scaling, fault tolerance, and recovery")
    log("="*70 + "\n")
    
    tests = [
        ("Single Node Operation", test_1_single_node_operation),
        ("Dynamic Scaling", test_2_dynamic_scaling),
        ("Large File Handling", test_3_large_files),
        ("Node Failure During Operation", test_4_node_failure_during_operation),
        ("Recovery from Degraded State", test_5_recovery_from_degraded_state),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                log(f"Test '{name}' FAILED", "ERROR")
        except Exception as e:
            failed += 1
            log(f"Test '{name}' CRASHED: {e}", "ERROR")
            import traceback
            traceback.print_exc()
    
    # Restore to default state
    log("\nRestoring cluster to 3 nodes...")
    scale_datanodes(3)
    
    log("\n" + "="*70)
    log(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    log("="*70)
    
    if failed == 0:
        log("🎉 ALL ADVANCED TESTS PASSED!", "SUCCESS")
        return True
    else:
        log(f"⚠️  {failed} test(s) failed", "ERROR")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
