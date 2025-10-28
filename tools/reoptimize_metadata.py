#!/usr/bin/env python3
"""
Re-optimizador de metadatos: un mapa por línea con formato compacto.
"""

import json
from pathlib import Path
from typing import Dict, List


def reoptimize_metadata():
    """Re-optimiza metadatos con un mapa por línea."""
    maps_dir = Path("map_data")
    
    print("🔧 Re-optimizando metadatos (un mapa por línea)...")
    
    # Eliminar archivos consolidados actuales
    for meta_file in maps_dir.glob("metadata_*.json"):
        meta_file.unlink()
        print(f"Eliminado {meta_file.name}")
    
    # Procesar todos los mapas
    all_metadata: List[Dict] = []
    
    # Buscar metadatos originales si existen, sino generar desde objetos
    map_ids = set()
    
    # Extraer IDs de archivos de objetos
    for obj_file in maps_dir.glob("objects_*.json"):
        with obj_file.open(encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        obj = json.loads(line)
                        map_ids.add(obj.get('m', 0))
                    except:
                        continue
    
    # Generar metadatos para cada mapa encontrado
    for map_id in sorted(map_ids):
        metadata = {
            "i": map_id,        # id (compacto)
            "n": f"Mapa {map_id}", # name
            "w": 100,          # width
            "h": 100,          # height  
            "r": False,        # rain
            "s": False         # snow
        }
        all_metadata.append(metadata)
    
    # Escribir en lotes de 50 mapas, un mapa por línea
    for i in range(0, len(all_metadata), 50):
        batch = all_metadata[i:i+50]
        start_id = batch[0]["i"]
        end_id = batch[-1]["i"]
        
        output_file = maps_dir / f"metadata_{start_id:03d}-{end_id:03d}.json"
        
        with output_file.open('w', encoding='utf-8') as f:
            for metadata in batch:
                # Una línea por mapa, formato compacto
                f.write(json.dumps(metadata, separators=(',', ':')) + '\n')
        
        print(f"✅ {output_file.name}: {len(batch)} mapas")
    
    print(f"\n📊 Nuevo formato: un mapa por línea")
    
    # Mostrar ejemplo
    print(f"\n📝 Ejemplo del nuevo formato:")
    if all_metadata:
        first_meta = all_metadata[0]
        print(f"   {json.dumps(first_meta, separators=(',', ':'))}")
        print(f"   // Mapa {first_meta['i']}: {first_meta['n']}")


def generate_stats():
    """Genera estadísticas del nuevo formato."""
    maps_dir = Path("map_data")
    
    meta_files = list(maps_dir.glob("metadata_*.json"))
    if not meta_files:
        return
    
    total_size = sum(f.stat().st_size for f in meta_files) / 1024
    total_maps = 0
    
    for meta_file in meta_files:
        with meta_file.open(encoding='utf-8') as f:
            total_maps += sum(1 for line in f if line.strip())
    
    print(f"\n📈 Estadísticas del nuevo formato:")
    print(f"Archivos: {len(meta_files)} consolidados")
    print(f"Mapas: {total_maps} totales")
    print(f"Tamaño: {total_size:.0f}KB")
    print(f"Promedio por mapa: {total_size/total_maps:.1f}KB")
    print(f"Formato: JSON compacto, un mapa por línea")


if __name__ == "__main__":
    reoptimize_metadata()
    generate_stats()
    print("\n✅ Re-optimización completada!")
