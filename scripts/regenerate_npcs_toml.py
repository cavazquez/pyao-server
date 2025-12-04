#!/usr/bin/env python3
"""Regenera los archivos TOML de NPCs desde el dat de VB6.

Este script lee NPCs.dat del servidor VB6 original y genera archivos TOML
con formato válido.
"""

import re
import sys
from pathlib import Path


def parse_ini_section(content: str) -> dict:
    """Parsea una sección INI y retorna un diccionario."""
    result = {}
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith("'") or line.startswith('#'):
            continue
        if '=' in line:
            key, value = line.split('=', 1)
            value = value.strip()
            # Quitar comentarios VB6 (empiezan con ')
            if "'" in value:
                value = value.split("'")[0].strip()
            result[key.strip()] = value
    return result


def parse_npcs_dat(filepath: Path) -> list[dict]:
    """Parsea el archivo NPCs.dat de VB6."""
    content = filepath.read_text(encoding='latin-1')
    
    # Buscar todas las secciones [NPC###]
    pattern = r'\[NPC(\d+)\](.*?)(?=\[NPC\d+\]|\[INIT\]|$)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    npcs = []
    for npc_id_str, section_content in matches:
        npc_id = int(npc_id_str)
        data = parse_ini_section(section_content)
        
        if not data.get('Name'):
            continue
        
        # Determinar categoría basada en características
        hostile = int(data.get('Hostile', 0))
        trades = int(data.get('Comercia', 0))
        npc_type = int(data.get('NpcType', 0))
        
        # Categorizar NPCs
        if hostile:
            category = "NPCS HOSTILES"
        elif trades:
            category = "NPCS COMERCIANTES"
        elif npc_type == 1:
            category = "NPCS RESUCITADORES"
        elif npc_type == 2:
            category = "NPCS GUARDIAS"
        elif npc_type == 3:
            category = "NPCS ENTRENADORES"
        elif npc_type == 4:
            category = "NPCS BANQUEROS"
        else:
            category = "NPCS VARIOS"
        
        # Generar tags
        tags = []
        if hostile:
            tags.append("hostil")
        else:
            tags.append("pacifico")
        if trades:
            tags.append("comerciante")
        
        # Extraer campos
        npc = {
            'id': npc_id,
            'name': data.get('Name', ''),
            'npc_type': npc_type,
            'category': category,
            'tags': tags,
            'description': data.get('Desc', ''),
            'head': int(data.get('Head', 0)),
            'body': int(data.get('Body', 0)),
            'heading': int(data.get('Heading', 3)),
            'movement': int(data.get('Movement', 0)),
            'hostile': hostile,
            'attackable': int(data.get('Attackable', 0)),
            'respawn': int(data.get('ReSpawn', 0)),
            'domable': int(data.get('Domable', 0)),
            'alignment': int(data.get('Alineacion', 0)),
            'trades': trades,
            'item_type': int(data.get('TipoItems', 0)),
            'backup': int(data.get('BackUp', 0)),
        }
        
        # Extraer stats de combate si existen
        if 'MaxHP' in data:
            npc['max_hp'] = int(data.get('MaxHP', 100))
            npc['min_hp'] = int(data.get('MinHP', 1))
        if 'MaxHit' in data:
            npc['max_hit'] = int(data.get('MaxHit', 0))
            npc['min_hit'] = int(data.get('MinHit', 0))
        if 'DEF' in data:
            npc['defense'] = int(data.get('DEF', 0))
        if 'EXP' in data:
            npc['exp'] = int(data.get('EXP', 0))
        if 'GiveGLD' in data:
            npc['gold_min'] = int(data.get('GiveGLDMin', 0))
            npc['gold_max'] = int(data.get('GiveGLDMax', 0))
        
        # Extraer inventario si comercia
        if npc['trades']:
            items = []
            num_items = int(data.get('NROITEMS', 0))
            for i in range(1, num_items + 1):
                obj_data = data.get(f'Obj{i}', '')
                if obj_data and '-' in obj_data:
                    item_id, qty = obj_data.split('-')
                    items.append({
                        'slot': i,
                        'item_id': int(item_id),
                        'quantity': int(qty)
                    })
            if items:
                npc['inventory'] = items
        
        npcs.append(npc)
    
    return npcs


def escape_string(s: str) -> str:
    """Escapa una cadena para TOML."""
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')


