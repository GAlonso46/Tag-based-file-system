# Tags-based-file-system (centralized minimal)

Proyecto independiente (centralizado) para la 1ra entrega.


Ejecutar la interfaz interactiva:

```powershell
python main.py
# o
python -m tags.cli
```

Ejemplo de uso en modo no interactivo:

```powershell
python main.py add "C:\path\a.txt" "importante,proyecto"
```

Comandos soportados en el prompt: add, delete, list, add-tags, delete-tags, show, exit

## Instalación de dependencias

Instala pytest para ejecutar los tests:

```powershell
pip install pytest
```

## Ejecutar tests

Desde la raíz del proyecto:

```powershell
pytest tests
```
