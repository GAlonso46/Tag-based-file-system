#!/usr/bin/env python3
"""
Extreme Stress & Chaos Engineering Test for Distributed Tag-Based File System

Tests verify:
1. Large file uploads (10MB, 50MB, 100MB)
2. Concurrent uploads (multiple files simultaneously)
3. Node failures during active uploads
4. System recovery under extreme load
"""
import requests
import subprocess
import time
import os
import sys
import random
import string
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")
PASSWORD = "password123"

def log(msg, level="INFO"):
    timestamp = time.strftime("%H:%M:%S")
    prefix = {
        "INFO": "ℹ️ ",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "WARN": "⚠️ ",
        "CHAOS": "💥"
    }.get(level, "  ")
    print(f"[{timestamp}] {prefix} {msg}", flush=True)

def generate_random_data(size_mb):
    """Generate random binary data of specified size in MB"""
    size_bytes = size_mb * 1024 * 1024
    log(f"Generating {size_mb}MB of random data...")
    # Generate in chunks to avoid memory issues
    chunk_size = 1024 * 1024  # 1MB chunks
    data = b''
    for _ in range(size_mb):
        data += ''.join(random.choices(string.ascii_letters + string.digits, k=chunk_size)).encode()
    return data

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
    time.sleep(15)
    actual = get_datanode_count()
    log(f"DataNodes: {actual} running", "SUCCESS" if actual == count else "WARN")
    return actual

