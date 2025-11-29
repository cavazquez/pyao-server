#!/usr/bin/env python3
"""
Script para extraer todos los hechizos del archivo Hechizos.dat del VB6
y convertirlos al formato TOML usado por el servidor.

Extrae los 46 hechizos del archivo original y los convierte al formato del servidor.
"""

import re
import tomllib
from pathlib import Path
from typing import Any


def parse_spells_dat(file_path: Path) -> list[dict[str, Any]]:
    """Parsea Hechizos.dat y retorna lista de hechizos."""
    spells: list[dict[str, Any]] = []
    
    try:
        with open(file_path, 'r', encoding='latin1') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    
    # Buscar todos los bloques [HECHIZOXXX]
    spell_pattern = r'\[HECHIZO(\d+)\](.*?)(?=\[HECHIZO|\Z)'
    
    for match in re.finditer(spell_pattern, content, re.DOTALL):
        spell_id = int(match.group(1))
        block_content = match.group(2).strip()
        
        # Extraer campos básicos
        nombre_match = re.search(r'Nombre=([^\n\r]+)', block_content)
        nombre = nombre_match.group(1).strip() if nombre_match else f"Hechizo {spell_id}"
        nombre = nombre.strip('"\'')
        
        # Descripción
        desc_match = re.search(r'Desc=([^\n\r]+)', block_content)
        description = desc_match.group(1).strip().strip('"\'') if desc_match else ""
        
        # Palabras mágicas
        palabras_match = re.search(r'PalabrasMagicas=([^\n\r]+)', block_content)
        magic_words = palabras_match.group(1).strip().strip('"\'') if palabras_match else ""
        
        # Mensajes
        hechizero_msg_match = re.search(r'HechizeroMsg=([^\n\r]+)', block_content)
        caster_msg = hechizero_msg_match.group(1).strip().strip('"\'') if hechizero_msg_match else ""
        
        propio_msg_match = re.search(r'PropioMsg=([^\n\r]+)', block_content)
        self_msg = propio_msg_match.group(1).strip().strip('"\'') if propio_msg_match else ""
        
        target_msg_match = re.search(r'TargetMsg=([^\n\r]+)', block_content)
        target_msg = target_msg_match.group(1).strip().strip('"\'') if target_msg_match else ""
        
        # Tipo y Target
        tipo_match = re.search(r'Tipo=(\d+)', block_content)
        spell_type = int(tipo_match.group(1)) if tipo_match else 1
        
        target_match = re.search(r'Target=(\d+)', block_content)
        target = int(target_match.group(1)) if target_match else 1
        
        # Recursos
        mana_match = re.search(r'ManaRequerido=(\d+)', block_content)
        mana_cost = int(mana_match.group(1)) if mana_match else 0
        
        sta_match = re.search(r'StaRequerido=(\d+)', block_content)
        stamina_cost = int(sta_match.group(1)) if sta_match else 0
        
        min_skill_match = re.search(r'MinSkill=(\d+)', block_content)
        min_skill = int(min_skill_match.group(1)) if min_skill_match else 0
        
        # Daño/Cura HP
        # SubeHP=1: Cura, SubeHP=2: Daña
        sube_hp_match = re.search(r'SubeHP=(\d+)', block_content)
        sube_hp = int(sube_hp_match.group(1)) if sube_hp_match else 0
        
        min_hp_match = re.search(r'MinHP=(\d+)', block_content)
        max_hp_match = re.search(r'MaxHP=(\d+)', block_content)
        min_hp = int(min_hp_match.group(1)) if min_hp_match else 0
        max_hp = int(max_hp_match.group(1)) if max_hp_match else 0
        
        # Determinar si es daño o cura
        if sube_hp == 1:  # Cura
            min_damage = min_hp
            max_damage = max_hp
        elif sube_hp == 2:  # Daño
            min_damage = min_hp
            max_damage = max_hp
        else:
            min_damage = 0
            max_damage = 0
        
        # Sonido y efectos
        wav_match = re.search(r'WAV=(\d+)', block_content)
        wav = int(wav_match.group(1)) if wav_match else 0
        
        fx_grh_match = re.search(r'FXgrh=(\d+)', block_content)
        fx_grh = int(fx_grh_match.group(1)) if fx_grh_match else 0
        
        loops_match = re.search(r'Loops=(\d+)', block_content)
        loops = int(loops_match.group(1)) if loops_match else 0
        
        # Efectos de estado (0 o 1)
        def get_bool_field(pattern: str) -> bool:
            match = re.search(pattern + r'=(\d+)', block_content)
            return int(match.group(1)) > 0 if match else False
        
        # Construir diccionario del hechizo
        spell_data: dict[str, Any] = {
            "id": spell_id,
            "name": nombre,
            "description": description,
            "magic_words": magic_words,
            "type": spell_type,
            "target": target,
            "mana_cost": mana_cost,
            "stamina_cost": stamina_cost,
            "min_skill": min_skill,
            "min_damage": min_damage,
            "max_damage": max_damage,
            "wav": wav,
            "fx_grh": fx_grh,
            "loops": loops,
        }
        
        # Mensajes (solo si existen)
        if caster_msg:
            spell_data["caster_msg"] = caster_msg
        if self_msg:
            spell_data["self_msg"] = self_msg
        if target_msg:
            spell_data["target_msg"] = target_msg
        
        # Efectos de estado
        spell_data["cures_poison"] = get_bool_field(r'CuraVeneno')
        spell_data["poisons"] = get_bool_field(r'Envenena')
        spell_data["paralyzes"] = get_bool_field(r'Paraliza')
        spell_data["immobilizes"] = get_bool_field(r'Inmoviliza')
        spell_data["blinds"] = get_bool_field(r'Ceguera')
        spell_data["dumbs"] = get_bool_field(r'Estupidez')
        spell_data["removes_paralysis"] = get_bool_field(r'RemoverParalisis')
        spell_data["removes_stupidity"] = get_bool_field(r'RemoverEstupidez')
        spell_data["makes_invisible"] = get_bool_field(r'Invisibilidad')
        spell_data["removes_invisibility"] = get_bool_field(r'RemueveInvisibilidadParcial')
        spell_data["revives"] = get_bool_field(r'Revivir')
        
        # Invocación
        spell_data["invokes"] = get_bool_field(r'Invoca')
        num_npc_match = re.search(r'NumNpc=(\d+)', block_content)
        spell_data["invoke_npc_id"] = int(num_npc_match.group(1)) if num_npc_match else 0
        cant_match = re.search(r'Cant=(\d+)', block_content)
        spell_data["invoke_count"] = int(cant_match.group(1)) if cant_match else 0
        
        # Materialización
        spell_data["materializes"] = get_bool_field(r'Materializa')
        item_index_match = re.search(r'itemindex=(\d+)', block_content)
        spell_data["materialize_item_id"] = int(item_index_match.group(1)) if item_index_match else 0
        
        # Metamorfosis
        spell_data["morphs"] = get_bool_field(r'Mimetiza')
        
        # Warp (para mascotas)
        spell_data["warps_pet"] = get_bool_field(r'Warp')
        
        # Staff
        spell_data["staff_affected"] = get_bool_field(r'StaffAffected')
        spell_data["need_staff"] = get_bool_field(r'NeedStaff')
        
        # Resis (resistencia)
        resis_match = re.search(r'Resis=(\d+)', block_content)
        spell_data["resis"] = int(resis_match.group(1)) if resis_match else 0
        
        # SubeHP flag (para saber si cura o daña)
        spell_data["heals_hp"] = (sube_hp == 1)
        
        spells.append(spell_data)
    
    return spells