def generate_toml(npcs: list[dict], section_name: str) -> str:
    """Genera contenido TOML para los NPCs."""
    lines = [
        f"# NPCs de Argentum Online - {section_name}",
        f"# Generado automáticamente desde NPCs.dat",
        f"# Total: {len(npcs)} NPCs",
        "",
        f"[{section_name}]",
        "",
    ]
    
    for npc in npcs:
        lines.append(f"[[{section_name}.npcs]]")
        lines.append(f"id = {npc['id']}")
        lines.append(f'name = "{escape_string(npc["name"])}"')
        lines.append(f'category = "{npc["category"]}"')
        lines.append(f"npc_type = {npc['npc_type']}")
        
        # Tags como array
        tags_str = ', '.join(f'"{t}"' for t in npc['tags'])
        lines.append(f'tags = [{tags_str}]')
        
        if npc['description']:
            desc = escape_string(npc['description'])
            lines.append(f'description = "{desc}"')
        
        # Appearance inline
        lines.append(f"appearance = {{ head = {npc['head']}, body = {npc['body']}, heading = {npc['heading']} }}")
        
        # Behavior inline
        lines.append(f"behavior = {{ movement = {npc['movement']}, hostile = {npc['hostile']}, respawn = {npc['respawn']} }}")
        
        # Flags inline
        lines.append(f"flags = {{ attackable = {npc['attackable']}, domable = {npc['domable']}, alignment = {npc['alignment']}, backup = {npc['backup']} }}")
        
        # Economics si comercia
        if npc['trades']:
            lines.append(f"economics = {{ trades = 1, item_type = {npc['item_type']} }}")
        
        # Combat stats si existen
        combat_parts = []
        if 'max_hp' in npc:
            combat_parts.append(f"max_hp = {npc['max_hp']}")
            combat_parts.append(f"min_hp = {npc['min_hp']}")
        if 'max_hit' in npc:
            combat_parts.append(f"max_hit = {npc['max_hit']}")
            combat_parts.append(f"min_hit = {npc['min_hit']}")
        if 'defense' in npc:
            combat_parts.append(f"defense = {npc['defense']}")
        if 'exp' in npc:
            combat_parts.append(f"exp = {npc['exp']}")
        if 'gold_min' in npc:
            combat_parts.append(f"gold_min = {npc['gold_min']}")
            combat_parts.append(f"gold_max = {npc['gold_max']}")
        
        if combat_parts:
            lines.append(f"combat = {{ {', '.join(combat_parts)} }}")
        
        # Inventory si existe
        if 'inventory' in npc and npc['inventory']:
            items_str = ', '.join(
                f'{{ slot = {i["slot"]}, item_id = {i["item_id"]}, quantity = {i["quantity"]} }}'
                for i in npc['inventory']
            )
            lines.append(f"inventory = {{ items = [{items_str}] }}")
        
        lines.append("")
    
    return '\n'.join(lines)


def main() -> int:
    """Ejecuta la regeneración."""
    vb6_dat = Path('/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Dat/NPCs.dat')
    
    if not vb6_dat.exists():
        print(f"❌ Archivo no encontrado: {vb6_dat}")
        return 1
    
    print(f"📄 Leyendo: {vb6_dat}")
    npcs = parse_npcs_dat(vb6_dat)
    print(f"   → {len(npcs)} NPCs parseados")
    
    # Clasificar NPCs
    npcs_completos = npcs
    npcs_hostiles = [n for n in npcs if n['hostile'] == 1]
    npcs_traders = [n for n in npcs if n['trades'] == 1]
    
    print(f"   → {len(npcs_hostiles)} hostiles")
    print(f"   → {len(npcs_traders)} comerciantes")
    
    data_dir = Path('data')
    
    # Generar npcs_complete.toml
    complete_path = data_dir / 'npcs_complete_new.toml'
    complete_toml = generate_toml(npcs_completos, 'npcs_complete')
    complete_path.write_text(complete_toml, encoding='utf-8')
    print(f"✅ Generado: {complete_path}")
    
    # Generar npcs_hostiles_extended.toml
    hostiles_path = data_dir / 'npcs_hostiles_new.toml'
    hostiles_toml = generate_toml(npcs_hostiles, 'npcs_hostiles')
    hostiles_path.write_text(hostiles_toml, encoding='utf-8')
    print(f"✅ Generado: {hostiles_path}")
    
    # Generar npcs_traders_extended.toml
    traders_path = data_dir / 'npcs_traders_new.toml'
    traders_toml = generate_toml(npcs_traders, 'npcs_traders')
    traders_path.write_text(traders_toml, encoding='utf-8')
    print(f"✅ Generado: {traders_path}")
    
    # Validar
    import tomllib
    for path in [complete_path, hostiles_path, traders_path]:
        try:
            with path.open('rb') as f:
                data = tomllib.load(f)
            section = list(data.keys())[0]
            count = len(data[section].get('npcs', []))
            print(f"   ✓ {path.name}: {count} NPCs válidos")
        except Exception as e:
            print(f"   ✗ {path.name}: {e}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

