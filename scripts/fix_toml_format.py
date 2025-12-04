#!/usr/bin/env python3
"""Corrige errores de formato en archivos TOML de NPCs.

Convierte sub-tablas inválidas a inline tables válidas.
"""

import re
import sys
from pathlib import Path


def convert_section_to_inline(section_match: re.Match) -> str:
    """Convierte una sección [name] a inline table."""
    section_name = section_match.group(1)
    content = section_match.group(2)
    
    # Parsear key=value del contenido
    pairs = []
    for line in content.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, value = line.split('=', 1)
            pairs.append(f'{key.strip()} = {value.strip()}')
    
    if pairs:
        return f'{section_name} = {{ {", ".join(pairs)} }}'
    return ''


def fix_npcs_toml(content: str) -> str:
    """Corrige el formato del archivo de NPCs."""
    
    # Patrón para encontrar secciones simples seguidas de key=value
    # Coincide con [nombre] seguido de líneas key=value hasta la siguiente sección
    pattern = r'\[(\w+)\]\n((?:(?!\[).*\n)*)'
    
    def replacer(match: re.Match) -> str:
        section_name = match.group(1)
        content = match.group(2)
        
        # No convertir secciones de primer nivel
        if section_name in ['npcs_complete', 'npcs_traders', 'npcs_hostiles']:
            return match.group(0)
        
        # Manejar inventory especialmente (tiene arrays)
        if section_name == 'inventory':
            items_match = re.search(r'items\s*=\s*\[(.*?)\]', content, re.DOTALL)
            if items_match:
                items_content = items_match.group(1).strip()
                # Limpiar y compactar
                items_cleaned = re.sub(r'\s+', ' ', items_content)
                return f'inventory.items = [{items_cleaned}]\n'
            return ''
        
        # Para otras secciones, convertir a inline table
        pairs = []
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line and not line.startswith('['):
                key, value = line.split('=', 1)
                pairs.append(f'{key.strip()} = {value.strip()}')
        
        if pairs:
            return f'{section_name} = {{ {", ".join(pairs)} }}\n'
        return ''
    
    result = re.sub(pattern, replacer, content)
    return result


def process_file(filepath: Path) -> bool:
    """Procesa un archivo y corrige errores."""
    print(f"Procesando: {filepath}")
    
    content = filepath.read_text(encoding='utf-8')
    fixed_content = fix_npcs_toml(content)
    
    # Crear backup
    backup_path = filepath.parent / (filepath.stem + '_backup_format.toml')
    backup_path.write_text(content, encoding='utf-8')
    print(f"  Backup: {backup_path}")
    
    # Escribir archivo corregido
    filepath.write_text(fixed_content, encoding='utf-8')
    
    # Verificar que es válido
    import tomllib
    try:
        with filepath.open('rb') as f:
            data = tomllib.load(f)
        
        # Contar NPCs cargados
        npcs_key = [k for k in data.keys() if 'npcs' in k.lower()]
        if npcs_key:
            npcs = data[npcs_key[0]].get('npcs', [])
            print(f"  ✅ Válido - {len(npcs)} NPCs cargados")
        else:
            print(f"  ✅ Válido")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        # Restaurar backup
        filepath.write_text(content, encoding='utf-8')
        print(f"  Restaurado desde backup")
        return False


def main() -> int:
    """Ejecuta la corrección."""
    data_dir = Path('data')
    
    files_to_fix = [
        data_dir / 'npcs_complete.toml',
        data_dir / 'npcs_traders_extended.toml',
    ]
    
    for filepath in files_to_fix:
        if filepath.exists():
            process_file(filepath)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
