"""Test para verificar detección de árboles en el servidor."""

import json
import sys
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.services.map.map_resources_service import MapResourcesService

SEARCH_RADIUS = 5
TARGET_COORD = (74, 92)


def test_tree_detection() -> bool:
    """Test simple para verificar detección del árbol en (74, 92).

    Returns:
        True si la coordenada conocida contiene un árbol.
    """
    print("🔍 Test: Detección de Árbol en Mapa 1, Coordenada (74, 92)")
    print("=" * 60)

    # Inicializar servicio
    service = MapResourcesService()

    # Verificar si el mapa 1 tiene recursos cargados
    map_key = "map_1"
    if map_key not in service.resources:
        print("❌ ERROR: Mapa 1 no tiene recursos cargados")
        print(f"Mapas disponibles: {list(service.resources.keys())}")
        return False

    # Verificar si hay árboles en el mapa 1
    trees = service.resources[map_key].get("trees", set())
    print(f"📊 Total árboles en mapa 1: {len(trees)}")

    # Verificar coordenada específica
    target_coord = (74, 92)
    has_tree = service.has_tree(1, 74, 92)

    print(f"🎯 Coordenada (74, 92): {'✅ ÁRBOL DETECTADO' if has_tree else '❌ SIN ÁRBOL'}")

    # Mostrar árboles cercanos
    nearby_trees = [
        coord
        for coord in trees
        if abs(coord[0] - TARGET_COORD[0]) <= SEARCH_RADIUS
        and abs(coord[1] - TARGET_COORD[1]) <= SEARCH_RADIUS
    ]

    if nearby_trees:
        print("🌳 Árboles cercanos (±5 tiles):")
        for tree_coord in sorted(nearby_trees):
            symbol = "🎯" if tree_coord == target_coord else "🌲"
            print(f"   {symbol} {tree_coord}")

    # Verificar archivo JSON directamente
    objects_file = Path("map_data/objects_001-050.json")
    if objects_file.exists():
        print(f"\n📁 Verificando archivo: {objects_file}")

        with objects_file.open(encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                entry = json.loads(line)
                if entry.get("m") == 1 and (entry.get("x"), entry.get("y")) == TARGET_COORD:
                    print(f"   ✅ Línea {line_num}: {entry}")
                    print(f"   📊 GrhIndex: {entry.get('g')}")
                    print(f"   🏷️  Tipo: {entry.get('t')}")
                    break
            else:
                print("   ❌ No se encontró (74, 92) en el archivo")

    return has_tree


if __name__ == "__main__":
    success = test_tree_detection()
    print("\n" + "=" * 60)
    if success:
        print("🎉 RESULTADO: El servidor DETECTA el árbol correctamente")
        print("💡 El problema debe estar en el cliente o en la sincronización")
    else:
        print("🚨 RESULTADO: El servidor NO detecta el árbol")
        print("🔧 Hay un problema en la carga de recursos del servidor")

    sys.exit(0 if success else 1)
