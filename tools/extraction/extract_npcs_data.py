#!/usr/bin/env python3
"""
Extractor de datos completos de NPCs del cliente Argentum Online.

Extrae todos los NPCs (336 totales) desde NPCs.dat y genera
estructuras TOML con atributos, inventarios, estadísticas y comportamientos.
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional


class NPCsDataExtractor:
    def __init__(self, data_dir: Path, output_dir: Path):
        self.data_dir = data_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)

        # Tipos de NPCs según el archivo
        self.npc_types = {
            0: "NPCS COMUNES",
            1: "PUEDE RESUCITAR",
            2: "GUARDIA", 
            3: "PUEDE ENTRENAR",
            4: "BANQUEROS",
            5: "NOBLES",
            6: "DRAGONES",
            7: "TIMBEROS",
            8: "GUARDIAS DEL CAOS",
            9: "PUEDE RESUCITAR SOLAMENTE A LOS NEWBIES",
        }

        # Categorías según los headers del archivo
        self.categories = [
            "NPCS VENDECASAS",
            "NPCS RESUCITADORES", 
            "NPCS ENLISTADORES",
            "NPCS ENTRENADORES",
            "NPCS VARIOS",
            "NPCS COMERCIANTES",
            "NPCS DECORATIVOS",
            "NPCS ULLATHORPE",
            "NPCS NIX",
            "NPCS BANDERBILL",
            "NPCS LINDOS",
            "NPCS ARGHAL",
            "NPCS ARKHEIN",
            "NPCS ESPERANZA",
            "NPCS CIUDAD PERDIDA",
            "NPCS GUARDIAS ARMADA",
            "NPCS GUARDIAS LEGIÓN",
            "NPCS NO HOSTILES",
            "NPCS HOSTILES",
            "NPCS PRETORIANOS"
        ]

    def parse_npcs_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parsea el archivo completo de NPCs."""
        npcs = []
        
        try:
            with open(file_path, 'r', encoding='latin1') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Fallback a utf-8 si latin1 falla
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        
        # Dividir por bloques de NPCs
        sections = content.split('#############################################')
        current_category = "NPCS VARIOS"
        
        for section in sections:
            # Buscar bloques NPC en esta sección
            npc_blocks = re.finditer(r'\[NPC(\d+)\](.*?)(?=\n\n|\Z)', section, re.DOTALL)
            
            # Actualizar categoría basada en el contenido de la sección
            for category in self.categories:
                if category.lower() in section.lower():
                    current_category = category
                    break
            
            for match in npc_blocks:
                npc_id = match.group(1)
                block_content = match.group(2).strip()
                
                # Extraer comentario/nombre del bloque
                comment_match = re.search(r"'([^']+)", block_content)
                comment = comment_match.group(1) if comment_match else f"NPC {npc_id}"
                
                # Parsear atributos del NPC
                npc_data = self.parse_npc_attributes(npc_id, comment, current_category, block_content)
                if npc_data:
                    npcs.append(npc_data)
        
        return npcs

    def parse_npc_attributes(self, npc_id: str, comment: str, category: str, content: str) -> Optional[Dict[str, Any]]:
        """Parsear atributos individuales de un NPC."""
        npc_data = {
            "id": int(npc_id),
            "name": "",
            "category": category,
            "comment": comment,
            "npc_type": 0,
            "description": "",
            "appearance": {},
            "behavior": {},
            "combat": {},
            "inventory": {},
            "economics": {},
            "flags": {}
        }
        
        # Extraer atributos usando regex
        attributes = {
            "Name": "name",
            "NpcType": "npc_type", 
            "Desc": "description",
            "Head": ("appearance", "head"),
            "Heading": ("appearance", "heading"),
            "Body": ("appearance", "body"),
            "Movement": ("behavior", "movement"),
            "Attackable": ("flags", "attackable"),
            "ReSpawn": ("behavior", "respawn"),
            "Hostile": ("behavior", "hostile"),
            "Domable": ("flags", "domable"),
            "Alineacion": ("flags", "alignment"),
            "Comercia": ("economics", "trades"),
            "TipoItems": ("economics", "item_type"),
            "GiveEXP": ("combat", "exp_given"),
            "MinHP": ("combat", "min_hp"),
            "MaxHP": ("combat", "max_hp"),
            "MaxHIT": ("combat", "max_hit"),
            "MinHIT": ("combat", "min_hit"),
            "DEF": ("combat", "defense"),
            "DefM": ("combat", "magic_defense"),
            "PoderAtaque": ("combat", "attack_power"),
            "PoderEvasion": ("combat", "evasion_power"),
            "NROITEMS": ("inventory", "total_items"),
            "InvReSpawn": ("inventory", "respawn"),
            "BackUp": ("flags", "backup")
        }
        
        # Parsear cada atributo
        for attr_key, target_key in attributes.items():
            pattern = f'{attr_key}=([^\n\r]+)'
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                
                # Determinar el destino
                if isinstance(target_key, tuple):
                    section, key = target_key
                    if section not in npc_data:
                        npc_data[section] = {}
                    npc_data[section][key] = self.parse_value(value)
                else:
                    npc_data[target_key] = self.parse_value(value)
        
        # Extraer inventario (Obj1, Obj2, etc.)
        npc_data["inventory"]["items"] = self.parse_inventory(content)
        
        # Extraer drops (Drop1, Drop2, etc.)
        npc_data["inventory"]["drops"] = self.parse_drops(content)
        
        # Extraer sonidos (Snd1, Snd2, etc.)
        npc_data["appearance"]["sounds"] = self.parse_sounds(content)
        
        # Agregar tipo de NPC descriptivo
        npc_data["type_description"] = self.npc_types.get(npc_data["npc_type"], "DESCONOCIDO")
        
        # Agregar tags basados en atributos
        npc_data["tags"] = self.generate_npc_tags(npc_data)
        
        return npc_data

    def parse_value(self, value: str) -> Any:
        """Convierte un valor string al tipo apropiado."""
        value = value.strip().strip("'\"")
        
        # Limpiar comentarios al final
        if "'" in value:
            value = value.split("'")[0].strip()
        
        # Intentar convertir a número
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            return value

    def parse_inventory(self, content: str) -> List[Dict[str, Any]]:
        """Extrae items del inventario (Obj1, Obj2, etc.)."""
        items = []
        obj_pattern = r'Obj(\d+)=([^\n\r]+)'
        
        for match in re.finditer(obj_pattern, content, re.IGNORECASE):
            slot = int(match.group(1))
            item_data = match.group(2).strip()
            
            # Parsear "ID-cantidad" y comentarios
            parts = item_data.split()
            if parts:
                item_parts = parts[0].split('-')
                if len(item_parts) >= 2:
                    item_id = int(item_parts[0])
                    quantity = int(item_parts[1])
                    
                    # Extraer comentario del item
                    comment = ""
                    if "'" in item_data:
                        comment = item_data.split("'", 1)[1].strip()
                    
                    items.append({
                        "slot": slot,
                        "item_id": item_id,
                        "quantity": quantity,
                        "description": comment
                    })
        
        return sorted(items, key=lambda x: x["slot"])

    def parse_drops(self, content: str) -> List[Dict[str, Any]]:
        """Extrae drops del NPC (Drop1, Drop2, etc.)."""
        drops = []
        drop_pattern = r'Drop(\d+)=([^\n\r]+)'
        
        for match in re.finditer(drop_pattern, content, re.IGNORECASE):
            slot = int(match.group(1))
            drop_data = match.group(2).strip()
            
            # Limpiar comentario
            if "'" in drop_data:
                drop_data = drop_data.split("'")[0].strip()
            
            # Parsear "ID-cantidad"
            parts = drop_data.split('-')
            if len(parts) >= 2:
                try:
                    item_id = int(parts[0])
                    # Limpiar cantidad de caracteres no numéricos
                    quantity_str = re.sub(r'[^\d]', '', parts[1])
                    if quantity_str:
                        quantity = int(quantity_str)
                        
                        # Extraer comentario si existe
                        comment = ""
                        if "'" in match.group(2):
                            comment = match.group(2).split("'", 1)[1].strip()
                        
                        drops.append({
                            "slot": slot,
                            "item_id": item_id,
                            "quantity": quantity,
                            "description": comment
                        })
                except ValueError:
                    # Si no se puede parsear, saltar este drop
                    continue
        
        return sorted(drops, key=lambda x: x["slot"])

    def parse_sounds(self, content: str) -> List[int]:
        """Extrae sonidos del NPC (Snd1, Snd2, etc.)."""
        sounds = []
        sound_pattern = r'Snd(\d+)=(\d+)'
        
        for match in re.finditer(sound_pattern, content, re.IGNORECASE):
            sound_id = int(match.group(2))
            sounds.append(sound_id)
        
        return sounds

    def generate_npc_tags(self, npc_data: Dict[str, Any]) -> List[str]:
        """Genera tags basados en los atributos del NPC."""
        tags = []
        
        if npc_data.get("behavior", {}).get("hostile", 0) == 1:
            tags.append("hostil")
        else:
            tags.append("pacifico")
        
        if npc_data.get("economics", {}).get("trades", 0) == 1:
            tags.append("comerciante")
        
        if npc_data.get("combat", {}).get("exp_given", 0) > 0:
            tags.append("combate")
        
        if npc_data.get("npc_type") in [1, 9]:
            tags.append("resucitador")
        elif npc_data.get("npc_type") == 2:
            tags.append("guardia")
        elif npc_data.get("npc_type") == 3:
            tags.append("entrenador")
        elif npc_data.get("npc_type") == 4:
            tags.append("banquero")
        elif npc_data.get("npc_type") == 5:
            tags.append("noble")
        elif npc_data.get("npc_type") == 6:
            tags.append("dragon")
        elif npc_data.get("npc_type") == 7:
            tags.append("timbero")
        elif npc_data.get("npc_type") == 8:
            tags.append("guardia_caos")
        
        if npc_data.get("flags", {}).get("attackable", 0) == 1:
            tags.append("atacable")
        
        if npc_data.get("inventory", {}).get("total_items", 0) > 0:
            tags.append("con_items")
        
        return tags

    def extract_all_npcs_data(self) -> None:
        """Extrae y procesa todos los datos de NPCs."""
        print("👥 Extrayendo datos de NPCs...")
        
        # Extraer NPCs
        npcs_file = self.data_dir / "NPCs.dat"
        npcs_data = self.parse_npcs_file(npcs_file)
        print(f"✅ NPCs extraídos: {len(npcs_data)}")
        
        # Estadísticas
        hostile_count = sum(1 for npc in npcs_data if npc.get("behavior", {}).get("hostile", 0) == 1)
        traders_count = sum(1 for npc in npcs_data if npc.get("economics", {}).get("trades", 0) == 1)
        combat_count = sum(1 for npc in npcs_data if npc.get("combat", {}).get("exp_given", 0) > 0)
        
        print(f"📊 Estadísticas:")
        print(f"   - Hostiles: {hostile_count}")
        print(f"   - Comerciantes: {traders_count}")
        print(f"   - Combate: {combat_count}")
        
        # Guardar datos
        self.save_npcs_data(npcs_data)
        
        print(f"\n✅ Extracción de NPCs completada!")

    def save_npcs_data(self, npcs: List[Dict[str, Any]]) -> None:
        """Guarda los datos de NPCs en formato TOML."""
        
        # Archivo principal de NPCs
        npcs_file = self.output_dir / "npcs_complete.toml"
        npcs_toml = self.convert_npcs_to_toml(npcs)
        with open(npcs_file, 'w', encoding='utf-8') as f:
            f.write(npcs_toml)
        print(f"✅ NPCs guardados en: {npcs_file}")
        
        # Separar por categorías
        categories_npcs = {}
        for npc in npcs:
            category = npc.get("category", "NPCS VARIOS")
            if category not in categories_npcs:
                categories_npcs[category] = []
            categories_npcs[category].append(npc)
        
        # Guardar NPCs hostiles
        hostile_file = self.output_dir / "npcs_hostiles_extended.toml"
        hostile_npcs = [npc for npc in npcs if npc.get("behavior", {}).get("hostile", 0) == 1]
        hostile_toml = self.convert_npcs_to_toml(hostile_npcs, "npcs_hostiles")
        with open(hostile_file, 'w', encoding='utf-8') as f:
            f.write(hostile_toml)
        print(f"✅ NPCs hostiles guardados en: {hostile_file}")
        
        # Guardar NPCs comerciantes
        traders_file = self.output_dir / "npcs_traders_extended.toml"
        trader_npcs = [npc for npc in npcs if npc.get("economics", {}).get("trades", 0) == 1]
        trader_toml = self.convert_npcs_to_toml(trader_npcs, "npcs_traders")
        with open(traders_file, 'w', encoding='utf-8') as f:
            f.write(trader_toml)
        print(f"✅ NPCs comerciantes guardados en: {traders_file}")

    def convert_npcs_to_toml(self, npcs: List[Dict[str, Any]], section_name: str = "npcs_complete") -> str:
        """Convierte NPCs a formato TOML."""
        toml_content = []
        
        toml_content.append(f"# Datos completos de NPCs - {section_name}")
        toml_content.append(f"[{section_name}]")
        toml_content.append("")
        
        for i, npc in enumerate(npcs):
            # Validar que no haya datos corruptos
            if not npc.get("id"):
                print(f"Advertencia: NPC sin ID omitido")
                continue
                
            # Limpiar comment para que no rompa TOML
            comment = npc.get("comment", f"NPC {npc.get('id')}")
            comment = re.sub(r'\n+', ' ', comment)  # Reemplazar saltos de línea
            comment = comment.strip()
            
            # Solo agregar [appearance] si hay datos válidos
            appearance = npc.get("appearance", {})
            has_appearance = any([appearance.get("head"), appearance.get("heading"), 
                                 appearance.get("body"), appearance.get("sounds")])
            
            # Solo agregar [behavior] si hay datos válidos
            behavior = npc.get("behavior", {})
            has_behavior = any([behavior.get("movement"), "respawn" in behavior, 
                              "hostile" in behavior])
            
            # Solo agregar [combat] si hay datos
            combat = npc.get("combat", {})
            has_combat = bool(combat)
            
            # Solo agregar [economics] si hay datos
            economics = npc.get("economics", {})
            has_economics = any([economics.get("trades"), economics.get("item_type")])
            
            # Solo agregar [inventory] si hay items
            inventory = npc.get("inventory", {})
            has_inventory = bool(inventory.get("items"))
            
            # Solo agregar [inventory.drops] si hay drops
            has_drops = bool(inventory.get("drops"))
            
            # Solo agregar [flags] si hay datos
            flags = npc.get("flags", {})
            has_flags = bool(flags)
            
            # Validar que el NPC tenga al menos nombre o ID
            if not npc.get("name") and not npc.get("id"):
                print(f"Advertencia: NPC sin nombre ni ID omitido")
                continue
            
            toml_content.append(f"[[{section_name}.npcs]]")
            toml_content.append(f'id = {npc["id"]}')
            
            name = npc.get("name", "").replace('"', '\\"')  # Escapar quotes
            toml_content.append(f'name = "{name}"')
            
            toml_content.append(f'category = "{npc["category"]}"')
            toml_content.append(f'comment = "{comment}"')
            toml_content.append(f'npc_type = {npc["npc_type"]}')
            toml_content.append(f'type_description = "{npc["type_description"]}"')
            
            # Descripción
            if npc.get("description"):
                desc = npc["description"].replace('\n', ' ').replace('\r', '')
                desc = desc.replace('"', '\\"')  # Escapar quotes
                toml_content.append(f'description = """{desc}"""')
            
            # Tags
            if npc.get("tags"):
                tags_str = '", "'.join(npc["tags"])
                toml_content.append(f'tags = ["{tags_str}"]')
            
            # Apariencia
            if has_appearance:
                toml_content.append("[appearance]")
                if appearance.get("head"):
                    toml_content.append(f'head = {appearance["head"]}')
                if appearance.get("heading"):
                    toml_content.append(f'heading = {appearance["heading"]}')
                if appearance.get("body"):
                    toml_content.append(f'body = {appearance["body"]}')
                if appearance.get("sounds"):
                    sounds_str = ", ".join(map(str, appearance["sounds"]))
                    toml_content.append(f'sounds = [{sounds_str}]')
            
            # Comportamiento
            if has_behavior:
                toml_content.append("[behavior]")
                if behavior.get("movement"):
                    toml_content.append(f'movement = {behavior["movement"]}')
                if "respawn" in behavior:
                    toml_content.append(f'respawn = {behavior["respawn"]}')
                if "hostile" in behavior:
                    toml_content.append(f'hostile = {behavior["hostile"]}')
            
            # Combate
            if has_combat:
                toml_content.append("[combat]")
                for key, value in combat.items():
                    toml_content.append(f'{key} = {value}')
            
            # Economía
            if has_economics:
                toml_content.append("[economics]")
                for key, value in economics.items():
                    toml_content.append(f'{key} = {value}')
            
            # Inventario
            if has_inventory:
                toml_content.append("[inventory]")
                toml_content.append("items = [")
                for item in inventory["items"]:
                    item_str = f'{{slot = {item["slot"]}, item_id = {item["item_id"]}, quantity = {item["quantity"]}'
                    if item.get("description"):
                        item_desc = item["description"].replace('\n', ' ').replace('\r', '')
                        item_desc = item_desc.replace('"', '\\"')
                        item_str += f', description = "{item_desc}"'
                    item_str += "},"
                    toml_content.append(f"    {item_str}")
                if inventory["items"]:
                    toml_content[-1] = toml_content[-1][:-1]  # Eliminar última coma
                toml_content.append("]")
            
            # Drops
            if has_drops:
                toml_content.append("[inventory.drops]")
                toml_content.append("drops = [")
                for drop in inventory["drops"]:
                    drop_str = f'{{slot = {drop["slot"]}, item_id = {drop["item_id"]}, quantity = {drop["quantity"]}'
                    if drop.get("description"):
                        drop_desc = drop["description"].replace('\n', ' ').replace('\r', '')
                        drop_desc = drop_desc.replace('"', '\\"')
                        drop_str += f', description = "{drop_desc}"'
                    drop_str += "},"
                    toml_content.append(f"    {drop_str}")
                if inventory["drops"]:
                    toml_content[-1] = toml_content[-1][:-1]  # Eliminar última coma
                toml_content.append("]")
            
            # Flags
            if has_flags:
                toml_content.append("[flags]")
                for key, value in flags.items():
                    toml_content.append(f'{key} = {value}')
            
            toml_content.append("")
        
        return '\n'.join(toml_content)


def main():
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "clientes" / "ArgentumOnline0.13.3-Cliente-Servidor" / "server" / "Dat"
    output_dir = base_dir / "data"
    
    if not data_dir.exists():
        print(f"Error: No existe {data_dir}")
        return
    
    extractor = NPCsDataExtractor(data_dir, output_dir)
    extractor.extract_all_npcs_data()
    
    print("\n✅ Extracción de NPCs completada!")
    print("📁 Archivos generados:")
    print("   - npcs_complete.toml (todos los NPCs)")
    print("   - npcs_hostiles_extended.toml (NPCs hostiles)")
    print("   - npcs_traders_extended.toml (NPCs comerciantes)")


if __name__ == "__main__":
    main()
