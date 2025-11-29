#!/usr/bin/env python3
"""
Script para agregar todos los NPCs del archivo NPCs.dat al servidor.

Convierte los NPCs del formato VB6 al formato simple TOML usado por el servidor
y los agrega a npcs_hostiles.toml y npcs_amigables.toml.
"""

import re
import tomllib
from pathlib import Path
from typing import Any


def parse_npcs_dat(file_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parsea NPCs.dat y retorna listas de hostiles y amigables."""
    hostiles: list[dict[str, Any]] = []
    amigables: list[dict[str, Any]] = []
    
    try:
        with open(file_path, 'r', encoding='latin1') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    
    # Buscar todos los bloques [NPCXXX]
    npc_pattern = r'\[NPC(\d+)\](.*?)(?=\n\n|\[NPC|\Z)'
    
    for match in re.finditer(npc_pattern, content, re.DOTALL):
        npc_id = int(match.group(1))
        block_content = match.group(2).strip()
        
        # Extraer atributos básicos
        name_match = re.search(r'Name=([^\n\r]+)', block_content)
        name = name_match.group(1).strip() if name_match else f"NPC{npc_id}"
        
        # Limpiar nombre de comillas
        name = name.strip('"\'')
        
        # Hostile
        hostile_match = re.search(r'Hostile=(\d+)', block_content)
        is_hostile = int(hostile_match.group(1)) if hostile_match else 0
        
        # Attackable
        attackable_match = re.search(r'Attackable=(\d+)', block_content)
        is_attackable = int(attackable_match.group(1)) if attackable_match else 0
        
        # Body
        body_match = re.search(r'Body=(\d+)', block_content)
        body_id = int(body_match.group(1)) if body_match else 0
        
        # Head
        head_match = re.search(r'Head=(\d+)', block_content)
        head_id = int(head_match.group(1)) if head_match else 0
        
        # Desc
        desc_match = re.search(r'Desc=([^\n\r]+)', block_content)
        description = desc_match.group(1).strip().strip('"\'') if desc_match else ""
        
        # Combat stats
        min_hp_match = re.search(r'MinHP=(\d+)', block_content)
        max_hp_match = re.search(r'MaxHP=(\d+)', block_content)
        min_hit_match = re.search(r'MinHIT=(\d+)', block_content)
        max_hit_match = re.search(r'MaxHIT=(\d+)', block_content)
        
        min_hp = int(min_hp_match.group(1)) if min_hp_match else 0
        max_hp = int(max_hp_match.group(1)) if max_hp_match else min_hp
        min_hit = int(min_hit_match.group(1)) if min_hit_match else 0
        max_hit = int(max_hit_match.group(1)) if max_hit_match else min_hit
        
        # EXP (para calcular nivel aproximado)
        exp_match = re.search(r'GiveEXP=(\d+)', block_content)
        exp_given = int(exp_match.group(1)) if exp_match else 0
        
        # Nivel aproximado basado en EXP
        level = max(1, min(100, exp_given // 10)) if exp_given > 0 else 0
        
        # NpcType
        npc_type_match = re.search(r'NpcType=(\d+)', block_content)
        npc_type = int(npc_type_match.group(1)) if npc_type_match else 0
        
        # Comercia
        comercia_match = re.search(r'Comercia=(\d+)', block_content)
        is_merchant = int(comercia_match.group(1)) if comercia_match else 0
        
        # Respawn
        respawn_match = re.search(r'ReSpawn=(\d+)', block_content)
        has_respawn = int(respawn_match.group(1)) if respawn_match else 0
        
        # Oro de drops
        gold_min, gold_max = 0, 0
        drop_matches = re.finditer(r'Drop\d+=12-(\d+)', block_content)
        gold_amounts = [int(m.group(1)) for m in drop_matches]
        if gold_amounts:
            gold_min = min(gold_amounts)
            gold_max = max(gold_amounts)
        
        # Construir NPC data
        npc_data = {
            'id': npc_id,
            'nombre': name,
            'descripcion': description or f"Un {name.lower()}.",
            'body_id': body_id,
            'head_id': head_id,
            'es_hostil': bool(is_hostile),
            'es_atacable': bool(is_attackable),
            'nivel': level,
            'hp_max': max_hp,
            'oro_min': gold_min,
            'oro_max': gold_max,
            'respawn_time': 60 if has_respawn and is_hostile else 0,
            'respawn_time_max': 120 if has_respawn and is_hostile else 0,
        }
        
        # Agregar campos específicos según tipo
        if is_hostile:
            # Calcular ataque promedio
            attack_avg = (min_hit + max_hit) // 2 if max_hit > 0 else max_hp // 10
            npc_data['ataque'] = max(1, attack_avg)
            npc_data['cooldown_ataque'] = 3.0
            npc_data['rango_agresion'] = 8
            hostiles.append(npc_data)
        else:
            # NPCs amigables
            npc_data['es_mercader'] = bool(is_merchant)
            npc_data['es_banquero'] = bool(npc_type == 4)  # Tipo 4 = Banquero
            amigables.append(npc_data)
    
    return hostiles, amigables


def load_existing_npcs(file_path: Path) -> dict[int, dict[str, Any]]:
    """Carga NPCs existentes desde un archivo TOML."""
    if not file_path.exists():
        return {}
    
    existing: dict[int, dict[str, Any]] = {}
    try:
        with open(file_path, 'rb') as f:
            data = tomllib.load(f)
            for npc in data.get('npc', []):
                npc_id = npc.get('id')
                if npc_id:
                    existing[npc_id] = npc
    except Exception as e:
        print(f"Error cargando {file_path}: {e}")
    
    return existing


def escape_toml_string(text: str) -> str:
    """Escapa una cadena para formato TOML."""
    # Escapar comillas dobles y saltos de línea
    text = text.replace('\\', '\\\\')
    text = text.replace('"', '\\"')
    text = text.replace('\n', '\\n')
    text = text.replace('\r', '')
    return text


def convert_to_toml_format(npc: dict[str, Any]) -> str:
    """Convierte un NPC dict al formato TOML simple."""
    lines = ['[[npc]]']
    lines.append(f'id = {npc["id"]}')
    nombre_escaped = escape_toml_string(str(npc["nombre"]))
    lines.append(f'nombre = "{nombre_escaped}"')
    desc_escaped = escape_toml_string(str(npc["descripcion"]))
    lines.append(f'descripcion = "{desc_escaped}"')
    lines.append(f'body_id = {npc["body_id"]}')
    lines.append(f'head_id = {npc["head_id"]}')
    lines.append(f'es_hostil = {str(npc["es_hostil"]).lower()}')
    lines.append(f'es_atacable = {str(npc["es_atacable"]).lower()}')
    lines.append(f'nivel = {npc["nivel"]}')
    lines.append(f'hp_max = {npc["hp_max"]}')
    lines.append(f'oro_min = {npc["oro_min"]}')
    lines.append(f'oro_max = {npc["oro_max"]}')
    lines.append(f'respawn_time = {npc["respawn_time"]}')
    lines.append(f'respawn_time_max = {npc["respawn_time_max"]}')
    
    if npc.get('ataque'):
        lines.append(f'ataque = {npc["ataque"]}')
        lines.append(f'cooldown_ataque = {npc["cooldown_ataque"]}')
        lines.append(f'rango_agresion = {npc["rango_agresion"]}')
    
    if npc.get('es_mercader'):
        lines.append('es_mercader = true')
    
    if npc.get('es_banquero'):
        lines.append('es_banquero = true')
    
    lines.append('')  # Línea en blanco
    return '\n'.join(lines)


def main():
    base_dir = Path(__file__).parent.parent.parent
    npcs_dat = base_dir / 'clientes' / 'ArgentumOnline0.13.3-Cliente-Servidor' / 'server' / 'Dat' / 'NPCs.dat'
    hostiles_file = base_dir / 'data' / 'npcs_hostiles.toml'
    amigables_file = base_dir / 'data' / 'npcs_amigables.toml'
    
    if not npcs_dat.exists():
        print(f"Error: No existe {npcs_dat}")
        return
    
    print("📖 Parseando NPCs.dat...")
    hostiles, amigables = parse_npcs_dat(npcs_dat)
    print(f"✅ Parseados: {len(hostiles)} hostiles, {len(amigables)} amigables")
    
    # Cargar NPCs existentes
    existing_hostiles = load_existing_npcs(hostiles_file)
    existing_amigables = load_existing_npcs(amigables_file)
    
    print(f"📋 NPCs existentes: {len(existing_hostiles)} hostiles, {len(existing_amigables)} amigables")
    
    # Filtrar NPCs nuevos
    new_hostiles = [npc for npc in hostiles if npc['id'] not in existing_hostiles]
    new_amigables = [npc for npc in amigables if npc['id'] not in existing_amigables]
    
    print(f"🆕 NPCs nuevos: {len(new_hostiles)} hostiles, {len(new_amigables)} amigables")
    
    # Leer archivos actuales
    hostiles_content = hostiles_file.read_text() if hostiles_file.exists() else "# NPCs Hostiles\n\n"
    amigables_content = amigables_file.read_text() if amigables_file.exists() else "# NPCs Amigables\n\n"
    
    # Agregar NPCs nuevos
    if new_hostiles:
        hostiles_content += "\n# NPCs agregados desde NPCs.dat\n"
        for npc in sorted(new_hostiles, key=lambda x: x['id']):
            hostiles_content += convert_to_toml_format(npc)
    
    if new_amigables:
        amigables_content += "\n# NPCs agregados desde NPCs.dat\n"
        for npc in sorted(new_amigables, key=lambda x: x['id']):
            amigables_content += convert_to_toml_format(npc)
    
    # Verificar que no haya duplicados (IDs que ya existen pero no están en la lista de existentes)
    # Esto puede pasar si el script se ejecuta múltiples veces
    print(f"⚠️  Verificando duplicados...")
    
    # Re-cargar para verificar
    try:
        test_hostiles = load_existing_npcs(hostiles_file)
        test_amigables = load_existing_npcs(amigables_file)
        if test_hostiles or test_amigables:
            print(f"   - Archivos válidos: ✅")
        else:
            print(f"   - Archivos válidos: ❌ (error de formato)")
    except Exception as e:
        print(f"   - Error validando archivos: {e}")
    
    # Guardar archivos
    hostiles_file.write_text(hostiles_content)
    amigables_file.write_text(amigables_content)
    
    print(f"✅ Archivos actualizados:")
    print(f"   - {hostiles_file}")
    print(f"   - {amigables_file}")


if __name__ == "__main__":
    main()

