# 📋 Índice de Documentación TODO

Este directorio contiene toda la documentación de tareas pendientes, mejoras y refactorings del proyecto PyAO Server.

---

## 📚 Documentos TODO

### 🎯 [TODO_GENERAL.md](TODO_GENERAL.md)
**Lista maestra de features y mejoras del proyecto**

Contenido principal:
- 🗺️ Roadmap de versiones (0.2.0 → 1.0.0)
- 🔥 Tareas de alta prioridad (Combate, Loot, IA de NPCs)
- 🎯 Tareas de media prioridad (Skills, Clases, Hechizos)
- 🔧 Refactoring y limpieza de código
- 📊 Optimizaciones y performance
- 🧪 Testing y calidad
- 🔒 Seguridad
- 🎮 Gameplay (Quests, Party, Guild, PvP)
- 🛠️ Herramientas y utilidades
- 📡 Protocolo
- 📈 Monitoreo y observabilidad
- 🌐 Infraestructura
- 🎨 Contenido (NPCs, Items, Mapas)
- 💡 Ideas innovadoras

**Estado:** 📋 Lista activa - Se actualiza regularmente  
**Audiencia:** Todo el equipo

---

### 🏗️ [TODO_ARQUITECTURA.md](TODO_ARQUITECTURA.md)
**Propuestas de mejoras arquitecturales**

Contenido principal:
1. **Service Container / Dependency Injection** (Baja, 4-6h)
2. **Event System / Message Bus** (Baja, 6-8h)
3. **Command Pattern para Tasks** (Media, 8-10h)
4. **Repository Pattern Mejorado** (Baja, 10-12h)
5. **Configuration Management** (Media, 2-3h)
6. **Sistema de Carga de Recursos** (Alta, 4-6h)
7. **Inicialización de Objetos con Valores None** (Alta, 6-8h)

**Estado:** 📝 Propuestas de diseño - Pendiente implementación  
**Audiencia:** Arquitectos, desarrolladores senior  
**Versión objetivo:** 0.6.0+

---

### 🔄 [TODO_REFACTORING.md](TODO_REFACTORING.md)
**Refactorings técnicos completados y pendientes**

Contenido principal:
- ✅ **PacketReader** - Implementado (3/9 tasks migradas, 33%)
- ✅ **MessageSender Refactoring** - Completado (8 componentes, 100%)
- 📝 **NPC Factory Pattern** - Diseño completo, pendiente
- 📝 **Service Container** - Propuesta pendiente
- 📝 **Validación de Packets** - Mejora de robustez
- 📝 **Logging Estructurado** - Mejora de observabilidad

**Estado:** 🔄 En progreso - 2/6 mejoras completadas  
**Audiencia:** Desarrolladores  
**Versión objetivo:** 0.5.0+

---

### 📦 [TODO_PACKET_READER_REFACTORING.md](TODO_PACKET_READER_REFACTORING.md)
**Migración detallada de tasks a PacketReader**

Contenido principal:
- ✅ Tasks completadas (3/9): bank_deposit, bank_extract, commerce_buy
- 📝 Tasks pendientes (6/9):
  - 🔴 Alta prioridad (4): commerce_sell, inventory_click, equip_item, double_click
  - 🟡 Media prioridad (2): left_click, cast_spell
- 📊 Progreso: 33% completado
- ⏱️ Tiempo restante estimado: ~1 hora

**Estado:** 🔄 En progreso - 3/9 tasks completadas  
**Audiencia:** Desarrolladores trabajando en refactoring  
**Versión objetivo:** 0.5.0

---

### 🎭 [TODO_NPC_FACTORY.md](TODO_NPC_FACTORY.md)
**Sistema de factory methods para NPCs**

Contenido principal:
- 🏗️ Diseño completo del patrón Factory
- 🎨 Efectos visuales (FX) integrados
- 📝 Factory methods para cada tipo de NPC:
  - Hostiles: Goblin, Lobo, Araña, Orco, Dragón
  - Amigables: Comerciante, Banquero, Guardia
- 🔧 Integración con NPCService
- ✅ Checklist de implementación

**Estado:** 📝 Diseño completo - Pendiente implementación  
**Audiencia:** Desarrolladores de gameplay  
**Versión objetivo:** 0.5.0

---

### 🖥️ [TODO_CLIENTE.md](TODO_CLIENTE.md)
**Mejoras del cliente Godot**

Contenido principal:
- 🔴 Alta prioridad:
  - Mostrar posición del jugador en GUI
- 🟡 Media prioridad:
  - Indicador visual de ground items
  - Feedback de acciones
  - Panel de inventario completo
- 🟢 Baja prioridad:
  - Minimapa
  - Panel de stats detallado
  - Chat mejorado

**Estado:** 📋 Lista de mejoras del cliente  
**Audiencia:** Desarrolladores del cliente Godot  
**Coordinación:** Requiere sincronización con servidor

---

## 🗂️ Organización por Categoría

### Por Prioridad

