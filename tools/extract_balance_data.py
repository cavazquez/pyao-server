#!/usr/bin/env python3
"""
Extractor de datos de Balance.dat del cliente Argentum Online.

Convierte los datos de balance del formato .dat a TOML estructurado.
"""

import re
from pathlib import Path
from typing import Dict, List, Any


class BalanceDataExtractor:
    def __init__(self, balance_file: Path, output_dir: Path):
        self.balance_file = balance_file
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)

    def parse_balance_dat(self) -> Dict[str, Dict[str, Any]]:
        """Parsea el archivo Balance.dat y extrae todas las secciones."""
        balance_data = {}
        current_section = None
        
        try:
            with open(self.balance_file, 'r', encoding='latin1') as f:
                for line in f:
                    line = line.strip()
                    
                    # Detectar sección
                    if line.startswith('[') and line.endswith(']'):
                        current_section = line[1:-1]
                        balance_data[current_section] = {}
                        continue
                    
                    # Parsear clave=valor
                    if '=' in line and current_section:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Convertir valores numéricos
                        if value.startswith('+') or value.startswith('-'):
                            try:
                                value = int(value)
                            except ValueError:
                                pass
                        else:
                            try:
                                if '.' in value:
                                    value = float(value)
                                else:
                                    value = int(value)
                            except ValueError:
                                pass
                        
                        balance_data[current_section][key] = value
                        
        except Exception as e:
            print(f"Error leyendo Balance.dat: {e}")
            
        return balance_data

    def convert_to_toml(self, balance_data: Dict[str, Dict[str, Any]]) -> str:
        """Convierte los datos de balance a formato TOML."""
        toml_content = []
        
        # Sección de razas
        if 'MODRAZA' in balance_data:
            toml_content.append("# Modificadores de atributos por raza")
            toml_content.append("[racial_modifiers]")
            
            race_data = balance_data['MODRAZA']
            races = {}
            
            # Agrupar por raza
            for key, value in race_data.items():
                if 'Fuerza' in key:
                    race = key.replace('Fuerza', '')
                    if race not in races:
                        races[race] = {}
                    races[race]['strength'] = value
                elif 'Agilidad' in key:
                    race = key.replace('Agilidad', '')
                    if race not in races:
                        races[race] = {}
                    races[race]['agility'] = value
                elif 'Inteligencia' in key:
                    race = key.replace('Inteligencia', '')
                    if race not in races:
                        races[race] = {}
                    races[race]['intelligence'] = value
                elif 'Carisma' in key:
                    race = key.replace('Carisma', '')
                    if race not in races:
                        races[race] = {}
                    races[race]['charisma'] = value
                elif 'Constitucion' in key:
                    race = key.replace('Constitucion', '')
                    if race not in races:
                        races[race] = {}
                    races[race]['constitution'] = value
            
            for race, stats in races.items():
                toml_content.append(f'[[racial_modifiers.races]]')
                toml_content.append(f'name = "{race}"')
                for stat, value in stats.items():
                    toml_content.append(f'{stat} = {value}')
                toml_content.append('')
        
        # Sección de clases - modificadores de combate
        combat_sections = [
            ('MODEVASION', 'Evasion'),
            ('MODATAQUEARMAS', 'Melee Attack'),
            ('MODATAQUEPROYECTILES', 'Ranged Attack'),
            ('MODATAQUEWRESTLING', 'Wrestling Attack'),
            ('MODDAÑOARMAS', 'Melee Damage'),
            ('MODDAÑOPROYECTILES', 'Ranged Damage'),
            ('MODESCUDO', 'Shield'),
            ('MODVIDA', 'Health')
        ]
        
        class_modifiers = {}
        
        for section_key, section_name in combat_sections:
            if section_key in balance_data:
                for class_name, value in balance_data[section_key].items():
                    if class_name not in class_modifiers:
                        class_modifiers[class_name] = {}
                    
                    # Convertir nombres de sección a claves TOML
                    toml_key = section_key.lower().replace('mod', '').replace('daño', 'damage').replace('ñ', 'n')
                    class_modifiers[class_name][toml_key] = value
        
        if class_modifiers:
            toml_content.append("# Modificadores de combate por clase")
            toml_content.append("[class_modifiers]")
            
            for class_name, modifiers in class_modifiers.items():
                toml_content.append(f'[[class_modifiers.classes]]')
                toml_content.append(f'name = "{class_name}"')
                for mod_key, value in modifiers.items():
                    toml_content.append(f'{mod_key} = {value}')
                toml_content.append('')
        
        # Otras secciones (DISTRIBUCION, EXTRA, PARTY, RECOMPENSAFACCION)
        other_sections = ['DISTRIBUCION', 'EXTRA', 'PARTY', 'RECOMPENSAFACCION']
        
        for section in other_sections:
            if section in balance_data:
                toml_content.append(f"# {section}")
                toml_content.append(f'[{section.lower()}]')
                
                for key, value in balance_data[section].items():
                    toml_content.append(f'{key.lower()} = {value}')
                toml_content.append('')
        
        return '\n'.join(toml_content)

    def extract_and_save(self):
        """Extrae y guarda los datos de balance en formato TOML."""
        print("🔧 Extrayendo datos de Balance.dat...")
        
        # Parsear archivo .dat
        balance_data = self.parse_balance_dat()
        print(f"✅ Secciones extraídas: {list(balance_data.keys())}")
        
        # Convertir a TOML
        toml_content = self.convert_to_toml(balance_data)
        
        # Guardar archivo
        output_file = self.output_dir / "classes_balance.toml"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(toml_content)
        
        print(f"✅ Datos guardados en: {output_file}")
        
        # Estadísticas
        total_entries = sum(len(section) for section in balance_data.values())
        print(f"📊 Estadísticas: {total_entries} entradas de balance procesadas")


def main():
    base_dir = Path(__file__).parent.parent
    balance_file = base_dir / "clientes" / "ArgentumOnline0.13.3-Cliente-Servidor" / "server" / "Dat" / "Balance.dat"
    output_dir = base_dir / "data"
    
    if not balance_file.exists():
        print(f"Error: No existe {balance_file}")
        return
    
    extractor = BalanceDataExtractor(balance_file, output_dir)
    extractor.extract_and_save()
    
    print("\n✅ Extracción de datos de balance completada!")


if __name__ == "__main__":
    main()