def convert_to_toml_format(spells: list[dict[str, Any]]) -> str:
    """Convierte la lista de hechizos a formato TOML."""
    lines = [
        "# Catálogo de Hechizos de Argentum Online",
        "# Extraído de Hechizos.dat del servidor VB6 original",
        "# Total: 46 hechizos",
        "",
    ]
    
    for spell in sorted(spells, key=lambda x: x["id"]):
        lines.append("[[spell]]")
        lines.append(f'id = {spell["id"]}')
        lines.append(f'name = "{spell["name"]}"')
        
        # Descripción (puede tener múltiples líneas o caracteres especiales)
        desc = spell["description"].replace('"', '\\"').replace('\n', ' ').replace('\r', '')
        lines.append(f'description = "{desc}"')
        
        lines.append(f'magic_words = "{spell["magic_words"]}"')
        lines.append(f"type = {spell['type']}")
        lines.append(f"target = {spell['target']}")
        lines.append(f"mana_cost = {spell['mana_cost']}")
        lines.append(f"stamina_cost = {spell['stamina_cost']}")
        lines.append(f"min_skill = {spell['min_skill']}")
        lines.append(f"min_damage = {spell['min_damage']}")
        lines.append(f"max_damage = {spell['max_damage']}")
        lines.append(f"wav = {spell['wav']}")
        lines.append(f"fx_grh = {spell['fx_grh']}")
        lines.append(f"loops = {spell['loops']}")
        
        # Mensajes (opcionales)
        if spell.get("caster_msg"):
            lines.append(f'caster_msg = "{spell["caster_msg"]}"')
        if spell.get("self_msg"):
            lines.append(f'self_msg = "{spell["self_msg"]}"')
        if spell.get("target_msg"):
            lines.append(f'target_msg = "{spell["target_msg"]}"')
        
        # Efectos de estado (solo si están activos)
        if spell.get("cures_poison"):
            lines.append("cures_poison = true")
        if spell.get("poisons"):
            lines.append("poisons = true")
        if spell.get("paralyzes"):
            lines.append("paralyzes = true")
        if spell.get("immobilizes"):
            lines.append("immobilizes = true")
        if spell.get("blinds"):
            lines.append("blinds = true")
        if spell.get("dumbs"):
            lines.append("dumbs = true")
        if spell.get("removes_paralysis"):
            lines.append("removes_paralysis = true")
        if spell.get("removes_stupidity"):
            lines.append("removes_stupidity = true")
        if spell.get("makes_invisible"):
            lines.append("makes_invisible = true")
        if spell.get("removes_invisibility"):
            lines.append("removes_invisibility = true")
        if spell.get("revives"):
            lines.append("revives = true")
        
        # Invocación
        if spell.get("invokes"):
            lines.append("invokes = true")
            if spell.get("invoke_npc_id"):
                lines.append(f"invoke_npc_id = {spell['invoke_npc_id']}")
            if spell.get("invoke_count"):
                lines.append(f"invoke_count = {spell['invoke_count']}")
        
        # Materialización
        if spell.get("materializes"):
            lines.append("materializes = true")
            if spell.get("materialize_item_id"):
                lines.append(f"materialize_item_id = {spell['materialize_item_id']}")
        
        # Metamorfosis
        if spell.get("morphs"):
            lines.append("morphs = true")
        
        # Warp
        if spell.get("warps_pet"):
            lines.append("warps_pet = true")
        
        # Staff
        if spell.get("staff_affected"):
            lines.append("staff_affected = true")
        if spell.get("need_staff"):
            lines.append("need_staff = true")
        
        # Heals HP
        if spell.get("heals_hp"):
            lines.append("heals_hp = true")
        
        # Resis
        if spell.get("resis"):
            lines.append(f"resis = {spell['resis']}")
        
        lines.append("")  # Línea en blanco entre hechizos
    
    return "\n".join(lines)