**🔴 Alta Prioridad:**
- Sistema de Carga de Recursos (TODO_ARQUITECTURA.md #6)
- Inicialización de Objetos (TODO_ARQUITECTURA.md #7)
- Completar PacketReader (TODO_PACKET_READER_REFACTORING.md)
- Sistema de Combate (TODO_GENERAL.md)
- Sistema de Loot (TODO_GENERAL.md)

**🟡 Media Prioridad:**
- Configuration Management (TODO_ARQUITECTURA.md #5)
- Command Pattern (TODO_ARQUITECTURA.md #3)
- NPC Factory (TODO_NPC_FACTORY.md)
- Sistema de Skills (TODO_GENERAL.md)
- Hechizos Avanzados (TODO_GENERAL.md)

**🟢 Baja Prioridad:**
- Service Container (TODO_ARQUITECTURA.md #1)
- Event System (TODO_ARQUITECTURA.md #2)
- Repository Pattern Mejorado (TODO_ARQUITECTURA.md #4)
- Features de gameplay avanzadas (TODO_GENERAL.md)

---

### Por Tipo de Trabajo

**🔧 Refactoring Técnico:**
- TODO_REFACTORING.md
- TODO_PACKET_READER_REFACTORING.md

**🏗️ Arquitectura:**
- TODO_ARQUITECTURA.md

**🎮 Features de Gameplay:**
- TODO_GENERAL.md
- TODO_NPC_FACTORY.md

**🖥️ Cliente:**
- TODO_CLIENTE.md

---

### Por Estado

**✅ Completado:**
- MessageSender Refactoring (8 componentes)
- PacketReader implementado (parcial)
- Sistema de Banco
- Sistema de Comercio
- Sistema de Respawn de NPCs

**🔄 En Progreso:**
- PacketReader migration (3/9 tasks)

**📝 Pendiente:**
- NPC Factory
- Configuration Management
- Service Container
- Event System
- Command Pattern
- Repository Pattern Mejorado
- Sistema de Carga de Recursos
- Inicialización de Objetos

---

## 📊 Métricas del Proyecto

**Versión actual:** 0.4.0-alpha  
**Tests:** 716 (100% pasando)  
**Cobertura:** ~80%  
**Servicios:** 10+  
**Sistemas completados:** Login, Movimiento, Combate, Loot, Banco, Comercio, Magia

---

## 🚀 Próximos Pasos Recomendados

### Corto Plazo (1-2 semanas)
1. ✅ Completar migración de PacketReader (6 tasks, ~1 hora)
2. 📝 Implementar NPC Factory (~3-4 horas)
3. 📝 Configuration Management (~2-3 horas)

### Medio Plazo (1 mes)
1. 📝 Sistema de Carga de Recursos (~4-6 horas)
2. 📝 Inicialización de Objetos con Builder Pattern (~6-8 horas)
3. 📝 Loot tables configurables (~4-6 horas)

### Largo Plazo (2-3 meses)
1. 📝 Service Container (~4-6 horas)
2. 📝 Event System (~6-8 horas)
3. 📝 Command Pattern (~8-10 horas)
4. 📝 Sistema de Quests
5. 📝 Sistema de Party

---

## 📝 Cómo Usar Esta Documentación

### Para Desarrolladores
1. Revisa **TODO_GENERAL.md** para ver el panorama completo
2. Consulta **TODO_REFACTORING.md** para tareas técnicas
3. Lee **TODO_PACKET_READER_REFACTORING.md** si trabajas en refactoring de tasks
4. Revisa **TODO_ARQUITECTURA.md** antes de cambios arquitecturales grandes

### Para Arquitectos
1. Empieza con **TODO_ARQUITECTURA.md**
2. Revisa **TODO_REFACTORING.md** para contexto técnico
3. Consulta **TODO_GENERAL.md** para entender roadmap

### Para Product Owners
1. Consulta **TODO_GENERAL.md** para features y roadmap
2. Revisa secciones de gameplay, contenido e ideas innovadoras
3. Prioriza basándote en versiones objetivo

---

## 🔄 Mantenimiento

**Actualización:** Estos documentos deben actualizarse cuando:
- Se completa una tarea importante
- Se agrega una nueva feature al roadmap
- Se cambia la prioridad de una tarea
- Se descubre un nuevo refactoring necesario

**Responsable:** Todo el equipo de desarrollo

**Última revisión general:** 2025-01-19

---

## 📚 Otros Documentos Relevantes

- **ARCHITECTURE.md** - Arquitectura actual del sistema
- **SERVICES_ARCHITECTURE.md** - Diseño de servicios
- **REDIS_ARCHITECTURE.md** - Estructura de datos en Redis
- **BANK_SYSTEM.md** - Sistema de banco (implementado)
- **COMMERCE_SYSTEM.md** - Sistema de comercio (implementado)
- **COMBAT_SYSTEM.md** - Sistema de combate
- **MAGIC_SYSTEM.md** - Sistema de magia
- **NPC_SYSTEM.md** - Sistema de NPCs
- **LOOT_SYSTEM.md** - Sistema de loot

---

**Última actualización:** 2025-01-19  
**Mantenido por:** Equipo PyAO  
**Estado:** 📋 Documentación activa
