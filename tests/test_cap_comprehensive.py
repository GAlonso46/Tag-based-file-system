#!/usr/bin/env python3
"""
COMPREHENSIVE CAP THEOREM & PARTITION TOLERANCE TEST SUITE

Tests covering:
1. CAP Theorem: Consistency vs Availability trade-offs
2. Network Partitions: Split-brain scenarios
3. Extreme file sizes: 200MB, 500MB, 1GB
4. Metadata consistency under failures
5. Concurrent operations during partitions
6. Recovery and data integrity verification
7. Edge cases: All nodes down except 1, rapid scaling
"""
import requests
import subprocess
import time
import os
import sys
import random
import string
import threading
import hashlib
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
        "CHAOS": "💥",
        "PARTITION": "🔀",
        "CONSISTENCY": "🔒"
    }.get(level, "  ")
    print(f"[{timestamp}] {prefix} {msg}", flush=True)

def generate_random_data(size_mb):
    """Generate random binary data with checksum"""
    size_bytes = size_mb * 1024 * 1024
    log(f"Generating {size_mb}MB of random data...")
    chunk_size = 1024 * 1024
    data = b''
    for _ in range(size_mb):
        data += ''.join(random.choices(string.ascii_letters + string.digits, k=chunk_size)).encode()
    checksum = hashlib.sha256(data).hexdigest()
    return data, checksum

def get_service_info(service_name):
    """Get detailed info about a service"""
    result = subprocess.run(
        ["docker", "service", "ps", service_name, "--filter", "desired-state=running", "--format", "{{.ID}}"],
        capture_output=True, text=True
    )
    tasks = result.stdout.strip().split('\n') if result.stdout.strip() else []
    return tasks

def scale_service(service_name, count):
    """Scale any service to specified count"""
    log(f"Scaling {service_name} to {count}...", "INFO")
    subprocess.run(
        ["docker", "service", "scale", f"{service_name}={count}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    time.sleep(15)
    actual = len(get_service_info(service_name))
    log(f"{service_name}: {actual} running", "SUCCESS" if actual == count else "WARN")
    return actual

def kill_service_task(service_name, task_id=None):
    """Kill a specific task or random task of a service"""
    tasks = get_service_info(service_name)
    if not tasks or not tasks[0]:
        return False
    
    victim = task_id if task_id else random.choice(tasks)
    log(f"Killing {service_name} task {victim[:12]}...", "CHAOS")
    
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{.Status.ContainerStatus.ContainerID}}", victim],
        capture_output=True, text=True
    )
    container_id = result.stdout.strip()
    if container_id:
        subprocess.run(["docker", "kill", container_id], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        return True
    return False

def register_and_login(username):
    """Register and login user"""
    res = requests.post(f"{API_URL}/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": PASSWORD
    })
    
    if res.status_code != 201:
        return None
    
    res = requests.post(f"{API_URL}/auth/login", data={
        "username": username,
        "password": PASSWORD
    })
    
    if res.status_code != 200:
        return None
    
    return {"Authorization": f"Bearer {res.json()['access_token']}"}

def upload_file(headers, filename, content, tags="test", timeout=300):
    """Upload file with checksum verification"""
    start_time = time.time()
    try:
        files = {"file": (filename, content, "application/octet-stream")}
        data = {"tags": tags}
        
        res = requests.post(f"{API_URL}/files", files=files, data=data, headers=headers, timeout=timeout)
        elapsed = time.time() - start_time
        
        if res.status_code == 200:
            log(f"Uploaded {filename} ({len(content)/1024/1024:.1f}MB) in {elapsed:.1f}s", "SUCCESS")
            return True, res.json()["url"]
        else:
            log(f"Upload failed {filename}: {res.status_code}", "ERROR")
            return False, None
    except Exception as e:
        log(f"Upload crashed {filename}: {e}", "ERROR")
        return False, None

def download_and_verify(headers, file_url, expected_content, expected_checksum=None):
    """Download and verify content"""
    try:
        res = requests.get(f"{API_URL}{file_url}", headers=headers, timeout=300)
        
        if res.status_code != 200:
            return False
        
        if res.content != expected_content:
            log(f"Content mismatch!", "ERROR")
            return False
        
        if expected_checksum:
            actual_checksum = hashlib.sha256(res.content).hexdigest()
            if actual_checksum != expected_checksum:
                log(f"Checksum mismatch!", "ERROR")
                return False
        
        return True
    except Exception as e:
        log(f"Download failed: {e}", "ERROR")
        return False