def main():
    """Función principal."""
    base_path = Path(__file__).parent.parent.parent
    hechizos_dat_path = base_path / "clientes" / "ArgentumOnline0.13.3-Cliente-Servidor" / "server" / "Dat" / "Hechizos.dat"
    spells_toml_path = base_path / "data" / "spells.toml"
    
    if not hechizos_dat_path.exists():
        print(f"❌ Error: No se encontró el archivo {hechizos_dat_path}")
        return
    
    print(f"📖 Leyendo hechizos desde {hechizos_dat_path}...")
    spells = parse_spells_dat(hechizos_dat_path)
    
    print(f"✅ Se encontraron {len(spells)} hechizos")
    
    # Convertir a formato TOML
    print("🔄 Convirtiendo a formato TOML...")
    toml_content = convert_to_toml_format(spells)
    
    # Guardar en archivo
    print(f"💾 Guardando en {spells_toml_path}...")
    spells_toml_path.write_text(toml_content, encoding='utf-8')
    
    print(f"✅ ¡Hechizos exportados exitosamente!")
    print(f"   Total: {len(spells)} hechizos")
    print(f"   Archivo: {spells_toml_path}")
    
    # Mostrar resumen
    print("\n📊 Resumen:")
    print(f"   - Hechizos de daño: {sum(1 for s in spells if s.get('min_damage', 0) > 0 and not s.get('heals_hp'))}")
    print(f"   - Hechizos de curación: {sum(1 for s in spells if s.get('heals_hp'))}")
    print(f"   - Hechizos de estado: {sum(1 for s in spells if any([s.get('paralyzes'), s.get('poisons'), s.get('immobilizes'), s.get('blinds'), s.get('dumbs')]))}")
    print(f"   - Hechizos de invocación: {sum(1 for s in spells if s.get('invokes'))}")
    print(f"   - Hechizos de materialización: {sum(1 for s in spells if s.get('materializes'))}")


if __name__ == "__main__":
    main()

