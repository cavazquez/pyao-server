# Roadmap de Versiones - PyAO Server

**Última actualización:** 2025-11-15  
**Versión actual:** 0.7.0-alpha (EN PROGRESO)  
**Estrategia:** Una feature principal por versión

---

## 📊 Estado Actual

**Versión estable:** 0.6.0-alpha (COMPLETADA)  
**Tests:** 1123 pasando (100%)  
**Cobertura:** 78%  
**Calidad:** Excelente (0 errores linting/mypy)

**Sistemas Completados en 0.6.0:**
- ✅ IA de NPCs configurable (daño, cooldown, aggro_range)
- ✅ Pathfinding A* para NPCs (4 direcciones)
- ✅ Sistema de trabajo completo (Tala, Pesca, Minería)
- ✅ Herramientas equipables y recursos
- ✅ Transiciones de mapa por rangos (120+ transiciones)

**Subversiones 0.6.x:**
- ✅ 0.6.1 - Tests faltantes (work/, admin/, map services)
- ✅ 0.6.2 - Refactorizar secuencia de cambio de mapa
- ✅ 0.6.3 - Validación de longitud de packets
- ✅ 0.6.4 - Configuration Management

---

## 🎯 Línea 0.6.x-alpha (COMPLETADA)

### 0.6.1-alpha - Tests Faltantes ✅ COMPLETADO
**Prioridad:** 🔴 Alta  
**Esfuerzo:** 1-2 días  
**Estado:** ✅ Completado (2025-01-29)

**Tareas:**
- ✅ Tests para `tasks/work/`
  - test_task_work.py (13 tests)
- ✅ Tests para `services/map/`
  - test_map_resources_service.py (14 tests)
  - test_map_transition_service.py (19 tests)
  - test_player_map_service.py (18 tests)
  - test_pathfinding_service.py (18 tests)

**Resultado:** 82 tests nuevos, todos pasando (100%)

**Archivos creados:**
- `tests/tasks/work/test_task_work.py`
- `tests/services/map/test_map_resources_service.py`
- `tests/services/map/test_map_transition_service.py`
- `tests/services/map/test_pathfinding_service.py`
- `tests/services/map/test_player_map_service.py`

**Beneficio:** Alta confianza en refactorings futuros, cobertura mejorada

---

### 0.6.2-alpha - Refactorizar Secuencia de Cambio de Mapa ✅ COMPLETADO
**Prioridad:** 🔴 Alta  
**Esfuerzo:** 1 día  
**Estado:** ✅ Completado

**Problema:** Código duplicado en 3 lugares con la misma secuencia de 12 pasos:
1. `task_login.py` - Login inicial del jugador
2. `task_walk.py` - Transiciones de mapa al caminar
3. `task_gm_commands.py` - Teletransporte GM

**Solución:**
- [x] Crear método `MapTransitionService.transition_player_to_map(user_id, new_map, new_x, new_y, heading)`
- [x] Encapsular toda la secuencia en un solo lugar
- [x] Parámetros opcionales para casos especiales (skip broadcast, etc.)
- [x] Migrar los 3 archivos al nuevo método
- [x] Tests unitarios del servicio