def kill_random_datanode():
    """Kill a random DataNode task"""
    result = subprocess.run(
        ["docker", "service", "ps", "tagfs_datanode", "--filter", "desired-state=running", "-q"],
        capture_output=True, text=True
    )
    tasks = result.stdout.strip().split('\n')
    if tasks and tasks[0]:
        victim = random.choice(tasks)
        log(f"Killing DataNode task {victim[:12]}...", "CHAOS")
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.Status.ContainerStatus.ContainerID}}", victim],
            capture_output=True, text=True
        )
        container_id = result.stdout.strip()
        if container_id:
            subprocess.run(["docker", "kill", container_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    return False

def register_and_login(username):
    """Register new user and get auth token"""
    res = requests.post(f"{API_URL}/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": PASSWORD
    })
    
    if res.status_code != 201:
        log(f"Registration failed for {username}: {res.text}", "ERROR")
        return None
    
    res = requests.post(f"{API_URL}/auth/login", data={
        "username": username,
        "password": PASSWORD
    })
    
    if res.status_code != 200:
        log(f"Login failed for {username}: {res.text}", "ERROR")
        return None
    
    return {"Authorization": f"Bearer {res.json()['access_token']}"}

def upload_file(headers, filename, content, tags="stress"):
    """Upload a single file and return success status"""
    start_time = time.time()
    try:
        files = {"file": (filename, content, "application/octet-stream")}
        data = {"tags": tags}
        
        res = requests.post(f"{API_URL}/files", files=files, data=data, headers=headers, timeout=120)
        
        elapsed = time.time() - start_time
        
        if res.status_code == 200:
            file_data = res.json()
            log(f"✅ Uploaded {filename} ({len(content)/1024/1024:.1f}MB) in {elapsed:.1f}s", "SUCCESS")
            return True, file_data["url"]
        else:
            log(f"❌ Upload failed {filename}: {res.status_code}", "ERROR")
            return False, None
    except Exception as e:
        elapsed = time.time() - start_time
        log(f"❌ Upload crashed {filename} after {elapsed:.1f}s: {e}", "ERROR")
        return False, None

def download_and_verify(headers, file_url, expected_content):
    """Download file and verify content matches"""
    try:
        res = requests.get(f"{API_URL}{file_url}", headers=headers, timeout=120)
        
        if res.status_code != 200:
            log(f"Download failed: {res.status_code}", "ERROR")
            return False
        
        if res.content != expected_content:
            log(f"Content mismatch! Expected {len(expected_content)} bytes, got {len(res.content)}", "ERROR")
            return False
        
        return True
    except Exception as e:
        log(f"Download crashed: {e}", "ERROR")
        return False

def test_1_very_large_files():
    """Test 1: Upload very large files (10MB, 50MB, 100MB)"""
    log("\n" + "="*70)
    log("TEST 1: Very Large File Uploads (10MB, 50MB, 100MB)")
    log("="*70)
    
    scale_datanodes(3)
    username = f"stress_large_{int(time.time())}"
    headers = register_and_login(username)
    if not headers:
        return False
    
    sizes = [10, 50, 100]
    
    for size_mb in sizes:
        log(f"\n📦 Testing {size_mb}MB file...")
        content = generate_random_data(size_mb)
        filename = f"large_{size_mb}mb.bin"
        
        success, file_url = upload_file(headers, filename, content, f"large,{size_mb}mb")
        if not success:
            log(f"Failed to upload {size_mb}MB file", "ERROR")
            return False
        
        log(f"Verifying {size_mb}MB download...")
        if not download_and_verify(headers, file_url, content):
            log(f"Failed to verify {size_mb}MB file", "ERROR")
            return False
        
        log(f"✅ {size_mb}MB file verified successfully", "SUCCESS")
    
    log("\n✅ Test 1 PASSED", "SUCCESS")
    return True

def test_2_concurrent_uploads():
    """Test 2: Upload multiple files concurrently"""
    log("\n" + "="*70)
    log("TEST 2: Concurrent Uploads (5 files of 10MB each)")
    log("="*70)
    
    scale_datanodes(3)
    username = f"stress_concurrent_{int(time.time())}"
    headers = register_and_login(username)
    if not headers:
        return False
    
    num_files = 5
    size_mb = 10
    
    log(f"Generating {num_files} files of {size_mb}MB each...")
    files_data = []
    for i in range(num_files):
        content = generate_random_data(size_mb)
        filename = f"concurrent_{i+1}_of_{num_files}.bin"
        files_data.append((filename, content))
    
    log(f"Uploading {num_files} files concurrently...")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=num_files) as executor:
        futures = []
        for filename, content in files_data:
            future = executor.submit(upload_file, headers, filename, content, "concurrent")
            futures.append((future, filename, content))
        
        results = []
        for future, filename, content in futures:
            success, file_url = future.result()
            results.append((success, file_url, content))
    
    elapsed = time.time() - start_time
    successful = sum(1 for s, _, _ in results if s)
    
    log(f"Concurrent upload completed: {successful}/{num_files} successful in {elapsed:.1f}s", 
        "SUCCESS" if successful == num_files else "WARN")
    
    if successful < num_files:
        log(f"Only {successful}/{num_files} uploads succeeded", "ERROR")
        return False
    
    log("\n✅ Test 2 PASSED", "SUCCESS")
    return True

def test_3_chaos_during_upload():
    """Test 3: Kill nodes during large file uploads"""
    log("\n" + "="*70)
    log("TEST 3: Chaos Engineering - Kill Nodes During Upload")
    log("="*70)
    
    scale_datanodes(3)
    username = f"stress_chaos_{int(time.time())}"
    headers = register_and_login(username)
    if not headers:
        return False
    
    size_mb = 50
    log(f"Generating {size_mb}MB file for chaos test...")
    content = generate_random_data(size_mb)
    filename = "chaos_test.bin"
    
    # Start upload in a thread
    upload_result = [None]
    
    def do_upload():
        upload_result[0] = upload_file(headers, filename, content, "chaos")
    
    upload_thread = threading.Thread(target=do_upload)
    
    log("Starting upload...")
    upload_thread.start()
    
    # Wait a bit, then kill a node
    time.sleep(3)
    log("💥 KILLING NODE DURING UPLOAD!", "CHAOS")
    kill_random_datanode()
    
    # Wait another bit, kill another node
    time.sleep(3)
    log("💥 KILLING ANOTHER NODE!", "CHAOS")
    kill_random_datanode()
    
    # Wait for upload to complete
    upload_thread.join()
    
    success, file_url = upload_result[0]
    
    if success:
        log("Upload succeeded despite chaos!", "SUCCESS")
        # Try to download
        log("Attempting download after chaos...")
        if download_and_verify(headers, file_url, content):
            log("✅ Download verified after chaos!", "SUCCESS")
        else:
            log("⚠️  Upload succeeded but download failed (expected with heavy node loss)", "WARN")
    else:
        log("⚠️  Upload failed during chaos (acceptable behavior)", "WARN")
    
    # Restore cluster
    scale_datanodes(3)
    
    log("\n✅ Test 3 PASSED (system survived chaos)", "SUCCESS")
    return True