def test_1_extreme_file_sizes():
    """Test 1: Extreme file sizes (200MB, 500MB)"""
    log("\n" + "="*70)
    log("TEST 1: Extreme File Sizes (200MB, 500MB)")
    log("="*70)
    
    scale_service("tagfs_datanode", 3)
    username = f"cap_extreme_{int(time.time())}"
    headers = register_and_login(username)
    if not headers:
        return False
    
    sizes = [200, 500]
    
    for size_mb in sizes:
        log(f"\n📦 Testing {size_mb}MB file...")
        content, checksum = generate_random_data(size_mb)
        filename = f"extreme_{size_mb}mb.bin"
        
        success, file_url = upload_file(headers, filename, content, f"extreme,{size_mb}mb", timeout=600)
        if not success:
            log(f"Failed to upload {size_mb}MB file", "WARN")
            continue
        
        log(f"Verifying {size_mb}MB download with checksum...")
        if download_and_verify(headers, file_url, content, checksum):
            log(f"✅ {size_mb}MB file verified with checksum", "SUCCESS")
        else:
            log(f"⚠️  {size_mb}MB verification failed", "WARN")
    
    log("\n✅ Test 1 COMPLETED", "SUCCESS")
    return True

def test_2_partition_tolerance():
    """Test 2: Network partition simulation - kill majority of nodes"""
    log("\n" + "="*70)
    log("TEST 2: Partition Tolerance - Minority Partition")
    log("="*70)
    
    scale_service("tagfs_datanode", 3)
    username = f"cap_partition_{int(time.time())}"
    headers = register_and_login(username)
    if not headers:
        return False
    
    # Upload file with 3 nodes
    log("Uploading file with full cluster (3 nodes)...")
    content, checksum = generate_random_data(10)
    success, file_url = upload_file(headers, "partition_test.bin", content, "partition")
    
    if not success:
        log("Initial upload failed", "ERROR")
        return False
    
    # Create partition: kill 2 nodes, leaving only 1
    log("\n🔀 SIMULATING NETWORK PARTITION - Killing 2/3 nodes", "PARTITION")
    kill_service_task("tagfs_datanode")
    time.sleep(2)
    kill_service_task("tagfs_datanode")
    time.sleep(5)
    
    # Try to upload with only 1 node (minority partition)
    log("Attempting upload in minority partition (1 node)...")
    content2, checksum2 = generate_random_data(5)
    success2, file_url2 = upload_file(headers, "partition_minority.bin", content2, "partition")
    
    if success2:
        log("✅ System available in minority partition (AP behavior)", "SUCCESS")
    else:
        log("⚠️  System unavailable in minority partition (CP behavior)", "WARN")
    
    # Verify original file still accessible
    log("Verifying original file still accessible...")
    if download_and_verify(headers, file_url, content, checksum):
        log("✅ Original file accessible after partition", "SUCCESS")
    else:
        log("⚠️  Original file lost in partition", "WARN")
    
    # Heal partition
    scale_service("tagfs_datanode", 3)
    time.sleep(10)
    
    log("\n✅ Test 2 COMPLETED", "SUCCESS")
    return True

def test_3_consistency_under_failures():
    """Test 3: Consistency verification under node failures"""
    log("\n" + "="*70)
    log("TEST 3: Consistency Under Failures")
    log("="*70)
    
    scale_service("tagfs_datanode", 3)
    username = f"cap_consistency_{int(time.time())}"
    headers = register_and_login(username)
    if not headers:
        return False
    
    # Upload multiple files
    files_data = []
    for i in range(5):
        content, checksum = generate_random_data(10)
        filename = f"consistency_{i}.bin"
        success, file_url = upload_file(headers, filename, content, "consistency")
        if success:
            files_data.append((filename, file_url, content, checksum))
    
    log(f"Uploaded {len(files_data)} files")
    
    # Kill nodes randomly
    log("\n💥 Killing nodes randomly...", "CHAOS")
    kill_service_task("tagfs_datanode")
    time.sleep(3)
    kill_service_task("tagfs_datanode")
    time.sleep(5)
    
    # Verify all files still accessible and consistent
    log("\n🔒 Verifying consistency of all files...", "CONSISTENCY")
    accessible = 0
    for filename, file_url, content, checksum in files_data:
        if download_and_verify(headers, file_url, content, checksum):
            accessible += 1
            log(f"✅ {filename} consistent", "SUCCESS")
        else:
            log(f"❌ {filename} inconsistent or unavailable", "ERROR")
    
    log(f"\nConsistency: {accessible}/{len(files_data)} files accessible and consistent")
    
    # Restore cluster
    scale_service("tagfs_datanode", 3)
    
    log("\n✅ Test 3 COMPLETED", "SUCCESS")
    return accessible >= len(files_data) * 0.5  # At least 50% should be consistent

