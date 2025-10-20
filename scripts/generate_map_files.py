"""Script para generar archivos JSON de mapas con tiles bloqueados básicos.

Este script crea archivos JSON para los mapas configurados en map_transitions.toml
con tiles bloqueados en los bordes para testing.
"""

import json
from pathlib import Path


def generate_map_json(map_id: int, name: str, blocked_tiles: list[dict]) -> dict:
    """Genera estructura JSON para un mapa.
    
    Args:
        map_id: ID del mapa
        name: Nombre del mapa
        blocked_tiles: Lista de tiles bloqueados
    
    Returns:
        Diccionario con estructura del mapa
    """
    return {
        "id": map_id,
        "name": name,
        "width": 100,
        "height": 100,
        "blocked_tiles": blocked_tiles,
        "spawn_points": [
            {"x": 50, "y": 50, "description": f"Centro de {name}"}
        ]
    }


def create_basic_blocked_tiles() -> list[dict]:
    """Crea tiles bloqueados básicos (bordes del mapa).
    
    Returns:
        Lista de tiles bloqueados en los bordes
    """
    blocked = []
    
    # Bordes del mapa (opcional, para testing)
    # Por ahora dejamos los mapas abiertos para que las transiciones funcionen
    
    # Agregar algunos tiles bloqueados de ejemplo en el centro
    # (esto es solo para demostración, en producción se cargarían desde los .map)
    for x in range(48, 53):
        for y in range(48, 53):
            if x == 50 and y == 50:
                continue  # Dejar el centro libre
            blocked.append({"x": x, "y": y, "type": "wall"})
    
    return blocked


def generate_all_maps():
    """Genera archivos JSON para todos los mapas configurados."""
    maps_dir = Path("maps")
    maps_dir.mkdir(exist_ok=True)
    
    # Mapas configurados en map_transitions.toml
    maps_config = [
        (1, "Ullathorpe"),
        (2, "Bosque Norte"),
        (3, "Campo Sur"),
        (4, "Bosque Este"),
        (5, "Montañas Oeste"),
        (6, "Bosque Profundo"),
        (7, "Camino del Desierto"),
        (8, "Tierras Salvajes"),
        (9, "Paso de Montaña"),
    ]
    
    for map_id, name in maps_config:
        # Crear tiles bloqueados básicos
        blocked_tiles = create_basic_blocked_tiles()
        
        # Generar JSON
        map_data = generate_map_json(map_id, name, blocked_tiles)
        
        # Guardar archivo
        output_file = maps_dir / f"map_{map_id}.json"
        with output_file.open('w', encoding='utf-8') as f:
            json.dump(map_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Generado: {output_file} ({len(blocked_tiles)} tiles bloqueados)")
    
    print(f"\n✅ {len(maps_config)} archivos de mapa generados en {maps_dir}/")


if __name__ == "__main__":
    print("=" * 60)
    print("Generador de Archivos de Mapa - PyAO Server")
    print("=" * 60)
    print()
    
    generate_all_maps()
