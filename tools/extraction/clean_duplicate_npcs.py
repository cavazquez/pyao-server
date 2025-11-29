#!/usr/bin/env python3
"""
Script para limpiar NPCs duplicados entre archivos hostiles y amigables.

Verifica el archivo NPCs.dat original para determinar si un NPC debe ser
hostil o amigable, y elimina las entradas duplicadas incorrectas.
"""

import re
import tomllib
from pathlib import Path
from typing import Any


def get_npc_hostile_status_from_dat(npc_id: int, npcs_dat_path: Path) -> tuple[bool, str] | None:
    """Obtiene el status de Hostile de un NPC desde NPCs.dat.
    
    Returns:
        (is_hostile, name) o None si no se encuentra
    """
    try:
        with open(npcs_dat_path, 'r', encoding='latin1') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(npcs_dat_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    
    # Buscar el bloque [NPC{id}]
    pattern = rf'\[NPC{npc_id}\]'
    match = re.search(pattern, content)
    if not match:
        return None
    
    # Extraer el bloque completo
    block_start = match.start()
    # Buscar hasta el siguiente [NPC o fin de archivo
    block_end_match = re.search(r'\n\[NPC\d+\]', content[block_start + 100:])
    if block_end_match:
        block = content[block_start:block_start + 100 + block_end_match.start()]
    else:
        block = content[block_start:block_start + 1000]
    
    # Extraer Hostile y Name
    hostile_match = re.search(r'Hostile=(\d+)', block)
    name_match = re.search(r'Name=([^\n\r]+)', block)
    
    if hostile_match:
        is_hostile = int(hostile_match.group(1)) == 1
        name = name_match.group(1).strip().strip('"\'') if name_match else f"NPC{npc_id}"
        return (is_hostile, name)
    
    return None


def clean_duplicate_npcs(
    hostiles_file: Path,
    amigables_file: Path,
    npcs_dat_path: Path
) -> None:
    """Limpia los NPCs duplicados entre hostiles y amigables."""
    
    # Cargar archivos actuales
    with open(hostiles_file, 'rb') as f:
        hostiles_data = tomllib.load(f)
        hostiles_npcs = {npc['id']: npc for npc in hostiles_data.get('npc', [])}
    
    with open(amigables_file, 'rb') as f:
        amigables_data = tomllib.load(f)
        amigables_npcs = {npc['id']: npc for npc in amigables_data.get('npc', [])}
    
    # Encontrar duplicados
    duplicate_ids = set(hostiles_npcs.keys()) & set(amigables_npcs.keys())
    
    if not duplicate_ids:
        print("✅ No hay NPCs duplicados.")
        return
    
    print(f"🔍 Encontrados {len(duplicate_ids)} NPCs duplicados.")
    print("   Verificando status en NPCs.dat original...")
    
    # Determinar cuál versión es correcta según NPCs.dat
    to_remove_from_hostiles: list[int] = []
    to_remove_from_amigables: list[int] = []
    
    for npc_id in duplicate_ids:
        status = get_npc_hostile_status_from_dat(npc_id, npcs_dat_path)
        if status is None:
            # Si no se encuentra en NPCs.dat, mantener ambos (no hacer nada)
            print(f"   ⚠️  NPC {npc_id} no encontrado en NPCs.dat, manteniendo ambas versiones")
            continue
        
        is_hostile_original, name = status
        hostile_npc = hostiles_npcs[npc_id]
        amigable_npc = amigables_npcs[npc_id]
        
        # Verificar cuál versión coincide con el original
        hostile_matches = hostile_npc.get('es_hostil') == is_hostile_original
        amigable_matches = not amigable_npc.get('es_hostil') == is_hostile_original
        
        if is_hostile_original:
            # Debe estar solo en hostiles
            if not hostile_matches:
                print(f"   ❌ NPC {npc_id} ({name}): hostil pero no coincide, removiendo de hostiles")
                to_remove_from_hostiles.append(npc_id)
            else:
                print(f"   ✅ NPC {npc_id} ({name}): debe ser hostil, removiendo de amigables")
                to_remove_from_amigables.append(npc_id)
        else:
            # Debe estar solo en amigables
            if not amigable_matches:
                print(f"   ❌ NPC {npc_id} ({name}): amigable pero no coincide, removiendo de amigables")
                to_remove_from_amigables.append(npc_id)
            else:
                print(f"   ✅ NPC {npc_id} ({name}): debe ser amigable, removiendo de hostiles")
                to_remove_from_hostiles.append(npc_id)
    
    # Leer archivos completos para editar
    hostiles_content = hostiles_file.read_text(encoding='utf-8')
    amigables_content = amigables_file.read_text(encoding='utf-8')
    
    # Remover NPCs de hostiles
    if to_remove_from_hostiles:
        print(f"\n🗑️  Removiendo {len(to_remove_from_hostiles)} NPCs del archivo hostiles...")
        for npc_id in to_remove_from_hostiles:
            # Buscar y remover el bloque [[npc]] con este id
            pattern = rf'\[\[npc\]\]\nid = {npc_id}\n.*?(?=\[\[npc\]\]|\Z)'
            hostiles_content = re.sub(pattern, '', hostiles_content, flags=re.DOTALL)
    
    # Remover NPCs de amigables
    if to_remove_from_amigables:
        print(f"🗑️  Removiendo {len(to_remove_from_amigables)} NPCs del archivo amigables...")
        for npc_id in to_remove_from_amigables:
            # Buscar y remover el bloque [[npc]] con este id
            pattern = rf'\[\[npc\]\]\nid = {npc_id}\n.*?(?=\[\[npc\]\]|\Z)'
            amigables_content = re.sub(pattern, '', amigables_content, flags=re.DOTALL)
    
    # Limpiar líneas en blanco múltiples
    hostiles_content = re.sub(r'\n\n\n+', '\n\n', hostiles_content)
    amigables_content = re.sub(r'\n\n\n+', '\n\n', amigables_content)
    
    # Guardar archivos
    if to_remove_from_hostiles or to_remove_from_amigables:
        hostiles_file.write_text(hostiles_content, encoding='utf-8')
        amigables_file.write_text(amigables_content, encoding='utf-8')
        print(f"\n✅ Archivos actualizados:")
        print(f"   - {hostiles_file}")
        print(f"   - {amigables_file}")
    else:
        print("\n✅ No se requieren cambios.")


def main():
    base_dir = Path(__file__).parent.parent.parent
    hostiles_file = base_dir / 'data' / 'npcs_hostiles.toml'
    amigables_file = base_dir / 'data' / 'npcs_amigables.toml'
    npcs_dat = base_dir / 'clientes' / 'ArgentumOnline0.13.3-Cliente-Servidor' / 'server' / 'Dat' / 'NPCs.dat'
    
    if not npcs_dat.exists():
        print(f"❌ Error: No existe {npcs_dat}")
        return
    
    clean_duplicate_npcs(hostiles_file, amigables_file, npcs_dat)
    
    # Verificar resultado
    print("\n📊 Verificando resultado...")
    try:
        with open(hostiles_file, 'rb') as f:
            hostiles_data = tomllib.load(f)
            hostiles_ids = {npc['id'] for npc in hostiles_data.get('npc', [])}
        
        with open(amigables_file, 'rb') as f:
            amigables_data = tomllib.load(f)
            amigables_ids = {npc['id'] for npc in amigables_data.get('npc', [])}
        
        duplicates = hostiles_ids & amigables_ids
        if duplicates:
            print(f"   ⚠️  Aún quedan {len(duplicates)} duplicados: {sorted(list(duplicates))[:10]}")
        else:
            print(f"   ✅ No hay duplicados restantes")
            print(f"   - Hostiles: {len(hostiles_ids)} NPCs")
            print(f"   - Amigables: {len(amigables_ids)} NPCs")
            print(f"   - Total: {len(hostiles_ids) + len(amigables_ids)} NPCs únicos")
    except Exception as e:
        print(f"   ❌ Error verificando: {e}")


if __name__ == "__main__":
    main()