**Beneficios:**
- DRY (Don't Repeat Yourself)
- Menos bugs por inconsistencias
- Más fácil de mantener y testear
- Un solo lugar para agregar features (ej: efectos visuales de transición)

**Referencia:** Memoria `SYSTEM-RETRIEVED-MEMORY[68f2a6f1-3f47-4423-98cb-7aaa32fe1977]`

---

### 0.6.3-alpha - Validación de Longitud de Packets ✅ COMPLETADO
**Prioridad:** 🟡 Media  
**Esfuerzo:** 4-6 horas  
**Estado:** ✅ Completado

**Tareas:**
- [x] Agregar validación de longitud en `PacketReader`/`PacketValidator`
- [x] Validar antes de parsear en todas las tasks relevantes
- [x] Enviar error descriptivo al cliente si falla
- [x] Tests de packets malformados/truncados

**Beneficio:** Prevenir crashes por packets malformados, mejor seguridad

**Referencia:** `todo/TODO_REFACTORING.md#179-194`

---

### 0.6.4-alpha - Configuration Management ✅ COMPLETADO
**Prioridad:** 🟡 Media  
**Esfuerzo:** 2-3 horas  
**Estado:** ✅ Completado

**Tareas:**
- [x] Centralizar configuraciones hardcodeadas en ficheros de config (`config/server.toml`) y un `ConfigManager`
- [x] Configurar Redis host/port, server host/port, timeouts y límites principales
- [x] Documentar todas las configuraciones en `docs/CONFIGURATION.md`
- [x] Tests básicos de carga de configuración

**Beneficio:** Fácil configuración sin recompilar, mejor para deployment

**Referencia:** `todo/TODO_ARQUITECTURA.md#385-443`

---

## 🚀 Versiones Futuras (0.7.0+)

### 0.7.0-alpha - Sistema de Clases
**Prioridad:** 🔴 Alta  
**Esfuerzo:** 2-3 semanas  
**Estado:** ✅ Completado (2025-01-30)

**Features:**
- [x] Clases: Guerrero, Mago, Arquero, Clérigo
- [x] Atributos base por clase
- [x] ~~Restricciones de equipo por clase~~ (NO - siguiendo VB6, modificadores ya balancean)
- [x] Skills específicas por clase
- [x] Balanceo de stats iniciales
- [x] Selección de clase en creación de personaje
- [x] Tests completos (26 tests)

**Dependencias:** Ninguna (puede empezar tras completar 0.6.0) ✅

**Referencia:** `todo/TODO_CLASS_SYSTEM.md`

**Archivos creados:**
- `src/models/character_class.py`
- `src/services/game/class_service.py`
- `data/classes.toml`
- `tests/models/test_character_class.py`
- `tests/services/game/test_class_service.py`
- `tests/integration/test_class_system_integration.py`

---

### 0.8.0-alpha - Sistema de Partys/Grupos
**Prioridad:** 🔴 Alta  
**Esfuerzo:** 1-2 semanas  
**Estado:** Planificado

**Features:**
- [ ] Creación de parties (2-6 miembros)
- [ ] Sistema de líder de party
- [ ] Exp compartida entre miembros
- [ ] Chat de party
- [ ] Invitar/Expulsar miembros
- [ ] Disolver party automática si líder se desconecta
- [ ] Sistema de loot compartido

**Archivos a crear:**
- `src/models/party.py`
- `src/services/party_service.py`
- `src/repositories/party_repository.py`
- `src/tasks/party/`

**Dependencias:** Ninguna (independiente de clases)

**Referencia:** `todo/TODO_CARACTERISTICAS_VB6.md#33-52`

---

### 0.8.5-alpha - Party Finder (Opcional)
**Prioridad:** 🟢 Baja (funcionalidad opcional)  
**Esfuerzo:** 1 semana  
**Estado:** Planificado

**Features:**
- [ ] Sistema de búsqueda de parties disponibles
- [ ] Anunciar party al finder con filtros (nivel, actividad)
- [ ] Anunciar disponibilidad para unirse a party
- [ ] Filtrar parties por criterios
- [ ] Unirse a party directamente desde finder
- [ ] Expiración automática de anuncios

**Archivos a crear:**
- `src/models/party_finder.py`
- `src/services/party_finder_service.py`
- `src/repositories/party_finder_repository.py`
- `src/tasks/task_party_finder_*.py` (6 archivos)

**Dependencias:** Requiere sistema de Parties funcionando (0.8.0) ✅

**Referencia:** `todo/TODO_PARTY_FINDER.md`

**Nota:** Funcionalidad opcional, no crítica. Útil para servidores con muchos jugadores.

---

### 0.9.0-alpha - Sistema de Clanes/Guilds
**Prioridad:** 🔴 Alta  
**Esfuerzo:** 2-3 semanas  
**Estado:** Planificado

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

**Dependencias:** Requiere sistema de Partys funcionando (0.8.0)

**Referencia VB6:** `modGuilds.bas` (71KB), `clsClan.cls` (29KB)  
**Referencia:** `todo/TODO_CARACTERISTICAS_VB6.md#9-30`

---

### 0.10.0-alpha - Targeting por Click para Hechizos
**Prioridad:** 🟡 Media  
**Esfuerzo:** 1 semana  
**Estado:** Planificado

**Features:**
- [ ] Sistema de "click para seleccionar target" en hechizos
- [ ] Cursor cambia visualmente al modo targeting
- [ ] Cliente envía CAST_SPELL con coordenadas (x, y)
- [ ] Servidor valida rango antes de lanzar
- [ ] Se puede cancelar el targeting (ESC o click derecho)
- [ ] Formato antiguo (heading) sigue funcionando como fallback

**Nota:** Servidor **ya está preparado** para recibir coordenadas en CAST_SPELL (formato de 6 bytes). Solo falta modificar el cliente para enviarlas.

**Archivos a modificar:**
- Cliente Godot: `ui/hub/spell_list_panel.gd`
- Cliente Godot: `screens/game_screen.gd`
- Cliente Godot: `engine/autoload/game_protocol.gd`
- Servidor: `src/task_cast_spell.py` (opcional, ya soporta)

**Dependencias:** Ninguna (servidor ya preparado)

**Referencia:** `todo/TODO_SPELL_CLICK_TARGETING.md`

---

### 0.11.0-alpha - Hechizos Avanzados
**Prioridad:** 🔴 Alta  
**Esfuerzo:** 3-4 semanas  
**Estado:** Planificado

**Features:**
- [ ] Sistema de escuelas de magia (Fuego, Agua, Tierra, Aire, Luz, Oscuridad)
- [ ] Hechizos de área (AOE)
- [ ] Hechizos con duración y efectos over time (DoT)
- [ ] Sistema de runas y componentes
- [ ] Hechizos de invocación
- [ ] Protecciones y barreras mágicas
- [ ] Libros de hechizos equipables

**Archivos a modificar:**
- `src/models/spell.py` - Expandir funcionalidad
- `src/services/spell_service.py` - Nuevos sistemas
- `data/spells.toml` - Más hechizos

**Dependencias:** Conviene tener targeting por click listo (0.10.0)

**Referencia VB6:** `modHechizos.bas` (97KB)  
**Referencia:** `todo/TODO_CARACTERISTICAS_VB6.md#76-94`

---

### 0.12.0-alpha - Sistema de Facciones
**Prioridad:** 🟡 Media  
**Esfuerzo:** 2-3 semanas  
**Estado:** Planificado

**Features:**
- [ ] Sistema de facciones (Legión, Caos, Real, Neutral)
- [ ] Guerras automáticas entre facciones
- [ ] Zonas controladas por facciones
- [ ] Beneficios por pertenecer a facción
- [ ] Sistema de prestigio de facción
- [ ] NPCs de facciones con comportamiento diferenciado

**Archivos a crear:**
- `src/models/faction.py`
- `src/services/faction_service.py`
- `src/repositories/faction_repository.py`
- `data/factions.toml`

**Dependencias:** Requiere clanes/partys para interacción social (0.8.0, 0.9.0)

**Referencia VB6:** `ModFacciones.bas` (33KB), `praetorians.bas` (39KB)  
**Referencia:** `todo/TODO_CARACTERISTICAS_VB6.md#55-73`

---

### 0.13.0-alpha - Sistema de Quests
**Prioridad:** 🟡 Media  
**Esfuerzo:** 2-3 semanas  
**Estado:** Planificado

**Features:**
- [ ] Sistema de misiones/quests
- [ ] Objetivos (matar NPCs, recolectar items, hablar con NPCs)
- [ ] Recompensas (exp, oro, items)
- [ ] Cadenas de quests
- [ ] Quest log para jugadores
- [ ] NPCs que dan quests
- [ ] Validación de requisitos (nivel, clase, facción)

**Archivos a crear:**
- `src/models/quest.py`
- `src/services/quest_service.py`
- `src/repositories/quest_repository.py`
- `data/quests.toml`

**Dependencias:** Ninguna (independiente)

**Referencia:** `todo/TODO_GENERAL.md#131-138`

---

### 0.14.0-alpha - Banco Avanzado
**Prioridad:** 🟡 Media  
**Esfuerzo:** 1-2 semanas  
**Estado:** Planificado

**Features:**
- [ ] Sistema de préstamos bancarios
- [ ] Intereses sobre depósitos
- [ ] Transferencias entre jugadores
- [ ] Cajas de seguridad privadas
- [ ] Historial de transacciones
- [ ] Límites de depósito por nivel

**Archivos a modificar:**
- `src/services/banking_service.py` - Expandir funcionalidad
- `src/repositories/bank_repository.py` - Nuevas operaciones

**Dependencias:** Extiende banco actual (ya implementado en 0.4.0)

**Referencia VB6:** `modBanco.bas` (12KB)  
**Referencia:** `todo/TODO_CARACTERISTICAS_VB6.md#97-112`

---

### 0.15.0-alpha - Chat Mejorado
**Prioridad:** 🟡 Media  
**Esfuerzo:** 1-2 semanas  
**Estado:** Planificado

**Features:**
- [ ] Canales de chat (Global, Local, Party, Clan, Comercio)
- [ ] Sistema de amigos
- [ ] Mensajes privados mejorados
- [ ] Ignorar jugadores
- [ ] Historial de chat persistente
- [ ] Filtros de mensajes
- [ ] Comandos con autocompletado

**Archivos a crear:**
- `src/services/chat_service.py`
- `src/repositories/friends_repository.py`

**Dependencias:** Ninguna (independiente)

**Referencia:** `todo/TODO_GENERAL.md#140-146`

---

### 0.16.0-alpha - Sistema Anti-cheat/Centinelas
**Prioridad:** 🟡 Media  
**Esfuerzo:** 2-3 semanas  
**Estado:** Planificado

**Features:**
- [ ] Detección de speed hack
- [ ] Anti-mass cloning (múltiples cuentas)
- [ ] Detección de movimientos inválidos
- [ ] Sistema de reportes automáticos
- [ ] Baneo temporal/permanente
- [ ] Log de actividades sospechosas

**Archivos a crear:**
- `src/services/centinel_service.py`
- `src/services/anti_cheat_service.py`

**Dependencias:** Requiere logging estructurado y buena cobertura de tests

**Referencia VB6:** `modCentinela.bas` (23KB), `clsAntiMassClon.cls`  
**Referencia:** `todo/TODO_CARACTERISTICAS_VB6.md#135-151`

---

### 0.17.0-alpha - Estadísticas Avanzadas
**Prioridad:** 🟢 Baja  
**Esfuerzo:** 1-2 semanas  
**Estado:** Planificado

**Features:**
- [ ] Estadísticas globales del servidor
- [ ] Rankings (PKs, nivel, riqueza)
- [ ] Estadísticas por facción
- [ ] Historial de eventos importantes
- [ ] Sistema de logros y trofeos
- [ ] API de estadísticas

**Archivos a modificar:**
- `src/services/statistics_service.py` - Expandir

**Dependencias:** Requiere datos consolidados, quizás Event Bus

**Referencia VB6:** `Statistics.bas` (15KB), `clsEstadisticasIPC.cls`  
**Referencia:** `todo/TODO_CARACTERISTICAS_VB6.md#154-169`

---

### 0.18.0-alpha - Sistema de Sonido por Mapa
**Prioridad:** 🟢 Baja  
**Esfuerzo:** 1 semana  
**Estado:** Planificado

**Features:**
- [ ] Música ambiental por mapa
- [ ] Efectos de sonido por zona
- [ ] Sonidos de combate
- [ ] Sistema de ambientes dinámicos
- [ ] Configuración de sonido por usuario

**Archivos a crear:**
- `src/services/sound_service.py`
- `data/map_sounds.toml`

**Dependencias:** Requiere transición de mapas estable (ya implementado)

**Referencia VB6:** `clsMapSoundManager.cls`  
**Referencia:** `todo/TODO_CARACTERISTICAS_VB6.md#172-187`

---

### 0.19.0-alpha - Foro/Noticias Interno
**Prioridad:** 🟢 Baja  
**Esfuerzo:** 1 semana  
**Estado:** Planificado

**Features:**
- [ ] Foro interno del servidor
- [ ] Sistema de noticias y anuncios
- [ ] Secciones por tema (Comercio, Clanes, Ayuda)
- [ ] Sistema de moderación
- [ ] Búsqueda de posts
- [ ] Posts fijos (pinned)

**Archivos a crear:**
- `src/models/forum_post.py`
- `src/services/forum_service.py`
- `src/repositories/forum_repository.py`

**Dependencias:** Ninguna (independiente)

**Referencia VB6:** `modForum.bas` (14KB)  
**Referencia:** `todo/TODO_CARACTERISTICAS_VB6.md#115-132`

---

### 0.20.0-alpha - Seguridad IP Avanzada
**Prioridad:** 🟢 Baja  
**Esfuerzo:** 1 semana  
**Estado:** Planificado

**Features:**
- [ ] Lista blanca/negra de IPs
- [ ] Límite de conexiones por IP
- [ ] Detección de ataques DDoS básicos
- [ ] Sistema de bans por IP/rango
- [ ] Logs de conexiones por IP

**Archivos a crear:**
- `src/services/ip_security_service.py`
- `data/ip_security.toml`

**Dependencias:** Ninguna (independiente)

**Referencia VB6:** `SecurityIp.bas` (12KB)  
**Referencia:** `todo/TODO_CARACTERISTICAS_VB6.md#207-222`

---

## 🏗️ Mejoras Arquitecturales (Opcionales)

Estas mejoras no bloquean features pero mejoran la calidad del código:

### Service Container / Dependency Injection
**Prioridad:** 🟢 Baja  
**Esfuerzo:** 4-6 horas  
**Cuándo:** Antes de 0.9.0 (clanes)

**Beneficios:**
- Inyección automática de dependencias
- Menos código boilerplate
- Mejor testabilidad

**Referencia:** `todo/TODO_ARQUITECTURA.md#534-640`

---

### Event Bus / Message Bus
**Prioridad:** 🟢 Baja  
**Esfuerzo:** 6-8 horas  
**Cuándo:** Antes de 0.13.0 (quests) o 0.17.0 (logros)

**Beneficios:**
- Desacoplamiento de componentes
- Fácil agregar listeners para eventos
- Útil para logros, quests, notificaciones

**Referencia:** `todo/TODO_ARQUITECTURA.md#534-640`

---

### Command Pattern para Tasks
**Prioridad:** 🟡 Media  
**Esfuerzo:** 8-10 horas  
**Cuándo:** Antes de 0.11.0 (hechizos avanzados)

**Beneficios:**
- Undo/Redo de acciones
- Cola de comandos
- Mejor logging de acciones

**Referencia:** `todo/TODO_ARQUITECTURA.md#534-640`

---

### Repository Pattern Mejorado
**Prioridad:** 🟢 Baja  
**Esfuerzo:** 10-12 horas  
**Cuándo:** Cuando tengas tiempo

**Beneficios:**
- Abstracción de persistencia
- Fácil cambiar de Redis a PostgreSQL
- Mejor separación de responsabilidades

**Referencia:** `todo/TODO_ARQUITECTURA.md#534-640`

---

### Logging Estructurado (JSON)
**Prioridad:** 🟢 Baja  
**Esfuerzo:** 2-3 horas  
**Cuándo:** Antes de producción

**Beneficios:**
- Logs parseables automáticamente
- Mejor análisis en producción
- Integración con herramientas de monitoring

**Opciones:**
- `structlog` - Logging estructurado para Python
- `python-json-logger` - JSON formatter para logging estándar

**Referencia:** `todo/TODO_REFACTORING.md#197-209`

---

## 📱 Cliente Godot (Paralelo al servidor)

Estas mejoras pueden hacerse en paralelo al desarrollo del servidor:

### Mostrar Posición en GUI
**Prioridad:** 🔴 Alta  
**Esfuerzo:** 1 hora

**Beneficios:** Facilita debugging y testing

**Referencia:** `todo/TODO_CLIENTE.md#7-28`

---

### Feedback Visual de Acciones
**Prioridad:** 🟡 Media  
**Esfuerzo:** 2-3 horas

**Acciones:**
- Recoger item (sonido + animación)
- Tirar item (sonido + animación)
- Atacar (efecto visual mejorado)
- Recibir daño (screen shake, efecto rojo)

**Referencia:** `todo/TODO_CLIENTE.md#41-49`

---

### Panel de Inventario Completo
**Prioridad:** 🟡 Media  
**Esfuerzo:** 1 semana

**Features:**
- Mostrar items con iconos
- Drag & drop para reorganizar
- Click derecho para usar/equipar
- Tooltip con stats del item

**Referencia:** `todo/TODO_CLIENTE.md#50-58`

---

### Minimapa
**Prioridad:** 🟢 Baja  
**Esfuerzo:** 3-4 horas

**Referencia:** `todo/TODO_CLIENTE.md#63-64`

---

## 📊 Criterios de Priorización

### 🔴 Alta Prioridad
- Impacto directo en gameplay
- Requerido para contenido end-game
- Mejora significativa de experiencia social
- Estabilidad y calidad del código

### 🟡 Media Prioridad
- Funcionalidades importantes pero no críticas
- Mejoras de sistemas existentes
- Contenido para jugadores avanzados

### 🟢 Baja Prioridad
- Funcionalidades opcionales
- Mejoras cosméticas/de calidad
- Herramientas administrativas

---

## 🎯 Recomendación de Orden de Implementación

### **Fase 1: Completar 0.6.0-alpha (1-2 semanas)**
1. ✅ 0.6.1 - Tests faltantes
2. ✅ 0.6.2 - Refactor MapTransitionService
3. ✅ 0.6.3 - Validación de packets
4. ✅ 0.6.4 - Configuration Management

### **Fase 2: Gameplay Core (6-8 semanas)**
5. 0.7.0 - Sistema de Clases
6. 0.8.0 - Partys
7. 0.9.0 - Clanes
8. 0.10.0 - Targeting hechizos
9. 0.11.0 - Hechizos avanzados

### **Fase 3: Contenido End-game (8-12 semanas)**
10. 0.12.0 - Facciones
11. 0.13.0 - Quests
12. 0.14.0 - Banco avanzado
13. 0.15.0 - Chat mejorado
14. 0.16.0 - Anti-cheat

### **Fase 4: Polish y Extras (4-6 semanas)**
15. 0.17.0 - Estadísticas
16. 0.18.0 - Sonido
17. 0.19.0 - Foro
18. 0.20.0 - Seguridad IP

---

## 📝 Notas Importantes

1. **Una feature por versión:** Cada versión se enfoca en una sola característica principal
2. **Tests obligatorios:** Cada feature debe tener tests completos antes de merge
3. **Documentación completa:** Actualizar docs antes de cerrar versión
4. **Performance first:** Optimizar para 1000+ jugadores concurrentes
5. **Seguridad:** Validar todos los inputs del cliente
6. **Compatibilidad:** Mantener compatibilidad con protocolo de cliente existente

---

## 🔗 Referencias

- **Servidor VB6:** `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Codigo/`
- **Cliente Godot:** `clientes/ArgentumOnlineGodot/`
- **Documentación existente:** `docs/`
- **TODOs detallados:** `todo/`

---

**Última actualización:** 2025-01-29  
**Autor:** Roadmap consolidado de todos los TODOs  
**Estado:** 📋 Documento maestro de planificación
