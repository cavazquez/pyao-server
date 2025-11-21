# TODO Consolidado - PyAO Server

**Última actualización:** 2025-01-30  
**Versión actual:** 0.6.4-alpha  
**Estado:** Documento maestro de tareas pendientes

> **Nota:** Este documento consolida todos los TODOs activos del proyecto. Para TODOs completados, ver `TODOS_COMPLETADOS.md`. Para roadmap de versiones, ver `ROADMAP_VERSIONES.md`.

---

## 📋 Índice

1. [Features Pendientes](#features-pendientes)
2. [Mejoras Arquitectónicas](#mejoras-arquitectónicas)
3. [Mejoras de Calidad](#mejoras-de-calidad)
4. [Tareas del Cliente](#tareas-del-cliente)
5. [Sistema de Items](#sistema-de-items)

---

## 🎯 Features Pendientes

### Sistema de Clases (v0.7.0-alpha) 🔴 Alta Prioridad
**Estado:** 🚧 Planificado  
**Esfuerzo:** 2-3 semanas  
**Referencia:** `ROADMAP_VERSIONES.md#123-139`

**Features:**
- [ ] Clases: Guerrero, Mago, Arquero, Clérigo
- [ ] Atributos base por clase
- [ ] Restricciones de equipo por clase
- [ ] Skills específicas por clase
- [ ] Balanceo de stats iniciales
- [ ] Selección de clase en creación de personaje

**Archivos a crear:**
- `src/models/character_class.py`
- `src/services/game/class_service.py`
- `data/classes.toml`

---

### Sistema de Partys/Grupos (v0.8.0-alpha) ✅ COMPLETADO
**Estado:** ✅ Sistema completo y funcional  
**Progreso:** 100% (10/10 criterios)  
**Referencia:** `docs/PARTY_SYSTEM_IMPLEMENTATION_STATUS.md`

**Completado:**
- ✅ Modelos de datos (Party, PartyMember, PartyInvitation)
- ✅ Persistencia en Redis (PartyRepository)
- ✅ Lógica de negocio (PartyService)
- ✅ Handlers de packets (7 tasks)
- ✅ Integración con sistema
- ✅ Documentación completa
- ✅ 60 tests creados (todos pasando)
- ✅ Experiencia compartida automática en combate
- ✅ Sistema de loot compartido
- ✅ Notificaciones broadcast a miembros
- ✅ Sincronización de level up en party

**Funcionalidades implementadas:**
- Creación, invitaciones, gestión de miembros
- Chat de party, transferencia de liderazgo
- Distribución automática de experiencia al matar NPCs
- Loot compartido (items y oro públicos)
- Sincronización automática de nivel cuando un miembro sube de nivel
- Notificaciones a todos los miembros de party

**Opcional (futuro):**
- Tests de integración end-to-end (funcionalidad ya implementada)
- Party finder (búsqueda de parties)
- Sistema de roles (tank, healer, dps)

---

### Sistema de Clanes/Guilds (v0.9.0-alpha) 🔴 Alta Prioridad
**Estado:** 📋 Pendiente  
**Esfuerzo:** 2-3 semanas  
**Referencia:** `TODO_CARACTERISTICAS_VB6.md#9-30`

**Features:**
- [ ] Creación de clanes
- [ ] Gestión de miembros (invitar, expulsar, promover)
- [ ] Almacén/depósito del clan
- [ ] Chat interno del clan
- [ ] Alianzas entre clanes
- [ ] Guerras de clanes
- [ ] Edificio del clan con NPCs
- [ ] Sistema de rangos jerárquicos

**Archivos a crear:**
- `src/models/clan.py`
- `src/services/clan_service.py`
- `src/repositories/clan_repository.py`
- `src/tasks/clan/`
- `data/clans.toml`

**Dependencias:** Requiere sistema de Partys funcionando (v0.8.0)

---

### Targeting por Click para Hechizos (v0.10.0-alpha) 🟡 Media Prioridad
**Estado:** 📋 Pendiente  
**Esfuerzo:** 1 semana  
**Referencia:** `TODO_SPELL_CLICK_TARGETING.md`

**Features:**
- [ ] Sistema de "click para seleccionar target" en hechizos
- [ ] Cursor cambia visualmente al modo targeting
- [ ] Cliente envía CAST_SPELL con coordenadas (x, y)
- [ ] Servidor valida rango antes de lanzar
- [ ] Se puede cancelar el targeting (ESC o click derecho)
- [ ] Formato antiguo (heading) sigue funcionando como fallback

**Nota:** Servidor **ya está preparado** para recibir coordenadas en CAST_SPELL (formato de 6 bytes). Solo falta modificar el cliente.

**Archivos a modificar:**
- Cliente Godot: `ui/hub/spell_list_panel.gd`
- Cliente Godot: `screens/game_screen.gd`
- Cliente Godot: `engine/autoload/game_protocol.gd`
- Servidor: `src/tasks/spells/task_cast_spell.py` (opcional, ya soporta)

---

### Hechizos Avanzados (v0.11.0-alpha) 🔴 Alta Prioridad
**Estado:** 📋 Pendiente  
**Esfuerzo:** 3-4 semanas  
**Referencia:** `TODO_CARACTERISTICAS_VB6.md#76-94`

**Features:**
- [ ] Sistema de escuelas de magia (Fuego, Agua, Tierra, Aire, Luz, Oscuridad)
- [ ] Hechizos de área (AOE)
- [ ] Hechizos con duración y efectos over time (DoT)
- [ ] Sistema de runas y componentes
- [ ] Hechizos de invocación
- [ ] Protecciones y barreras mágicas
- [ ] Libros de hechizos equipables

**Dependencias:** Conviene tener targeting por click listo (v0.10.0)

---

### Sistema de Facciones (v0.12.0-alpha) 🟡 Media Prioridad
**Estado:** 📋 Pendiente  
**Esfuerzo:** 2-3 semanas  
**Referencia:** `TODO_CARACTERISTICAS_VB6.md#55-73`

**Features:**
- [ ] Sistema de facciones (Legión, Caos, Real, Neutral)
- [ ] Guerras automáticas entre facciones
- [ ] Zonas controladas por facciones
- [ ] Beneficios por pertenecer a facción
- [ ] Sistema de prestigio de facción
- [ ] NPCs de facciones con comportamiento diferenciado

**Dependencias:** Requiere clanes/partys para interacción social (v0.8.0, v0.9.0)

---

### Sistema de Quests (v0.13.0-alpha) 🟡 Media Prioridad
**Estado:** 📋 Pendiente  
**Esfuerzo:** 2-3 semanas

**Features:**
- [ ] Sistema de misiones/quests
- [ ] Objetivos (matar NPCs, recolectar items, hablar con NPCs)
- [ ] Recompensas (exp, oro, items)
- [ ] Cadenas de quests
- [ ] Quest log para jugadores
- [ ] NPCs que dan quests
- [ ] Validación de requisitos (nivel, clase, facción)

---

## 🏗️ Mejoras Arquitectónicas

### Service Container / Dependency Injection 🟢 Baja Prioridad
**Estado:** 📝 Propuesta  
**Esfuerzo:** 4-6 horas  
**Referencia:** `TODO_ARQUITECTURA.md#15-130`

**Problema:** Código repetitivo en creación de tasks con dependencias.

**Solución:** Contenedor de servicios con inyección automática de dependencias.

**Beneficios:**
- Código más limpio
- Fácil agregar nuevas dependencias
- Mejor testabilidad

**Cuándo:** Antes de v0.9.0 (clanes)

---

### Event Bus / Message Bus 🟢 Baja Prioridad
**Estado:** 📝 Propuesta  
**Esfuerzo:** 6-8 horas  
**Referencia:** `TODO_ARQUITECTURA.md#133-237`

**Beneficios:**
- Desacoplamiento de componentes
- Fácil agregar listeners para eventos
- Útil para logros, quests, notificaciones

**Cuándo:** Antes de v0.13.0 (quests) o v0.17.0 (logros)

---

### Command Pattern para Tasks 🟡 Media Prioridad
**Estado:** 📝 Propuesta  
**Esfuerzo:** 8-10 horas  
**Referencia:** `TODO_ARQUITECTURA.md#240-304`

**Beneficios:**
- Undo/Redo de acciones
- Cola de comandos
- Mejor logging de acciones

**Cuándo:** Antes de v0.11.0 (hechizos avanzados)

---

### Repository Pattern Mejorado 🟢 Baja Prioridad
**Estado:** 📝 Propuesta  
**Esfuerzo:** 10-12 horas  
**Referencia:** `TODO_ARQUITECTURA.md#307-382`

**Beneficios:**
- Abstracción de persistencia
- Fácil cambiar de Redis a PostgreSQL
- Mejor separación de responsabilidades

**Cuándo:** Cuando tengas tiempo

---

### Logging Estructurado (JSON) 🟢 Baja Prioridad
**Estado:** 📝 Propuesta  
**Esfuerzo:** 2-3 horas  
**Referencia:** `TODO_REFACTORING.md#191-203`

**Beneficios:**
- Logs parseables automáticamente
- Mejor análisis en producción
- Integración con herramientas de monitoring

**Opciones:**
- `structlog` - Logging estructurado para Python
- `python-json-logger` - JSON formatter para logging estándar

**Cuándo:** Antes de producción

---

## 📈 Mejoras de Calidad

### Ampliar Cobertura de Tests 🔴 Alta Prioridad
**Estado:** 🚧 En progreso  
**Cobertura actual:** 72%  
**Objetivo:** 80%+

**Áreas prioritarias:**
- [ ] `services/commerce_service.py` - 13% (sistema crítico)
- [ ] `tasks/inventory/task_use_item.py` - 13% (funcionalidad importante)
- [ ] `tasks/player/task_attack.py` - 25% (sistema de combate)
- [ ] `game/map_manager.py` - 48% (módulo grande)
- [ ] `services/map/map_resources_service.py` - 28% (módulo grande)

**Referencia:** `TODO_POST_REORGANIZACION.md#23-44`

---

### Documentar APIs por Módulo 🟡 Media Prioridad
**Estado:** 📋 Pendiente  
**Esfuerzo:** Medio  
**Referencia:** `TODO_POST_REORGANIZACION.md#48-70`

**Tareas:**
- [ ] Generar docs automáticos con Sphinx o MkDocs
- [ ] Documentar API de cada módulo principal
- [ ] Crear diagramas de arquitectura (Mermaid)
- [ ] Documentar flujos de datos principales

**Herramientas sugeridas:**
- Sphinx con autodoc
- MkDocs con mkdocstrings
- Mermaid para diagramas

---

### Mejorar CI/CD con Tests por Categoría 🟡 Media Prioridad
**Estado:** 📋 Pendiente  
**Esfuerzo:** Bajo  
**Referencia:** `TODO_POST_REORGANIZACION.md#73-92`

**Tareas:**
- [ ] Configurar pytest para ejecutar tests por categoría
- [ ] Crear jobs de CI separados (quick checks vs full tests)
- [ ] Implementar test paralelo por categoría
- [ ] Agregar badges de cobertura por módulo

---

### Crear Plantillas para Nuevos Componentes 🟡 Media Prioridad
**Estado:** 📋 Pendiente  
**Esfuerzo:** Bajo  
**Referencia:** `TODO_POST_REORGANIZACION.md#118-138`

**Tareas:**
- [ ] Crear template de Task con su test
- [ ] Crear template de Service con su test
- [ ] Crear template de Repository con su test
- [ ] Documentar convenciones de naming
- [ ] Crear script `new_component.py` para generar boilerplate

---

## 💻 Tareas del Cliente

### Mostrar Posición del Jugador en GUI 🔴 Alta Prioridad
**Estado:** 📋 Pendiente  
**Esfuerzo:** 1 hora  
**Referencia:** `TODO_CLIENTE.md#7-28`

**Descripción:** La GUI debería mostrar la posición actual del jugador (X, Y, Mapa) en tiempo real.

**Beneficios:**
- Facilita debugging
- Ayuda en testing
- Útil para reportar bugs

**Ubicación en Cliente:**
- `ui/hub/hub_controller.gd` - Actualizar en cada movimiento
- Packet `POS_UPDATE` ya envía la posición

---

### Feedback Visual de Acciones 🟡 Media Prioridad
**Estado:** 📋 Pendiente  
**Esfuerzo:** 2-3 horas  
**Referencia:** `TODO_CLIENTE.md#41-49`

**Acciones que necesitan feedback:**
- Recoger item (sonido + animación)
- Tirar item (sonido + animación)
- Atacar (efecto visual mejorado)
- Recibir daño (screen shake, efecto rojo)

---

### Panel de Inventario Completo 🟡 Media Prioridad
**Estado:** 📋 Pendiente  
**Esfuerzo:** 1 semana  
**Referencia:** `TODO_CLIENTE.md#50-58`

**Funcionalidades:**
- Mostrar items con iconos
- Drag & drop para reorganizar
- Click derecho para usar/equipar
- Tooltip con stats del item

---

## 🎒 Sistema de Items

### ItemFactory 🟡 Media Prioridad
**Estado:** 📋 Pendiente  
**Referencia:** `ITEMS_SYSTEM_TODO.md`

**Tareas:**
- [ ] Implementar `ItemFactory` para la creación de ítems
- [ ] Mover la lógica de manzanas a un sistema de comportamientos
- [ ] Añadir soporte para más tipos de ítems

---

### Documentación y Tests 🟡 Media Prioridad
**Estado:** 📋 Pendiente

**Tareas:**
- [ ] Documentar la API de ítems
- [ ] Añadir tests unitarios para `TaskUseItem`
- [ ] Implementar sistema de efectos temporales

---

### Features Avanzadas 🟢 Baja Prioridad
**Estado:** 📋 Pendiente

**Tareas:**
- [ ] Añadir sistema de durabilidad para ítems
- [ ] Implementar sistema de encantamientos
- [ ] Documentar el flujo completo de uso de ítems

---

## 📊 Priorización

### 🔴 Alta Prioridad (Implementar primero)
1. Completar sistema de Parties (corregir tests, funcionalidades faltantes)
2. Sistema de Clases (v0.7.0)
3. Ampliar cobertura de tests (áreas críticas)
4. Mostrar posición en GUI del cliente

### 🟡 Media Prioridad (Implementar después)
1. Sistema de Clanes (v0.9.0)
2. Targeting por click para hechizos (v0.10.0)
3. Hechizos Avanzados (v0.11.0)
4. Documentar APIs por módulo
5. Mejorar CI/CD con tests por categoría

### 🟢 Baja Prioridad (Implementar al final)
1. Mejoras arquitectónicas opcionales
2. Logging estructurado
3. Features avanzadas de items
4. Panel de inventario completo del cliente

---

## 🔗 Referencias

- **Roadmap completo:** `ROADMAP_VERSIONES.md` ⭐
- **TODOs completados:** `TODOS_COMPLETADOS.md`
- **Características VB6:** `TODO_CARACTERISTICAS_VB6.md`
- **Arquitectura:** `TODO_ARQUITECTURA.md`
- **Cliente:** `TODO_CLIENTE.md`
- **Items:** `ITEMS_SYSTEM_TODO.md`

---

**Última actualización:** 2025-01-30  
**Mantenido por:** Consolidación automática de TODOs