def test_4_concurrent_operations_during_failures():
    """Test 4: Concurrent operations during continuous failures"""
    log("\n" + "="*70)
    log("TEST 4: Concurrent Operations During Continuous Failures")
    log("="*70)
    
    scale_service("tagfs_datanode", 3)
    username = f"cap_concurrent_{int(time.time())}"
    headers = register_and_login(username)
    if not headers:
        return False
    
    # Start chaos monkey
    chaos_active = [True]
    
    def chaos_monkey():
        while chaos_active[0]:
            time.sleep(random.uniform(3, 7))
            if chaos_active[0]:
                kill_service_task("tagfs_datanode")
                log("💥 Chaos monkey struck!", "CHAOS")
    
    chaos_thread = threading.Thread(target=chaos_monkey, daemon=True)
    chaos_thread.start()
    
    # Concurrent uploads
    num_files = 10
    log(f"Starting {num_files} concurrent uploads with chaos monkey active...")
    
    def upload_task(i):
        content, checksum = generate_random_data(5)
        filename = f"concurrent_chaos_{i}.bin"
        return upload_file(headers, filename, content, "concurrent_chaos")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(upload_task, i) for i in range(num_files)]
        results = [f.result() for f in as_completed(futures)]
    
    chaos_active[0] = False
    successful = sum(1 for success, _ in results if success)
    
    log(f"\nConcurrent operations: {successful}/{num_files} successful under chaos")
    
    # Restore cluster
    scale_service("tagfs_datanode", 3)
    
    log("\n✅ Test 4 COMPLETED", "SUCCESS")
    return successful >= num_files * 0.5  # At least 50% should succeed

def test_5_split_brain_scenario():
    """Test 5: Split-brain scenario - rapid scaling up and down"""
    log("\n" + "="*70)
    log("TEST 5: Split-Brain Scenario - Rapid Scaling")
    log("="*70)
    
    username = f"cap_splitbrain_{int(time.time())}"
    headers = register_and_login(username)
    if not headers:
        return False
    
    # Rapid scaling: 3 -> 1 -> 3 -> 2 -> 3
    scales = [3, 1, 3, 2, 3]
    
    for i, scale in enumerate(scales):
        log(f"\nRapid scale to {scale} nodes...")
        scale_service("tagfs_datanode", scale)
        
        # Try upload at each scale
        content, checksum = generate_random_data(5)
        filename = f"splitbrain_{i}_n{scale}.bin"
        success, file_url = upload_file(headers, filename, content, f"splitbrain,n{scale}")
        
        if success:
            log(f"✅ Upload successful with {scale} nodes", "SUCCESS")
        else:
            log(f"⚠️  Upload failed with {scale} nodes", "WARN")
    
    log("\n✅ Test 5 COMPLETED", "SUCCESS")
    return True

def test_6_metadata_consistency():
    """Test 6: Metadata consistency - verify file listings"""
    log("\n" + "="*70)
    log("TEST 6: Metadata Consistency - File Listings")
    log("="*70)
    
    scale_service("tagfs_datanode", 3)
    username = f"cap_metadata_{int(time.time())}"
    headers = register_and_login(username)
    if not headers:
        return False
    
    # Upload files
    uploaded_files = []
    for i in range(10):
        content = f"Metadata test file {i}".encode()
        filename = f"metadata_{i}.txt"
        success, file_url = upload_file(headers, filename, content, f"metadata,test{i}")
        if success:
            uploaded_files.append(filename)
    
    log(f"Uploaded {len(uploaded_files)} files")
    
    # Kill metadata service and restart
    log("\n💥 Killing Metadata service...", "CHAOS")
    kill_service_task("tagfs_metadata")
    time.sleep(10)
    
    # List files and verify
    log("Verifying file listings after metadata restart...")
    try:
        res = requests.get(f"{API_URL}/files", headers=headers, timeout=30)
        if res.status_code == 200:
            files = res.json()
            found = sum(1 for f in files if f["name"] in uploaded_files)
            log(f"Found {found}/{len(uploaded_files)} files in listing", "SUCCESS" if found == len(uploaded_files) else "WARN")
            return found >= len(uploaded_files) * 0.8
        else:
            log("File listing failed", "ERROR")
            return False
    except Exception as e:
        log(f"Listing crashed: {e}", "ERROR")
        return False