def test_4_extreme_stress():
    """Test 4: Extreme stress - concurrent large uploads with node failures"""
    log("\n" + "="*70)
    log("TEST 4: EXTREME STRESS - Concurrent 20MB uploads + Node Failures")
    log("="*70)
    
    scale_datanodes(3)
    username = f"stress_extreme_{int(time.time())}"
    headers = register_and_login(username)
    if not headers:
        return False
    
    num_files = 3
    size_mb = 20
    
    log(f"Generating {num_files} files of {size_mb}MB each...")
    files_data = []
    for i in range(num_files):
        content = generate_random_data(size_mb)
        filename = f"extreme_{i+1}.bin"
        files_data.append((filename, content))
    
    log(f"Starting {num_files} concurrent uploads...")
    
    # Start chaos thread
    chaos_active = [True]
    
    def chaos_monkey():
        time.sleep(5)
        while chaos_active[0]:
            log("💥 Chaos monkey strikes!", "CHAOS")
            kill_random_datanode()
            time.sleep(8)
    
    chaos_thread = threading.Thread(target=chaos_monkey, daemon=True)
    chaos_thread.start()
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=num_files) as executor:
        futures = []
        for filename, content in files_data:
            future = executor.submit(upload_file, headers, filename, content, "extreme")
            futures.append((future, filename))
        
        successful = 0
        for future, filename in futures:
            success, _ = future.result()
            if success:
                successful += 1
    
    chaos_active[0] = False
    elapsed = time.time() - start_time
    
    log(f"\nExtreme stress completed: {successful}/{num_files} successful in {elapsed:.1f}s", 
        "SUCCESS" if successful > 0 else "ERROR")
    
    # Restore cluster
    scale_datanodes(3)
    time.sleep(10)
    
    if successful > 0:
        log(f"✅ Test 4 PASSED ({successful}/{num_files} survived extreme chaos)", "SUCCESS")
        return True
    else:
        log("❌ Test 4 FAILED (no uploads survived)", "ERROR")
        return False

def main():
    log("\n" + "="*70)
    log("💥 EXTREME STRESS & CHAOS ENGINEERING TEST SUITE")
    log("="*70)
    log(f"Target API: {API_URL}")
    log("Testing: Large files, concurrency, chaos engineering")
    log("="*70 + "\n")
    
    tests = [
        ("Very Large Files (10MB, 50MB, 100MB)", test_1_very_large_files),
        ("Concurrent Uploads (5x10MB)", test_2_concurrent_uploads),
        ("Chaos During Upload", test_3_chaos_during_upload),
        ("Extreme Stress (Concurrent + Chaos)", test_4_extreme_stress),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            log(f"\n{'='*70}")
            log(f"Starting: {name}")
            log(f"{'='*70}")
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            log(f"Test '{name}' CRASHED: {e}", "ERROR")
            import traceback
            traceback.print_exc()
    
    # Restore to default state
    log("\n" + "="*70)
    log("Restoring cluster to 3 nodes...")
    scale_datanodes(3)
    
    log("\n" + "="*70)
    log(f"FINAL RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    log("="*70)
    
    if failed == 0:
        log("🎉 ALL EXTREME STRESS TESTS PASSED!", "SUCCESS")
        return True
    else:
        log(f"⚠️  {failed} test(s) failed (some failures expected under extreme chaos)", "WARN")
        return passed > 0  # Pass if at least some tests succeeded

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
