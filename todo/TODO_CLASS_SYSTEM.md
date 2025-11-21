# Sistema de Clases - Implementación

**Versión objetivo:** v0.7.0-alpha  
**Prioridad:** 🔴 Alta  
**Esfuerzo estimado:** 2-3 semanas  
**Estado:** ✅ Completado (2025-01-30)  
**Dependencias:** Ninguna (puede empezar tras completar 0.6.0) ✅

---

## 📋 Descripción

Sistema completo de clases de personaje que define atributos base, restricciones de equipo, skills específicas y balanceo de stats iniciales para cada clase.

## 🎯 Objetivo

Implementar un sistema robusto de clases que:
- Defina atributos base por clase
- Restrinja equipamiento según clase
- Asigne skills específicas por clase
- Balancee stats iniciales
- Permita selección de clase en creación de personaje

## ✨ Funcionalidades

### 1. Clases Básicas (v0.7.0)
- **Guerrero**: Combate cuerpo a cuerpo, alta resistencia
- **Mago**: Magia ofensiva, baja resistencia
- **Arquero**: Combate a distancia, agilidad
- **Clérigo**: Magia curativa, balanceado

### 2. Atributos Base por Clase
- Cada clase tiene atributos base diferentes
- Se suman a los atributos de dados del jugador
- Se aplican modificadores raciales después

### 3. Restricciones de Equipo
- ❌ **NO implementado** - Siguiendo comportamiento VB6 original
- En el VB6 original, cualquier clase puede equipar cualquier item
- Los modificadores de clase (`ataquearmas`, `danoarmas`, etc.) ya penalizan el uso inadecuado
- Ejemplo: Un Mago puede equipar espada, pero hace 50% menos daño por los modificadores

### 4. Skills Específicas por Clase
- Cada clase tiene skills iniciales diferentes
- Skills se asignan automáticamente al crear personaje

### 5. Balanceo de Stats Iniciales
- HP, Mana, Stamina iniciales según clase
- Modificadores de clase ya implementados en `BalanceService`

## 📦 Estructura de Datos

### Modelo CharacterClass

```python
@dataclass
class CharacterClass:
    """Representa una clase de personaje."""
    class_id: int  # ID del protocolo (1-12)
    name: str  # Nombre de la clase
    base_attributes: dict[str, int]  # Atributos base
    allowed_weapon_types: list[str]  # Tipos de armas permitidas
    allowed_armor_types: list[str]  # Tipos de armaduras permitidas
    initial_skills: dict[str, int]  # Skills iniciales
    description: str  # Descripción de la clase
```

### Archivo de Configuración

**Archivo:** `data/classes.toml`

```toml
[classes]
[[classes.character_class]]
id = 1
name = "Mago"
base_strength = 8
base_agility = 8
base_intelligence = 15
base_charisma = 10
base_constitution = 9
allowed_weapon_types = ["varita", "baston"]
allowed_armor_types = ["tunica", "capucha"]
initial_skills = { "magia" = 10 }
description = "Maestro de las artes arcanas"
```

## 🏗️ Arquitectura

### Modelos

**Archivo:** `src/models/character_class.py`

**Clases:**
- `CharacterClass` - Modelo de datos de clase
- `ClassCatalog` - Catálogo de todas las clases disponibles

### Servicio

**Archivo:** `src/services/game/class_service.py`

**Métodos:**
- `get_class(class_id: int) -> CharacterClass | None`
- `get_class_by_name(name: str) -> CharacterClass | None`
- `get_all_classes() -> list[CharacterClass]`
- `get_base_attributes(class_id: int) -> dict[str, int]`
- `can_equip_weapon(class_id: int, weapon_type: str) -> bool` (método existe pero no se usa - siguiendo VB6)
- `can_equip_armor(class_id: int, armor_type: str) -> bool` (método existe pero no se usa - siguiendo VB6)
- `get_initial_skills(class_id: int) -> dict[str, int]`
- `apply_class_base_attributes(base_attrs: dict, class_id: int) -> dict[str, int]`

### Integración

**Archivos a modificar:**
- `src/tasks/player/task_account.py` - Integrar selección de clase ✅
- ~~`src/services/player/equipment_service.py` - Validar restricciones~~ (NO necesario, siguiendo VB6)
- `src/repositories/player_repository.py` - Guardar clase del personaje (ya se guarda en account_repo)

## 🔄 Flujo de Implementación