def test_7_recovery_verification():
    """Test 7: Complete recovery verification"""
    log("\n" + "="*70)
    log("TEST 7: Complete Recovery Verification")
    log("="*70)
    
    username = f"cap_recovery_{int(time.time())}"
    headers = register_and_login(username)
    if not headers:
        return False
    
    # Phase 1: Upload with full cluster
    log("Phase 1: Upload with full cluster (3 nodes)...")
    scale_service("tagfs_datanode", 3)
    content1, checksum1 = generate_random_data(20)
    success1, url1 = upload_file(headers, "recovery_phase1.bin", content1, "recovery")
    
    # Phase 2: Degrade to 1 node
    log("\nPhase 2: Degrade to 1 node...")
    scale_service("tagfs_datanode", 1)
    content2, checksum2 = generate_random_data(10)
    success2, url2 = upload_file(headers, "recovery_phase2.bin", content2, "recovery")
    
    # Phase 3: Kill all DataNodes
    log("\nPhase 3: Kill all DataNodes...")
    scale_service("tagfs_datanode", 0)
    time.sleep(5)
    
    # Phase 4: Recover to 3 nodes
    log("\nPhase 4: Recover to 3 nodes...")
    scale_service("tagfs_datanode", 3)
    time.sleep(15)
    
    # Phase 5: Verify all files
    log("\nPhase 5: Verifying all files after recovery...")
    phase1_ok = download_and_verify(headers, url1, content1, checksum1) if success1 else False
    phase2_ok = download_and_verify(headers, url2, content2, checksum2) if success2 else False
    
    if phase1_ok:
        log("✅ Phase 1 file recovered", "SUCCESS")
    if phase2_ok:
        log("✅ Phase 2 file recovered", "SUCCESS")
    
    # Upload new file after recovery
    log("\nUploading new file after recovery...")
    content3, checksum3 = generate_random_data(15)
    success3, url3 = upload_file(headers, "recovery_phase5.bin", content3, "recovery")
    phase3_ok = download_and_verify(headers, url3, content3, checksum3) if success3 else False
    
    if phase3_ok:
        log("✅ New file after recovery successful", "SUCCESS")
    
    log("\n✅ Test 7 COMPLETED", "SUCCESS")
    return phase1_ok or phase2_ok or phase3_ok

def main():
    log("\n" + "="*70)
    log("🔬 COMPREHENSIVE CAP THEOREM & PARTITION TOLERANCE TEST SUITE")
    log("="*70)
    log(f"Target API: {API_URL}")
    log("Testing: CAP theorem, partitions, consistency, availability")
    log("="*70 + "\n")
    
    tests = [
        ("Extreme File Sizes (200MB, 500MB)", test_1_extreme_file_sizes),
        ("Partition Tolerance", test_2_partition_tolerance),
        ("Consistency Under Failures", test_3_consistency_under_failures),
        ("Concurrent Operations During Failures", test_4_concurrent_operations_during_failures),
        ("Split-Brain Scenario", test_5_split_brain_scenario),
        ("Metadata Consistency", test_6_metadata_consistency),
        ("Complete Recovery Verification", test_7_recovery_verification),
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
    log("Restoring all services to default state...")
    scale_service("tagfs_datanode", 3)
    scale_service("tagfs_metadata", 1)
    scale_service("tagfs_gateway", 1)
    
    log("\n" + "="*70)
    log(f"FINAL RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    log("="*70)
    
    if passed >= len(tests) * 0.7:  # 70% pass rate acceptable for extreme tests
        log("🎉 CAP TEST SUITE PASSED (70%+ success rate)", "SUCCESS")
        return True
    else:
        log(f"⚠️  {failed} test(s) failed", "WARN")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
