"""Script para reorganizar archivos de messaging."""

import subprocess
from pathlib import Path


def reorganize_messaging() -> None:
    """Reorganiza archivos de messaging en subcarpetas."""
    src_dir = Path("src")
    messaging_dir = src_dir / "messaging"
    senders_dir = messaging_dir / "senders"

    # Crear estructura de carpetas
    print("📁 Creando estructura de messaging...")
    messaging_dir.mkdir(exist_ok=True)
    senders_dir.mkdir(exist_ok=True)
    
    (messaging_dir / "__init__.py").write_text('"""Package de messaging del servidor."""\n')
    (senders_dir / "__init__.py").write_text('"""Senders de mensajes específicos."""\n')
    print("  ✓ messaging/")
    print("  ✓ messaging/senders/")

    # Archivos a mover a messaging/senders/
    senders = [
        "message_audio_sender.py",
        "message_character_sender.py",
        "message_console_sender.py",
        "message_inventory_sender.py",
        "message_map_sender.py",
        "message_player_stats_sender.py",
        "message_session_sender.py",
        "message_visual_effects_sender.py",
        "message_work_sender.py",
    ]

    # Archivo principal que va a messaging/ (no a senders/)
    main_sender = "message_sender.py"

    # Mover senders específicos a messaging/senders/
    print("\n📦 Moviendo message senders...")
    moved_count = 0
    for sender in senders:
        src_file = src_dir / sender
        if src_file.exists():
            dest_file = senders_dir / sender
            subprocess.run(["git", "mv", str(src_file), str(dest_file)], check=True)
            print(f"  ✓ {sender} → messaging/senders/")
            moved_count += 1

    # Mover message_sender.py principal a messaging/
    src_file = src_dir / main_sender
    if src_file.exists():
        dest_file = messaging_dir / main_sender
        subprocess.run(["git", "mv", str(src_file), str(dest_file)], check=True)
        print(f"  ✓ {main_sender} → messaging/")
        moved_count += 1

    print(f"\n✅ Reorganización completada: {moved_count} archivos movidos")
    print("\n⚠️  SIGUIENTE PASO: Actualizar imports en:")
    print("  - Todos los archivos que importan MessageSender")
    print("  - Archivos en messaging/senders/ que se importan entre sí")


if __name__ == "__main__":
    reorganize_messaging()
