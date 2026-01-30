import socket
import sys

def check_alias(alias_name):
    print(f"\n--- Verificando alias: {alias_name} ---")
    try:
        # Buscamos todas las IPs asociadas al alias
        # El puerto 0 y SOCK_DGRAM se usan solo para la consulta DNS
        infos = socket.getaddrinfo(alias_name, 0, socket.AF_INET, socket.SOCK_DGRAM)
        
        # Extraer IPs únicas
        ips = sorted(list(set([info[4][0] for info in infos])))
        
        print(f"✅ Éxito: Se encontraron {len(ips)} nodos activos.")
        for i, ip in enumerate(ips, 1):
            print(f"  {i}. IP: {ip}")
            
    except socket.gaierror:
        print(f"❌ Error: No se encontró ningún contenedor con el alias '{alias_name}'.")
    except Exception as e:
        print(f"⚠️ Error inesperado: {e}")

if __name__ == "__main__":
    print("=== TEST DE DESCUBRIMIENTO DE SERVICIOS TAGFS ===")
    
    # Lista de los alias que definimos en los comandos 'docker run'
    servicios_a_probar = [
        "metadata_service",
        "datanode_service",
        "gateway_service"
    ]
    
    for servicio in servicios_a_probar:
        check_alias(servicio)
    
    print("\n================================================")
