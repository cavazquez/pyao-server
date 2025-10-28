#!/usr/bin/env python3
"""
Optimizador de datos de mapas (metadata y blocked).

Consolida archivos y comprime formatos para reducir tamaño y mejorar rendimiento.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple


class MapDataOptimizer:
    def __init__(self, maps_dir: Path):
        self.maps_dir = maps_dir

    def optimize_metadata(self):
        """Optimiza archivos metadata consolidándolos en lotes."""
        print("🔧 Optimizando metadatos...")
        
        metadata_files = sorted(self.maps_dir.glob("*_metadata.json"))
        if not metadata_files:
            print("No se encontraron archivos metadata")
            return

        all_metadata: Dict[int, Dict] = {}
        
        # Cargar todos los metadatos
        for meta_file in metadata_files:
            try:
                with meta_file.open() as f:
                    metadata = json.load(f)
                    map_id = metadata.get("id")
                    if map_id:
                        all_metadata[map_id] = metadata
            except Exception as e:
                print(f"Error leyendo {meta_file}: {e}")
        
        # Generar archivos consolidados
        map_ids = sorted(all_metadata.keys())
        for i in range(0, len(map_ids), 50):
            batch = map_ids[i:i+50]
            start_id = batch[0]
            end_id = batch[-1]
            
            consolidated = {str(map_id): all_metadata[map_id] for map_id in batch}
            output_file = self.maps_dir / f"metadata_{start_id:03d}-{end_id:03d}.json"
            
            with output_file.open('w', encoding='utf-8') as f:
                json.dump(consolidated, f, separators=(',', ':'))
            
            print(f"✅ {output_file.name}: {len(batch)} mapas")
        
        print(f"📊 Metadatos: {len(metadata_files)} archivos → {(len(map_ids) + 49) // 50} consolidados")

    def optimize_blocked(self):
        """Optimiza archivos blocked usando formato compacto y consolidación."""
        print("\n🔧 Optimizando archivos blocked...")
        
        blocked_files = sorted(self.maps_dir.glob("*_blocked.json"))
        if not blocked_files:
            print("No se encontraron archivos blocked")
            return

        # Procesar en lotes de 50 mapas
        for i in range(0, len(blocked_files), 50):
            batch = blocked_files[i:i+50]
            start_map = int(batch[0].stem.split('_')[0])
            end_map = int(batch[-1].stem.split('_')[0])
            
            output_file = self.maps_dir / f"blocked_{start_map:03d}-{end_map:03d}.json"
            total_tiles = 0
            
            with output_file.open('w', encoding='utf-8') as f:
                for blocked_file in batch:
                    map_id = int(blocked_file.stem.split('_')[0])
                    
                    try:
                        with blocked_file.open(encoding='utf-8') as infile:
                            for line in infile:
                                line = line.strip()
                                if not line:
                                    continue
                                
                                try:
                                    tile = json.loads(line)
                                    tile_type = tile.get('type')
                                    x = tile.get('x')
                                    y = tile.get('y')
                                    
                                    if tile_type == 'blocked':
                                        # Formato compacto
                                        compact_tile = {
                                            't': 'b',  # type: blocked
                                            'm': map_id,  # map_id
                                            'x': x,
                                            'y': y
                                        }
                                        f.write(json.dumps(compact_tile, separators=(',', ':')) + '\n')
                                        total_tiles += 1
                                    elif tile_type == 'water':
                                        # Formato compacto
                                        compact_tile = {
                                            't': 'w',  # type: water
                                            'm': map_id,
                                            'x': x,
                                            'y': y
                                        }
                                        f.write(json.dumps(compact_tile, separators=(',', ':')) + '\n')
                                        total_tiles += 1
                                        
                                except json.JSONDecodeError:
                                    continue
                                    
                    except Exception as e:
                        print(f"Error procesando {blocked_file}: {e}")
            
            print(f"✅ {output_file.name}: {total_tiles} tiles ({len(batch)} mapas)")
        
        print(f"📊 Blocked: {len(blocked_files)} archivos → {(len(blocked_files) + 49) // 50} consolidados")

    def generate_stats(self):
        """Genera estadísticas de optimización."""
        print("\n📈 Estadísticas de optimización:")
        
        # Calcular tamaños originales
        orig_meta_size = sum(f.stat().st_size for f in self.maps_dir.glob("*_metadata.json")) / 1024
        orig_blocked_size = sum(f.stat().st_size for f in self.maps_dir.glob("*_blocked.json")) / 1024
        
        # Calcular tamaños optimizados
        opt_meta_size = sum(f.stat().st_size for f in self.maps_dir.glob("metadata_*.json")) / 1024
        opt_blocked_size = sum(f.stat().st_size for f in self.maps_dir.glob("blocked_*.json")) / 1024
        
        print(f"Metadatos: {orig_meta_size:.0f}KB → {opt_meta_size:.0f}KB ({100 - (opt_meta_size*100/orig_meta_size):.0f}% reducción)")
        print(f"Blocked: {orig_blocked_size:.0f}KB → {opt_blocked_size:.0f}KB ({100 - (opt_blocked_size*100/orig_blocked_size):.0f}% reducción)")
        print(f"Total: {(orig_meta_size + orig_blocked_size):.0f}KB → {(opt_meta_size + opt_blocked_size):.0f}KB ({100 - ((opt_meta_size + opt_blocked_size)*100/(orig_meta_size + orig_blocked_size)):.0f}% reducción)")
        
        # Reducción de archivos
        orig_files = len(list(self.maps_dir.glob("*_metadata.json"))) + len(list(self.maps_dir.glob("*_blocked.json")))
        opt_files = len(list(self.maps_dir.glob("metadata_*.json"))) + len(list(self.maps_dir.glob("blocked_*.json")))
        print(f"Archivos: {orig_files} → {opt_files} ({orig_files//opt_files}x menos I/O)")

    def cleanup_original(self):
        """Elimina archivos originales después de la optimización."""
        print("\n🧹 Limpiando archivos originales...")
        
        metadata_count = 0
        for meta_file in self.maps_dir.glob("*_metadata.json"):
            meta_file.unlink()
            metadata_count += 1
        
        blocked_count = 0
        for blocked_file in self.maps_dir.glob("*_blocked.json"):
            blocked_file.unlink()
            blocked_count += 1
        
        print(f"Eliminados: {metadata_count} metadata + {blocked_count} blocked archivos")


def main():
    maps_dir = Path("map_data")
    
    if not maps_dir.exists():
        print("Error: No existe el directorio map_data")
        return
    
    optimizer = MapDataOptimizer(maps_dir)
    
    # Optimizar
    optimizer.optimize_metadata()
    optimizer.optimize_blocked()
    
    # Generar estadísticas
    optimizer.generate_stats()
    
    # Preguntar si limpiar archivos originales
    print("\n¿Desea eliminar los archivos originales? (y/n): ", end="")
    response = input().strip().lower()
    if response == 'y':
        optimizer.cleanup_original()
    
    print("\n✅ Optimización completada!")


if __name__ == "__main__":
    main()
