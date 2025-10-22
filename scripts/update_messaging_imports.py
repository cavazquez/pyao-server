"""Script para actualizar imports de messaging."""

from pathlib import Path

# Mapeo de imports antiguos a nuevos
IMPORT_REPLACEMENTS = {
    # MessageSender principal
    "from src.message_sender import": "from src.messaging.message_sender import",
    
    # Senders específicos
    "from src.message_audio_sender import": "from src.messaging.senders.message_audio_sender import",
    "from src.message_character_sender import": "from src.messaging.senders.message_character_sender import",
    "from src.message_console_sender import": "from src.messaging.senders.message_console_sender import",
    "from src.message_inventory_sender import": "from src.messaging.senders.message_inventory_sender import",
    "from src.message_map_sender import": "from src.messaging.senders.message_map_sender import",
    "from src.message_player_stats_sender import": "from src.messaging.senders.message_player_stats_sender import",
    "from src.message_session_sender import": "from src.messaging.senders.message_session_sender import",
    "from src.message_visual_effects_sender import": "from src.messaging.senders.message_visual_effects_sender import",
    "from src.message_work_sender import": "from src.messaging.senders.message_work_sender import",
}


def update_imports_in_file(file_path: Path) -> bool:
    """Actualiza imports en un archivo.
    
    Returns:
        True si se hicieron cambios, False si no.
    """
    content = file_path.read_text()
    original_content = content

    # Aplicar reemplazos
    for old_import, new_import in IMPORT_REPLACEMENTS.items():
        content = content.replace(old_import, new_import)

    # Guardar si hubo cambios
    if content != original_content:
        file_path.write_text(content)
        return True
    return False


def update_all_imports() -> None:
    """Actualiza imports en todos los archivos."""
    updated_count = 0
    
    # Actualizar archivos en src/
    print("📝 Actualizando imports en src/...")
    for py_file in Path("src").rglob("*.py"):
        if update_imports_in_file(py_file):
            updated_count += 1
            print(f"  ✓ {py_file.relative_to('.')}")
    
    # Actualizar archivos en tests/
    print("\n📝 Actualizando imports en tests/...")
    for py_file in Path("tests").glob("*.py"):
        if update_imports_in_file(py_file):
            updated_count += 1
            print(f"  ✓ {py_file.name}")
    
    print(f"\n✅ {updated_count} archivos actualizados")


if __name__ == "__main__":
    update_all_imports()
