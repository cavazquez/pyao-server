# Propuesta de Reorganización del Código

**Fecha:** 21 de octubre, 2025  
**Estado actual:** 138 archivos en src/, 118 en tests/  
**Problema:** Difícil navegación y mantenimiento

---

## 📁 Estructura Propuesta

```
src/
├── __init__.py
├── main.py                    # Entry point del servidor
│
├── core/                      # Core del servidor
│   ├── __init__.py
│   ├── server.py
│   ├── client_connection.py
│   ├── session_manager.py
│   ├── dependency_container.py
│   └── service_initializer.py
│
├── network/                   # Capa de red y protocolos
│   ├── __init__.py
│   ├── packet_id.py
│   ├── packet_reader.py
│   ├── packet_validator.py
│   ├── packet_data.py
│   └── packet_handlers.py
│
├── tasks/                     # Handlers de packets (Tasks)
│   ├── __init__.py
│   ├── task.py               # Base class
│   ├── task_factory.py
│   │
│   ├── player/               # Tasks de jugador
│   │   ├── __init__.py
│   │   ├── task_login.py
│   │   ├── task_create_account.py
│   │   ├── task_walk.py
│   │   ├── task_change_heading.py
│   │   ├── task_attack.py
│   │   ├── task_meditate.py
│   │   ├── task_safe_toggle.py
│   │   └── task_request_pos_update.py
│   │
│   ├── inventory/            # Tasks de inventario
│   │   ├── __init__.py
│   │   ├── task_inventory_click.py
│   │   ├── task_equip_item.py
│   │   ├── task_drop.py
│   │   └── task_double_click.py
│   │
│   ├── commerce/             # Tasks de comercio
│   │   ├── __init__.py
│   │   ├── task_commerce_buy.py
│   │   ├── task_commerce_sell.py
│   │   └── task_commerce_end.py
│   │
│   ├── banking/              # Tasks de banco
│   │   ├── __init__.py
│   │   ├── task_bank_deposit.py
│   │   └── task_bank_extract.py
│   │
│   ├── spells/               # Tasks de hechizos
│   │   ├── __init__.py
│   │   ├── task_cast_spell.py
│   │   ├── task_spell_info.py
│   │   └── task_move_spell.py
│   │
│   ├── interaction/          # Tasks de interacción
│   │   ├── __init__.py
│   │   ├── task_left_click.py
│   │   └── task_information.py
│   │
│   ├── work/                 # Tasks de trabajo
│   │   ├── __init__.py
│   │   ├── task_work.py
│   │   └── task_work_left_click.py
│   │
│   └── admin/                # Tasks de GM
│       ├── __init__.py
│       └── task_gm_commands.py
│
├── models/                   # Modelos de datos
│   ├── __init__.py
│   ├── player.py
│   ├── npc.py
│   ├── item.py
│   ├── item_types.py
│   ├── spell.py
│   └── ground_item.py
│
├── repositories/             # Capa de datos (Redis)
│   ├── __init__.py
│   ├── player_repository.py
│   ├── account_repository.py
│   ├── inventory_repository.py
│   ├── equipment_repository.py
│   ├── spellbook_repository.py
│   ├── npc_repository.py
│   ├── merchant_repository.py
│   └── bank_repository.py
│
├── services/                 # Lógica de negocio
│   ├── __init__.py
│   ├── account_service.py
│   ├── combat_service.py
│   ├── spell_service.py
│   ├── commerce_service.py
│   ├── stamina_service.py
│   ├── npc_service.py
│   ├── npc_ai_service.py
│   ├── pathfinding_service.py
│   └── map_resources_service.py
│
├── messaging/                # Envío de mensajes al cliente
│   ├── __init__.py
│   ├── message_sender.py    # Agregador principal
│   │
│   ├── senders/
│   │   ├── __init__.py
│   │   ├── console_sender.py
│   │   ├── player_stats_sender.py
│   │   ├── character_sender.py
│   │   ├── inventory_sender.py
│   │   ├── spell_sender.py
│   │   ├── combat_sender.py
│   │   ├── work_sender.py
│   │   └── multiplayer_broadcast_service.py
│
├── world/                    # Mundo del juego
│   ├── __init__.py
│   ├── map_manager.py
│   ├── npc_factory.py
│   └── spawner_service.py
│
├── data_loaders/             # Cargadores de datos
│   ├── __init__.py
│   ├── items_catalog.py
│   ├── spells_catalog.py
│   ├── npc_data_loader.py
│   └── merchant_data_loader.py
│
└── utils/                    # Utilidades
    ├── __init__.py
    ├── password_utils.py
    ├── position.py
    └── heading.py
```

