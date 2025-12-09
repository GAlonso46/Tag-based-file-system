#!/usr/bin/env python3
"""
Tests unitarios para FileStore con locks y concurrencia.

Prueba:
- File locking (fcntl)
- Escritura atómica
- Retry logic
- Acceso concurrente simulado
"""
import os
import sys
import json
import tempfile
import shutil
import threading
import time
from pathlib import Path

# Agregar directorio raíz al path
sys.path.insert(0, os.path.dirname(__file__))

from tags.data.file_store import FileStore


def test_basic_operations():
    """Test básico de add_file, add_tags, delete_file"""
    print("\n[TEST 1] Operaciones básicas...")
    
    # Crear directorio temporal
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FileStore(tmpdir)
        
        # Test 1: Agregar archivo
        store.add_file("test.txt", b"Hello World")
        assert (Path(tmpdir) / "files" / "test.txt").exists(), "Archivo no creado"
        print("  ✓ add_file funciona")
        
        # Test 2: Agregar tags
        store.add_tags("test.txt", ["tag1", "tag2"])
        assert "test.txt" in store.meta, "Metadata no actualizada"
        assert "tag1" in store.meta["test.txt"], "Tag1 no agregado"
        assert "tag2" in store.meta["test.txt"], "Tag2 no agregado"
        print("  ✓ add_tags funciona")
        
        # Test 3: Buscar por tags
        matches = store.files_matching(["tag1"])
        assert "test.txt" in matches, "Búsqueda por tags falla"
        print("  ✓ files_matching funciona")
        
        # Test 4: Eliminar archivo
        store.delete_file("test.txt")
        assert not (Path(tmpdir) / "files" / "test.txt").exists(), "Archivo no eliminado"
        assert "test.txt" not in store.meta, "Metadata no actualizada tras delete"
        print("  ✓ delete_file funciona")
    
    print("✅ TEST 1 PASADO")


