#!/usr/bin/env python3
"""Encuentra TODOS los yunques y fraguas en obj.dat"""
import re
from pathlib import Path

obj_dat_path = Path('/home/cristian/repos/propios/pyao-server/clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Dat/obj.dat')

print("\n🔍 Buscando todos los yunques (ObjType=27) y fraguas (ObjType=28) en obj.dat...\n")

anvils = []
forges = []

with open(obj_dat_path, 'r', encoding='latin-1') as f:
    current_obj = {}
    
    for line in f:
        line = line.strip()
        
        if line.startswith('[OBJ'):
            if current_obj:
                obj_type = current_obj.get('ObjType')
                if obj_type == '27':
                    anvils.append(current_obj)
                elif obj_type == '28':
                    forges.append(current_obj)
            current_obj = {}
        
        elif '=' in line:
            key, value = line.split('=', 1)
            current_obj[key] = value
    
    # Último objeto
    if current_obj:
        obj_type = current_obj.get('ObjType')
        if obj_type == '27':
            anvils.append(current_obj)
        elif obj_type == '28':
            forges.append(current_obj)

print("=" * 70)
print("🔨 YUNQUES (ObjType=27)")
print("=" * 70)
if anvils:
    grh_set = set()
    for obj in anvils:
        name = obj.get('Name', 'Sin nombre')
        grh = obj.get('GrhIndex', '?')
        grh_set.add(grh)
        print(f"  {name:30s} GrhIndex={grh}")
    print(f"\n  Total: {len(anvils)} yunques, {len(grh_set)} GrhIndex únicos: {sorted(grh_set)}")
else:
    print("  No se encontraron yunques")

print("\n" + "=" * 70)
print("🔥 FRAGUAS (ObjType=28)")
print("=" * 70)
if forges:
    grh_set = set()
    for obj in forges:
        name = obj.get('Name', 'Sin nombre')
        grh = obj.get('GrhIndex', '?')
        grh_set.add(grh)
        print(f"  {name:30s} GrhIndex={grh}")
    print(f"\n  Total: {len(forges)} fraguas, {len(grh_set)} GrhIndex únicos: {sorted(grh_set)}")
else:
    print("  No se encontraron fraguas")

print("=" * 70)