---

## 🧪 Estructura de Tests

```
tests/
├── __init__.py
├── conftest.py              # Fixtures compartidos
│
├── unit/                    # Tests unitarios
│   ├── __init__.py
│   │
│   ├── network/
│   │   ├── test_packet_reader.py
│   │   ├── test_packet_validator.py
│   │   └── test_packet_id.py
│   │
│   ├── models/
│   │   ├── test_player.py
│   │   ├── test_npc.py
│   │   └── test_item.py
│   │
│   ├── repositories/
│   │   ├── test_player_repository.py
│   │   ├── test_inventory_repository.py
│   │   └── test_npc_repository.py
│   │
│   ├── services/
│   │   ├── test_combat_service.py
│   │   ├── test_spell_service.py
│   │   ├── test_stamina_service.py
│   │   ├── test_npc_ai_service.py
│   │   └── test_pathfinding_service.py
│   │
│   └── utils/
│       ├── test_password_utils.py
│       └── test_position.py
│
├── integration/             # Tests de integración
│   ├── __init__.py
│   ├── test_login_flow.py
│   ├── test_combat_flow.py
│   ├── test_commerce_flow.py
│   ├── test_work_flow.py
│   └── test_npc_spawning.py
│
└── tasks/                   # Tests de tasks (agrupados)
    ├── __init__.py
    │
    ├── player/
    │   ├── test_task_login.py
    │   ├── test_task_walk.py
    │   └── test_task_attack.py
    │
    ├── inventory/
    │   ├── test_task_inventory_click.py
    │   ├── test_task_equip_item.py
    │   └── test_task_drop.py
    │
    ├── commerce/
    │   ├── test_task_commerce_buy.py
    │   └── test_task_commerce_sell.py
    │
    └── work/
        ├── test_task_work.py
        └── test_task_work_left_click.py
```

---

## 🎯 Ventajas de esta Organización

### 1. **Navegación Más Fácil**
- Categorías claras por responsabilidad
- Máximo ~15 archivos por carpeta
- Estructura predecible

### 2. **Mejor Mantenibilidad**
- Cambios relacionados agrupados
- Menos conflictos en git
- Refactoring más simple

### 3. **Imports Más Claros**
```python
# Antes (confuso)
from src.task_login import TaskLogin
from src.task_walk import TaskWalk
from src.task_attack import TaskAttack

# Después (organizado)
from src.tasks.player import TaskLogin, TaskWalk, TaskAttack
```

### 4. **Tests Alineados con Código**
- Estructura de tests espeja la de src/
- Fácil encontrar tests de un módulo específico

### 5. **Escalabilidad**
- Agregar nuevas features es más claro
- Cada carpeta es un "módulo" cohesivo

---

## 📊 Migración Sugerida

### Opción 1: Migración Gradual (Recomendada)

**Fase 1: Tasks** (~50 archivos)
- Crear `src/tasks/` con subcarpetas
- Mover tasks por categoría
- Actualizar imports
- Tests siguen pasando

**Fase 2: Messaging** (~15 archivos)
- Crear `src/messaging/senders/`
- Mover message senders
- Actualizar MessageSender principal

**Fase 3: Repositories** (~10 archivos)
- Crear `src/repositories/`
- Mover todos los repositorios

**Fase 4: Services** (~12 archivos)
- Crear `src/services/`
- Mover servicios

**Fase 5: Models** (~8 archivos)
- Crear `src/models/`
- Mover modelos de datos

**Fase 6: Tests**
- Reorganizar tests siguiendo estructura de src/

