#!/usr/bin/env python3
"""
Remueve NPCs hostiles que tienen IDs que según NPCs.dat deben ser amigables.

Estos NPCs fueron agregados manualmente antes pero tienen IDs incorrectos.
"""

import re
import tomllib
from pathlib import Path


def get_friendly_npc_ids(npcs_dat_path: Path) -> set[int]:
    """Obtiene los IDs de NPCs que deben ser amigables según NPCs.dat."""
    try:
        with open(npcs_dat_path, 'r', encoding='latin1') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(npcs_dat_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    
    friendly_ids = set()
    
    # Buscar todos los bloques [NPCXXX]
    for match in re.finditer(r'\[NPC(\d+)\]', content):
        npc_id = int(match.group(1))
        block_start = match.start()
        block = content[block_start:block_start + 500]
        
        hostile_match = re.search(r'Hostile=(\d+)', block)
        if hostile_match and int(hostile_match.group(1)) == 0:
            friendly_ids.add(npc_id)
    
    return friendly_ids


def remove_incorrect_hostiles(hostiles_file: Path, npcs_dat_path: Path) -> None:
    """Remueve NPCs hostiles que deberían ser amigables."""
    
    # Obtener IDs que deben ser amigables
    friendly_ids = get_friendly_npc_ids(npcs_dat_path)
    
    # Cargar hostiles actuales
    with open(hostiles_file, 'rb') as f:
        hostiles_data = tomllib.load(f)
        hostiles_npcs = {npc['id']: npc for npc in hostiles_data.get('npc', [])}
    
    # Encontrar NPCs hostiles que deberían ser amigables
    incorrect_ids = [npc_id for npc_id in hostiles_npcs.keys() if npc_id in friendly_ids]
    
    if not incorrect_ids:
        print("✅ No hay NPCs hostiles incorrectos para remover.")
        return
    
    print(f"🗑️  Removiendo {len(incorrect_ids)} NPCs hostiles incorrectos...")
    for npc_id in sorted(incorrect_ids):
        npc = hostiles_npcs[npc_id]
        print(f"   - NPC {npc_id}: {npc['nombre']} (debe ser amigable según NPCs.dat)")
    
    # Leer archivo completo
    hostiles_content = hostiles_file.read_text(encoding='utf-8')
    
    # Remover cada NPC incorrecto
    for npc_id in incorrect_ids:
        # Buscar y remover el bloque [[npc]] con este id
        pattern = rf'\[\[npc\]\]\nid = {npc_id}\n.*?(?=\[\[npc\]\]|\Z)'
        hostiles_content = re.sub(pattern, '', hostiles_content, flags=re.DOTALL)
    
    # Limpiar líneas en blanco múltiples
    hostiles_content = re.sub(r'\n\n\n+', '\n\n', hostiles_content)
    
    # Guardar archivo
    hostiles_file.write_text(hostiles_content, encoding='utf-8')
    print(f"\n✅ Archivo actualizado: {hostiles_file}")


def main():
    base_dir = Path(__file__).parent.parent.parent
    hostiles_file = base_dir / 'data' / 'npcs_hostiles.toml'
    npcs_dat = base_dir / 'clientes' / 'ArgentumOnline0.13.3-Cliente-Servidor' / 'server' / 'Dat' / 'NPCs.dat'
    
    if not npcs_dat.exists():
        print(f"❌ Error: No existe {npcs_dat}")
        return
    
    remove_incorrect_hostiles(hostiles_file, npcs_dat)
    
    # Verificar resultado
    print("\n📊 Verificando resultado...")
    try:
        with open(hostiles_file, 'rb') as f:
            hostiles_data = tomllib.load(f)
            hostiles_ids = {npc['id'] for npc in hostiles_data.get('npc', [])}
        
        friendly_ids = get_friendly_npc_ids(npcs_dat)
        remaining_incorrect = hostiles_ids & friendly_ids
        
        if remaining_incorrect:
            print(f"   ⚠️  Aún quedan {len(remaining_incorrect)} NPCs hostiles incorrectos")
        else:
            print(f"   ✅ No quedan NPCs hostiles incorrectos")
            print(f"   - Hostiles restantes: {len(hostiles_ids)} NPCs")
    except Exception as e:
        print(f"   ❌ Error verificando: {e}")


if __name__ == "__main__":
    main()

