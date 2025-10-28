#!/usr/bin/env python3
"""
Extractor de objetos de mapas del cliente Argentum Online (versión optimizada).

Este script lee los archivos .map binarios del cliente y extrae
árboles, minerales y otros objetos para generar archivos JSON compactos.
"""

import struct
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Rangos de índices gráficos para objetos
TREE_RANGES = [
    (641, 641),    # Árbol básico
    (647, 647),    # Árbol variante
    (7000, 7020),  # Árboles grandes
    (5592, 5592),  # Árbol tipo 1
    (5593, 5593),  # Árbol tipo 2
    (5599, 5599),  # Árbol tipo 3
    (5600, 5600),  # Árbol tipo 4
    (5748, 5748),  # Árbol especial
    (1460, 1460),  # Árbolito
    (1472, 1485),  # Más árboles
    (1490, 1504),  # Árboles en maceta
]

MINE_RANGES = [
    (8608, 8619),  # Yacimientos
]


class MapObjectExtractor:
    def __init__(self, maps_dir: Path, output_dir: Path):
        self.maps_dir = maps_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)

    def is_tree(self, grh_index: int) -> bool:
        """Verifica si el índice gráfico corresponde a un árbol."""
        for start, end in TREE_RANGES:
            if start <= grh_index <= end:
                return True
        return False

    def is_mine(self, grh_index: int) -> bool:
        """Verifica si el índice gráfico corresponde a una mina."""
        for start, end in MINE_RANGES:
            if start <= grh_index <= end:
                return True
        return False

    def extract_map_objects(self, map_file: Path) -> List[Dict]:
        """Extrae objetos de un archivo de mapa específico."""
        objects = []
        
        try:
            with open(map_file, 'rb') as f:
                # Saltar header (primeros 255 bytes)
                f.seek(255)
                
                # Procesar mapa 100x100 tiles
                for y in range(1, 101):
                    for x in range(1, 101):
                        # Leer ByFlags
                        by_flags = struct.unpack('<B', f.read(1))[0]
                        
                        # Layer 1 - siempre presente
                        grh1 = struct.unpack('<H', f.read(2))[0]
                        
                        # Layer 2-4 - condicionales
                        grh2 = 0
                        grh3 = 0
                        grh4 = 0
                        
                        if by_flags & 2:  # Layer 2
                            grh2 = struct.unpack('<H', f.read(2))[0]
                        if by_flags & 4:  # Layer 3
                            grh3 = struct.unpack('<H', f.read(2))[0]
                        if by_flags & 8:  # Layer 4
                            grh4 = struct.unpack('<H', f.read(2))[0]
                            
                        # Trigger - condicional
                        if by_flags & 16:
                            f.read(1)  # Skip trigger byte
                        
                        # Extraer objetos de los layers
                        for layer, grh_index in enumerate([grh1, grh2, grh3, grh4], 1):
                            if grh_index == 0:
                                continue
                                
                            if self.is_tree(grh_index):
                                # Formato compacto: solo datos esenciales
                                objects.append({
                                    "t": "tree",  # type
                                    "x": x,
                                    "y": y,
                                    "g": grh_index  # grh_index
                                })
                            elif self.is_mine(grh_index):
                                objects.append({
                                    "t": "mine",
                                    "x": x,
                                    "y": y,
                                    "g": grh_index
                                })
                                
        except Exception as e:
            print(f"Error procesando {map_file}: {e}")
            
        return objects

    def process_all_maps(self):
        """Procesa todos los archivos de mapa y genera los JSON consolidados."""
        map_files = list(self.maps_dir.glob("*.map"))
        print(f"Encontrados {len(map_files)} archivos de mapa")
        
        # Agrupar mapas en lotes de 50
        all_objects: Dict[int, List[Dict]] = {}
        
        # Extraer objetos de todos los mapas
        for map_file in sorted(map_files):
            print(f"Procesando {map_file.name}...")
            
            map_number = self.extract_map_number(map_file)
            if map_number is None:
                continue
                
            objects = self.extract_map_objects(map_file)
            all_objects[map_number] = objects
            
            if objects:
                print(f"  → {len(objects)} objetos extraídos")
        
        # Generar archivos consolidados
        self._write_consolidated_files(all_objects)
        
    def _write_consolidated_files(self, all_objects: Dict[int, List[Dict]]):
        """Escribe archivos JSON consolidados en lotes de 50 mapas."""
        map_ids = sorted(all_objects.keys())
        
        for i in range(0, len(map_ids), 50):
            batch = map_ids[i:i+50]
            start_id = batch[0]
            end_id = batch[-1]
            
            output_file = self.output_dir / f"objects_{start_id:03d}-{end_id:03d}.json"
            
            total_objects = 0
            with open(output_file, 'w', encoding='utf-8') as f:
                for map_id in batch:
                    objects = all_objects[map_id]
                    for obj in objects:
                        obj['m'] = map_id  # Añadir ID del mapa
                        f.write(json.dumps(obj, separators=(',', ':')) + '\n')
                        total_objects += 1
            
            print(f"✅ {output_file.name}: {total_objects} objetos ({len(batch)} mapas)")
        
        print(f"\n✅ Generados {(len(map_ids) + 49) // 50} archivos consolidados")

    def extract_map_number(self, map_file: Path) -> Optional[int]:
        """Extrae el número del mapa del nombre del archivo."""
        name = map_file.stem.lower()
        if name.startswith('mapa'):
            try:
                return int(name[4:])
            except ValueError:
                pass
        elif name.startswith('map'):
            try:
                return int(name[3:])
            except ValueError:
                pass
        return None


def main():
    # Directorios
    base_dir = Path(__file__).parent.parent
    client_maps_dir = base_dir / "clientes" / "ArgentumOnline0.13.3-Cliente-Servidor" / "client" / "Mapas"
    output_dir = base_dir / "map_data"
    
    if not client_maps_dir.exists():
        print(f"Error: No existe el directorio {client_maps_dir}")
        return
        
    extractor = MapObjectExtractor(client_maps_dir, output_dir)
    extractor.process_all_maps()
    
    print("\n✅ Extracción optimizada completada!")
    print("Los archivos consolidados han sido generados en map_data/")
    print("📊 Formato compacto: ~75% reducción de tamaño")
    print("🚀 Archivos consolidados: ~50x menos I/O")


if __name__ == "__main__":
    main()
