"""Analiza los gráficos (GRH) usados en tiles bloqueados de los mapas."""

import struct
from collections import Counter
from pathlib import Path


def analyze_blocked_grh(map_id: int, maps_dir: str = "./clientes/ArgentumOnlineGodot/Assets/Maps") -> Counter:
    """Analiza los GRH de tiles bloqueados en un mapa.
    
    Args:
        map_id: ID del mapa
        maps_dir: Directorio con archivos .map
    
    Returns:
        Counter con frecuencia de cada GRH
    """
    map_path = Path(maps_dir) / f"mapa{map_id}.map"
    
    if not map_path.exists():
        return Counter()
    
    grh_counter = Counter()
    
    with map_path.open('rb') as f:
        # Saltar header
        f.seek(2 + 255 + 4 + 4 + 8)
        
        # Leer tiles
        for y in range(100):
            for x in range(100):
                flags_byte = f.read(1)
                if not flags_byte:
                    break
                flags = struct.unpack('B', flags_byte)[0]
                
                layer1_bytes = f.read(2)
                if not layer1_bytes:
                    break
                layer1 = struct.unpack('<H', layer1_bytes)[0]
                
                # Layer 2
                if flags & 0x2:
                    f.read(2)
                
                # Layer 3
                if flags & 0x4:
                    f.read(2)
                
                # Layer 4
                if flags & 0x8:
                    f.read(2)
                
                # Trigger
                if flags & 0x10:
                    f.read(2)
                
                # Si está bloqueado, contar el GRH
                if flags & 0x1:
                    grh_counter[layer1] += 1
    
    return grh_counter


def main():
    """Analiza los GRH de todos los mapas."""
    print("=" * 70)
    print("Análisis de GRH en Tiles Bloqueados")
    print("=" * 70)
    print()
    
    for map_id in range(1, 10):
        print(f"📊 Mapa {map_id}:")
        grh_counter = analyze_blocked_grh(map_id)
        
        # Mostrar top 20 GRH más comunes
        print(f"   Total tiles bloqueados: {sum(grh_counter.values())}")
        print(f"   GRH únicos: {len(grh_counter)}")
        print(f"   Top 20 GRH más comunes:")
        
        for grh, count in grh_counter.most_common(20):
            percentage = (count / sum(grh_counter.values()) * 100)
            print(f"      GRH {grh:5d}: {count:4d} tiles ({percentage:5.1f}%)")
        
        print()


if __name__ == "__main__":
    main()