def test_atomic_writes():
    """Test de escritura atómica con archivos temporales"""
    print("\n[TEST 2] Escritura atómica...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FileStore(tmpdir)
        
        # Agregar archivo grande
        large_data = b"X" * 1024 * 100  # 100KB
        store.add_file("large.bin", large_data)
        
        # Verificar que no quedaron archivos .tmp
        tmp_files = list(Path(tmpdir).rglob("*.tmp*"))
        assert len(tmp_files) == 0, f"Archivos temporales no limpiados: {tmp_files}"
        print("  ✓ No quedan archivos temporales")
        
        # Verificar integridad
        with open(Path(tmpdir) / "files" / "large.bin", "rb") as f:
            content = f.read()
            assert content == large_data, "Contenido corrupto"
        print("  ✓ Contenido íntegro después de escritura atómica")
    
    print("✅ TEST 2 PASADO")


def test_metadata_persistence():
    """Test de persistencia de metadata con reload"""
    print("\n[TEST 3] Persistencia de metadata...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Primera instancia
        store1 = FileStore(tmpdir)
        store1.add_file("file1.txt", b"data1")
        store1.add_tags("file1.txt", ["persistent", "test"])
        
        # Segunda instancia (simula otro proceso/nodo)
        store2 = FileStore(tmpdir)
        
        # Verificar que cargó la metadata
        assert "file1.txt" in store2.meta, "Metadata no cargada en nueva instancia"
        assert "persistent" in store2.meta["file1.txt"], "Tags no persistidos"
        print("  ✓ Metadata persiste entre instancias")
        
        # Modificar en store2
        store2.add_tags("file1.txt", ["new_tag"])
        
        # Recargar en store1
        store1.reload_meta()
        assert "new_tag" in store1.meta["file1.txt"], "reload_meta no funciona"
        print("  ✓ reload_meta funciona correctamente")
    
    print("✅ TEST 3 PASADO")


def test_concurrent_access():
    """Test de acceso concurrente simulado"""
    print("\n[TEST 4] Acceso concurrente...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FileStore(tmpdir)
        errors = []
        
        def worker(worker_id, iterations=10):
            """Simula un backend haciendo operaciones"""
            try:
                for i in range(iterations):
                    filename = f"file_{worker_id}_{i}.txt"
                    
                    # Crear archivo
                    store.add_file(filename, f"Data from worker {worker_id}".encode())
                    
                    # Agregar tags
                    store.add_tags(filename, [f"worker{worker_id}", f"iter{i}"])
                    
                    # Pequeño delay aleatorio
                    time.sleep(0.001 * (worker_id % 3))
                    
                    # Leer metadata (simula búsqueda)
                    _ = store.files_matching([f"worker{worker_id}"])
                    
            except Exception as e:
                errors.append(f"Worker {worker_id}: {e}")
        
        # Lanzar 5 workers concurrentes
        threads = []
        num_workers = 5
        
        for i in range(num_workers):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()
        
        # Esperar a que terminen
        for t in threads:
            t.join()
        
        # Verificar que no hubo errores
        if errors:
            print(f"  ✗ Errores en workers: {errors}")
            assert False, "Hubo errores en acceso concurrente"
        
        print(f"  ✓ {num_workers} workers completaron sin errores")
        
        # Verificar que todos los archivos fueron creados
        expected_files = num_workers * 10
        actual_files = len(list((Path(tmpdir) / "files").glob("file_*.txt")))
        
        assert actual_files == expected_files, f"Esperados {expected_files}, encontrados {actual_files}"
        print(f"  ✓ Todos los {expected_files} archivos fueron creados correctamente")
        
        # Verificar metadata
        assert len(store.meta) >= expected_files, "Metadata incompleta"
        print(f"  ✓ Metadata completa ({len(store.meta)} entradas)")
    
    print("✅ TEST 4 PASADO")


def test_retry_logic():
    """Test de retry logic en save_meta"""
    print("\n[TEST 5] Retry logic...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FileStore(tmpdir)
        
        # Agregar múltiples archivos rápidamente
        # (puede causar conflictos que deben resolverse con retry)
        for i in range(20):
            store.add_file(f"rapid_{i}.txt", f"Data {i}".encode())
            store.add_tags(f"rapid_{i}.txt", [f"tag{i}"])
        
        # Verificar que todos fueron creados
        assert len(store.meta) == 20, f"Esperados 20, encontrados {len(store.meta)}"
        print("  ✓ Retry logic manejó escrituras rápidas correctamente")
        
        # Verificar JSON es válido
        meta_path = Path(tmpdir) / "files" / "files.json"
        with open(meta_path) as f:
            data = json.load(f)
            assert len(data) == 20, "JSON corrupto"
        print("  ✓ JSON válido después de escrituras múltiples")
    
    print("✅ TEST 5 PASADO")


def test_error_recovery():
    """Test de recuperación ante errores"""
    print("\n[TEST 6] Recuperación ante errores...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FileStore(tmpdir)
        
        # Test: archivo ya existe (overwrite)
        store.add_file("existing.txt", b"original")
        store.add_file("existing.txt", b"updated")
        
        with open(Path(tmpdir) / "files" / "existing.txt", "rb") as f:
            assert f.read() == b"updated", "Overwrite falló"
        print("  ✓ Overwrite de archivos funciona")
        
        # Test: eliminar archivo inexistente (debe ser graceful)
        try:
            store.delete_file("nonexistent.txt")
            print("  ✓ delete_file de archivo inexistente no lanza error")
        except Exception as e:
            assert False, f"delete_file lanzó error inesperado: {e}"
        
        # Test: agregar tags a archivo inexistente crea entrada
        store.add_tags("new_file.txt", ["tag1"])
        assert "new_file.txt" in store.meta, "add_tags no crea entrada nueva"
        print("  ✓ add_tags crea entrada si no existe")
    
    print("✅ TEST 6 PASADO")


def run_all_tests():
    """Ejecutar todos los tests"""
    print("=" * 60)
    print("  Tests de FileStore con Locks y Concurrencia")
    print("=" * 60)
    
    tests = [
        test_basic_operations,
        test_atomic_writes,
        test_metadata_persistence,
        test_concurrent_access,
        test_retry_logic,
        test_error_recovery,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ TEST FALLÓ: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ ERROR INESPERADO: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"  RESULTADOS: {passed} ✓  |  {failed} ✗")
    print("=" * 60)
    
    if failed == 0:
        print("\n🎉 TODOS LOS TESTS PASARON")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) fallaron")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