### Fase 1: Modelos y Datos (Día 1-2) ✅
1. ✅ Crear modelo `CharacterClass`
2. ✅ Crear `ClassCatalog` para cargar clases
3. ✅ Crear archivo `data/classes.toml` con 4 clases básicas
4. ✅ Tests para modelos (11 tests)

### Fase 2: Servicio (Día 3-4) ✅
1. ✅ Crear `ClassService`
2. ✅ Implementar métodos de consulta
3. ✅ Integrar con `BalanceService` existente
4. ✅ Tests para servicio (11 tests)

### Fase 3: Integración en Creación (Día 5-6) ✅
1. ✅ Modificar `TaskCreateAccount` para aplicar atributos base
2. ✅ Asignar skills iniciales por clase
3. ✅ Guardar clase en Redis (ya se guarda en account_repo)
4. ✅ Tests de integración (4 tests)

### Fase 4: Restricciones de Equipo (Día 7-10) ❌
- ❌ **CANCELADO** - Siguiendo comportamiento VB6 original
- No se implementan restricciones estrictas
- Los modificadores de clase en `classes_balance.toml` ya balancean el uso de items

### Fase 5: Testing y Documentación (Día 11-14) ✅
1. ✅ Tests end-to-end (26 tests totales, todos pasando)
2. ✅ Documentar sistema completo
3. ✅ Actualizar roadmap
4. ✅ Revisión final

## 📊 Datos de Clases

### Guerrero (ID: 3)
- **Atributos base**: STR: 15, AGI: 10, INT: 8, CHA: 10, CON: 12
- **Armas**: Espadas, Hachas, Mazas
- **Armaduras**: Pesadas, Medias
- **Skills**: Combate cuerpo a cuerpo

### Mago (ID: 1)
- **Atributos base**: STR: 8, AGI: 8, INT: 15, CHA: 10, CON: 9
- **Armas**: Varitas, Bastones
- **Armaduras**: Túnicas, Capuchas
- **Skills**: Magia ofensiva

### Arquero (ID: 10 - Cazador)
- **Atributos base**: STR: 10, AGI: 15, INT: 10, CHA: 10, CON: 10
- **Armas**: Arcos, Ballestas
- **Armaduras**: Ligeras, Cuero
- **Skills**: Combate a distancia

### Clérigo (ID: 2)
- **Atributos base**: STR: 10, AGI: 9, INT: 12, CHA: 12, CON: 12
- **Armas**: Mazas, Bastones
- **Armaduras**: Medias, Túnicas
- **Skills**: Magia curativa

## 🧪 Tests

**Archivos de tests:**
- `tests/models/test_character_class.py` - 11 tests para modelos
- `tests/services/game/test_class_service.py` - 11 tests para servicio
- `tests/integration/test_class_system_integration.py` - 4 tests de integración

**Total:** 26 tests, todos pasando ✅

**Tests implementados:**
- ✅ Test cargar clases desde TOML
- ✅ Test obtener clase por ID
- ✅ Test obtener clase por nombre
- ✅ Test atributos base por clase
- ✅ Test skills iniciales
- ✅ Test integración con BalanceService
- ✅ Test aplicación de atributos base en creación de personaje

## 📝 Notas

- **Compatibilidad**: Usar IDs de `JOB_ID_TO_CLASS_NAME` existente
- **Balance**: Ya existe en `classes_balance.toml`, solo integrar
- **Extensibilidad**: Fácil agregar más clases en el futuro
- **Restricciones de Equipo**: NO implementadas - siguiendo comportamiento VB6 original donde cualquier clase puede equipar cualquier item, pero los modificadores de clase penalizan el uso inadecuado

---

## ✅ Estado Final

**Completado:** 2025-01-30  
**Tests:** 26 tests, todos pasando  
**Cobertura:** Modelos, Servicio, Integración

### Funcionalidades Implementadas
- ✅ Modelo CharacterClass con atributos base y skills
- ✅ ClassCatalog para cargar clases desde TOML
- ✅ ClassService con métodos de consulta
- ✅ Integración en creación de personaje (atributos base + skills)
- ✅ Tests completos (26 tests)
- ✅ Documentación actualizada

### Decisiones de Diseño
- **Restricciones de equipo:** NO implementadas (siguiendo VB6 original)
- **Balance:** Modificadores de clase en `classes_balance.toml` ya balancean
- **Compatibilidad:** Usa IDs de `JOB_ID_TO_CLASS_NAME` existente

---

**Última actualización:** 2025-01-30  
**Autor:** Sistema de IA  
**Versión del documento:** 1.0 (Completado)