### Opción 2: Big Bang (Arriesgada)
- Mover todo de una vez
- Alto riesgo de romper imports
- Requiere testing exhaustivo

---

## 🛠️ Script de Migración (Fase 1: Tasks)

```python
# scripts/reorganize_tasks.py
"""Script para reorganizar archivos de tasks en subcarpetas."""

from pathlib import Path
import shutil

# Mapeo de archivos a carpetas
TASK_MAPPING = {
    # player/
    "task_login.py": "player",
    "task_create_account.py": "player",
    "task_walk.py": "player",
    "task_change_heading.py": "player",
    "task_attack.py": "player",
    "task_meditate.py": "player",
    "task_safe_toggle.py": "player",
    "task_request_pos_update.py": "player",
    
    # inventory/
    "task_inventory_click.py": "inventory",
    "task_equip_item.py": "inventory",
    "task_drop.py": "inventory",
    "task_double_click.py": "inventory",
    
    # commerce/
    "task_commerce_buy.py": "commerce",
    "task_commerce_sell.py": "commerce",
    "task_commerce_end.py": "commerce",
    
    # banking/
    "task_bank_deposit.py": "banking",
    "task_bank_extract.py": "banking",
    
    # spells/
    "task_cast_spell.py": "spells",
    "task_spell_info.py": "spells",
    "task_move_spell.py": "spells",
    
    # interaction/
    "task_left_click.py": "interaction",
    "task_information.py": "interaction",
    
    # work/
    "task_work.py": "work",
    "task_work_left_click.py": "work",
    
    # admin/
    "task_gm_commands.py": "admin",
}

def reorganize_tasks():
    src_dir = Path("src")
    tasks_dir = src_dir / "tasks"
    
    # Crear estructura de carpetas
    for category in set(TASK_MAPPING.values()):
        (tasks_dir / category).mkdir(parents=True, exist_ok=True)
        (tasks_dir / category / "__init__.py").touch()
    
    # Mover archivos
    for file, category in TASK_MAPPING.items():
        src_file = src_dir / file
        if src_file.exists():
            dest_file = tasks_dir / category / file
            shutil.move(str(src_file), str(dest_file))
            print(f"✓ Moved {file} → tasks/{category}/")
    
    # Crear __init__.py principal
    (tasks_dir / "__init__.py").write_text(
        '"""Package de tasks del servidor."""\n'
    )
    
    print(f"\n✅ Reorganización completada")

if __name__ == "__main__":
    reorganize_tasks()
```

---

## ⚠️ Consideraciones

### 1. **Imports a Actualizar**
Todos los imports deberán cambiar:
```python
# Antes
from src.task_login import TaskLogin

# Después
from src.tasks.player.task_login import TaskLogin

# O mejor aún
from src.tasks.player import TaskLogin
```

### 2. **Circular Imports**
Reorganizar puede exponer circular imports. Solución:
- Usar `TYPE_CHECKING` para type hints
- Mover imports dentro de funciones si es necesario

### 3. **Tests**
Cada reorganización debe ir acompañada de:
```bash
./scripts/checks.sh  # Verificar que todo sigue funcionando
```

### 4. **Git History**
Usar `git mv` en lugar de copiar/borrar para preservar historia:
```bash
git mv src/task_login.py src/tasks/player/task_login.py
```

---

## 📝 TODO

- [ ] Crear script de migración para Fase 1
- [ ] Migrar tasks a subcarpetas
- [ ] Actualizar todos los imports
- [ ] Verificar tests (990 deben seguir pasando)
- [ ] Migrar messaging senders
- [ ] Migrar repositories
- [ ] Migrar services
- [ ] Migrar models
- [ ] Reorganizar tests
- [ ] Actualizar documentación

---

## 🚀 Beneficio Esperado

**Antes:**
- 138 archivos en src/
- Difícil encontrar archivos relacionados
- Scroll infinito en IDE

**Después:**
- ~10 carpetas bien organizadas
- Máximo 15 archivos por carpeta
- Navegación intuitiva
- Estructura profesional escalable

---

**Recomendación:** Empezar con Fase 1 (Tasks) que son ~50 archivos. Si funciona bien, continuar con las demás fases.
