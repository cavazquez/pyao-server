# TODO General - PyAO Server

**Estado:** 📋 Lista maestra de tareas y mejoras  
**Prioridad:** Mixta  
**Última actualización:** 2025-01-20

---

## 📊 Estado Actual del Proyecto

**Versión:** 0.5.0-alpha (100% COMPLETADO) 🎉  
**Tests:** 807 pasando (100%)  
**Cobertura:** Alta  
**Commits en sesión:** 47  
**Calidad:** Excelente (0 errores linting/mypy)

**Sistemas Completados Recientemente:**
- ✅ Sistema de Energía/Stamina (100%)
- ✅ Sistema de Críticos basado en Agilidad (100%)
- ✅ Sistema de Esquives basado en Agilidad (100%)
- ✅ NPC Factory Pattern
- ✅ Loot Tables Configurables
- ✅ PacketReader (21/33 tasks migradas)

---

## 📚 Índice de Documentación TODO

Este proyecto tiene varios documentos TODO especializados:

- **TODO_REFACTORING.md** - Refactorings técnicos (PacketReader, MessageSender)
- **TODO_ARQUITECTURA.md** - Mejoras arquitecturales (DI, Event System, etc.)
- **TODO_NPC_FACTORY.md** - Sistema de factory para NPCs
- **TODO_PACKET_READER_REFACTORING.md** - Migración de tasks a PacketReader
- **TODO_CLIENTE.md** - Mejoras del cliente Godot
- **TODO_GENERAL.md** (este archivo) - Lista general de features y mejoras

---

## 🎯 Roadmap de Versiones

### ✅ Versión 0.2.0-alpha - Sistema de Movimiento y Colisiones
- [x] Sistema de colisiones completo
- [x] Detección de NPCs y jugadores bloqueando
- [x] Minimapa actualizado al login
- [x] REQUEST_POSITION_UPDATE (tecla L)
- [x] Heading guardado y cargado correctamente
- [x] Fix bug parsing CHARACTER_MOVE
- [x] Broadcast de movimiento optimizado
- [x] Bug fix: Tiles bloqueados al remover NPCs
- [x] Validación de tiles ocupados en add_npc

### ✅ Versión 0.3.0-alpha - Sistema de Respawn de NPCs
- [x] Respawn automático con tiempo aleatorio
- [x] Búsqueda de posición libre aleatoria cercana
- [x] Reintentos no bloqueantes con asyncio
- [x] Logs INFO para diagnóstico de bloqueos
- [x] NPCs permanentes (respawn_time=0)

### ✅ Versión 0.4.0-alpha - Sistemas de Economía
- [x] Sistema de banco completo
- [x] Sistema de comercio completo
- [x] Loot tables configurables
- [x] Items variados (armas, armaduras, pociones)

### ✅ Versión 0.5.0-alpha - Refactorings y Contenido (100% COMPLETADO) 🎉

**Completado:**
- [x] MessageSender refactoring (100% completado)
- [x] PacketReader implementado (21/33 tasks migradas - 64%)
- [x] NPC Factory Pattern
- [x] **Sistema de Energía/Stamina - COMPLETADO ✅**
  - [x] Consumo de energía por acción (walk: 1, attack: 2, spell: 3)
  - [x] Regeneración automática (2 puntos/segundo)
  - [x] Condiciones: solo regenera si hambre > 0 y sed > 0
  - [x] Efectos de energía baja (bloquea acciones si energía = 0)
  - [x] Balance de energía configurado
  - [x] StaminaService y StaminaRegenEffect integrados
- [x] **Sistema de críticos basado en agilidad ✅**
  - [x] CriticalCalculator implementado
  - [x] Probabilidad base 15% + bonus por AGI
  - [x] Multiplicador de daño 2x
  - [x] Integrado en CombatService

**Completado adicional:**
- [x] Sistema de esquives ✅
- [x] Mensajes de daño al jugador (usando CONSOLE_MSG) ✅
- [x] Inventario lleno - manejar casos límite ✅
- [x] Sistema de transiciones de mapa (funcional, pendiente sincronización) ✅

**Bug resuelto - Transiciones de mapa:** ✅
- [x] Cliente se congela después de cambiar de mapa - **RESUELTO**
- Causa: No se enviaban los NPCs/jugadores/objetos del nuevo mapa
- Solución: Implementado envío completo de entidades en `_handle_map_transition()`
- Documentación: `docs/MAP_TRANSITION_FIX.md`

**Movido a v0.5.0+ (Features más complejas):**
- [ ] Precios dinámicos según oferta/demanda
- [ ] Depositar/retirar oro
- [ ] Pathfinding básico (A* o similar)
- [ ] NPCs que patrullan rutas predefinidas
- [ ] NPCs que huyen cuando tienen poca vida
- [ ] NPCs que llaman refuerzos
- [ ] Diferentes comportamientos por tipo de NPC
- [ ] Rango de agresión configurable por NPC
- [ ] Cooldown entre ataques

### 📝 Versión 0.6.0-alpha - Clases, Hechizos y Social

**Sistema de Clases:**
- [ ] Atributos base por clase (Guerrero, Mago, etc.)
- [ ] Habilidades especiales por clase
- [ ] Restricciones de equipamiento por clase
- [ ] Balance de clases

**Hechizos Avanzados:**
- [ ] Hechizos de área (AOE)
- [ ] Hechizos de buff/debuff
- [ ] Hechizos de curación
- [ ] Hechizos de invocación
- [ ] Cooldowns de hechizos
- [ ] Animaciones y efectos visuales

**Sistema de Skills:**
- [ ] Subir skills con uso (minería, tala, pesca)
- [ ] Experiencia de skills
- [ ] Niveles de skills (0-100)
- [ ] Bonificadores por nivel de skill
- [ ] Packet WORK para trabajar

### 📝 Versión 0.7.0-alpha - Configuración, Quests y Social
- [ ] Configuration Management
- [ ] Sistema de quests
- [ ] Eventos mundiales
- [ ] Sistema de amigos

### 📝 Versión 0.8.0-alpha - Social y Party
- [ ] Sistema de party
- [ ] Chat mejorado con canales

### 📝 Versión 1.0.0 - Producción
- [ ] Todas las funcionalidades core
- [ ] Performance optimizado
- [ ] Seguridad robusta
- [ ] Documentación completa
- [ ] Coverage > 90%

---

## 🔥 Prioridad Alta

### Sistema de Combate
- [x] Implementar `CombatService` para combate jugador vs NPC ✅
- [x] Calcular daño basado en stats (fuerza, armas, armadura) ✅
- [x] Animaciones de ataque (FX) ✅
- [x] Muerte de NPCs ✅
- [x] Experiencia al matar NPCs ✅
- [x] Packet `ATTACK` para iniciar combate ✅
- [x] Sistema de Respawn de NPCs ✅
- [x] Sistema de críticos basado en agilidad ✅
- [ ] Sistema de esquives (preparado, pendiente integrar)
- [ ] Packet `DAMAGE` para mostrar daño recibido

### Sistema de Loot
- [x] Drops de oro al matar NPCs ✅
- [x] Recoger items del suelo (`PICK_UP`) ✅
- [x] Visualización de items en el mapa ✅
- [x] Drops de items según tabla de probabilidades ✅
- [x] Loot tables configurables por NPC ✅
- [ ] Inventario lleno - manejar casos límite

### IA de NPCs Mejorada
- [ ] Pathfinding básico (A* o similar)
- [ ] NPCs que patrullan rutas predefinidas
- [ ] NPCs que huyen cuando tienen poca vida
- [ ] NPCs que llaman refuerzos
- [ ] Diferentes comportamientos por tipo de NPC
- [ ] Rango de agresión configurable por NPC
- [ ] Cooldown entre ataques

---

## 🎯 Prioridad Media

### Sistema de Comercio
- [x] `TradeService` para comercio con NPCs ✅
- [x] Ventana de comercio (comprar/vender) ✅
- [x] Inventario de comerciantes ✅
- [x] Packet `COMMERCE_BUY` y `COMMERCE_SELL` ✅
- [ ] Precios dinámicos según oferta/demanda (→ v0.5.0)

### Sistema de Banco
- [x] `BankService` para gestión de banco ✅
- [x] Depositar/retirar items ✅
- [x] Límite de slots en banco ✅
- [x] Packet `BANK_DEPOSIT` y `BANK_EXTRACT_ITEM` ✅
- [ ] Depositar/retirar oro (→ v0.5.0)

---

## 🔧 Refactoring y Limpieza de Código

### Análisis de Código
- [ ] **Revisar todos los `# noqa`** - Analizar si son necesarios o si se puede arreglar el código
- [ ] **Revisar todos los `# type: ignore`** - Analizar si se pueden eliminar mejorando los tipos
- [x] **Dividir MessageSender** ✅ - Completado con 8 componentes especializados
- [ ] **Analizar complejidad ciclomática** - Métodos con `C901` y `PLR0912`
- [ ] **Reducir variables locales** - Métodos con `PLR0914` (too many local variables)

### Refactoring Prioritario
- [ ] **Refactorizar PacketValidator** - Cada task debería tener un método `validate_*()` que retorne bool
  - Problema actual: Métodos como `read_slot()`, `read_quantity()` retornan valores o None
  - Propuesta: Métodos como `validate_bank_deposit()` que retornan bool y guardan datos parseados
  - Beneficio: API más clara, validación centralizada, mejor separación de responsabilidades
  - Ejemplo: `validator.validate_gm_teleport()` retorna tupla o None (ya implementado parcialmente)
  
- [ ] **Encapsular secuencia de cambio de mapa** - Código duplicado en 3 lugares
  - Lugares con duplicación:
    1. `task_login.py` - Al hacer login inicial
    2. `task_walk.py` - Al cambiar de mapa por transición
    3. `task_gm_commands.py` - Al teletransportarse
  - Secuencia común:
    1. Enviar CHANGE_MAP
    2. Delay 100ms para carga del mapa
    3. Actualizar posición en Redis
    4. Enviar POS_UPDATE
    5. Remover jugador del mapa anterior (MapManager)
    6. Broadcast CHARACTER_REMOVE en mapa anterior
    7. Agregar jugador al nuevo mapa (MapManager)
    8. Enviar CHARACTER_CREATE del propio jugador
    9. Enviar todos los jugadores existentes
    10. Enviar todos los NPCs
    11. Enviar todos los objetos del suelo
    12. Broadcast CHARACTER_CREATE a otros jugadores
  - Propuesta: Crear `MapTransitionService.transition_player_to_map()`
  - Beneficio: DRY, menos bugs, más fácil de mantener y testear

### Mapas y Datos
- [ ] **Importar mapas del AO Godot** - Convertir archivos `.map` a formato JSON
- [ ] **Script de conversión** - `scripts/convert_map.py` para automatizar
- [ ] **Validar todos los mapas** - Asegurar que tiles bloqueados sean correctos
- [ ] **Optimizar formato de mapas** - Considerar formato binario más eficiente

### Integración de Colisiones
- [x] **Integrar validación en TaskWalk** ✅
- [x] **Integrar validación en NPCMovementEffect** ✅
- [x] **Actualizar índice en todos los movimientos** ✅
- [x] **Método get_tile_occupant** ✅
- [ ] **Cargar mapas al iniciar servidor** - `map_manager.load_map_data()`

### Estructura de Datos Redis
- [ ] **Reorganizar datos en Redis** - Muchos datos del mismo tipo están en diferentes lugares
  - Revisar keys de jugadores, NPCs, items, etc.
  - Estandarizar nomenclatura de keys
  - Agrupar datos relacionados
  - Documentar estructura de datos en Redis

---

## 📊 Optimizaciones y Performance

### Broadcast Inteligente
- [ ] Solo enviar updates a jugadores en rango visible (15x15 tiles)
- [ ] Batch de múltiples updates en un solo packet
- [ ] Throttling de movimiento (no enviar cada tile)
- [ ] Compresión de packets grandes

### Redis Optimizations
- [ ] Pipeline de comandos Redis
- [ ] Caché en memoria para datos frecuentes
- [ ] TTL automático para datos temporales
- [ ] Índices secundarios para búsquedas rápidas

### Validaciones de Mapa
- [x] Validar tiles bloqueados antes de mover ✅
- [ ] Cargar datos de mapas desde archivos `.map`
- [ ] Colisiones con objetos del mapa
- [ ] Zonas seguras (no PvP)

---

## 🧪 Testing y Calidad

### Tests Faltantes
- [ ] Tests de integración end-to-end
- [ ] Tests de carga (múltiples jugadores simultáneos)
- [ ] Tests de stress (límites del servidor)
- [ ] Tests de concurrencia (race conditions)
- [ ] Tests de desconexión inesperada
- [ ] Coverage > 90%

### Herramientas de Testing
- [ ] Bot de prueba automatizado (simula cliente)
- [ ] Generador de tráfico para load testing
- [ ] Métricas de performance (latencia, throughput)
- [ ] Profiling de código (identificar cuellos de botella)

---

## 🔒 Seguridad

### Validaciones
- [ ] Rate limiting por IP (anti-spam)
- [ ] Validación de rangos en todos los packets
- [ ] Sanitización de strings (nombres, chat)
- [ ] Prevención de exploits conocidos
- [ ] Logs de seguridad (intentos de hack)

### Autenticación
- [ ] Hash de passwords con bcrypt/argon2
- [ ] Tokens de sesión con expiración
- [ ] Logout automático por inactividad
- [ ] Límite de intentos de login fallidos
- [ ] 2FA opcional

---

## 🎮 Gameplay

### Sistema de Quests
- [ ] `QuestService` para misiones
- [ ] Objetivos de quest (matar X NPCs, recolectar Y items)
- [ ] Recompensas (oro, experiencia, items)
- [ ] Cadenas de quests
- [ ] Quest log del jugador

### Sistema de Party
- [ ] Crear/unirse a party
- [ ] Compartir experiencia
- [ ] Chat de party
- [ ] Líder de party
- [ ] Expulsar miembros

### Sistema de Guild
- [ ] Crear/unirse a guild
- [ ] Rangos en guild
- [ ] Chat de guild
- [ ] Guerra entre guilds
- [ ] Territorio de guild

### PvP
- [ ] Combate jugador vs jugador
- [ ] Zonas PvP/seguras
- [ ] Sistema de karma/criminal
- [ ] Penalizaciones por matar jugadores
- [ ] Duelos 1v1

---

## 🛠️ Herramientas y Utilidades

### Panel de Administración
- [ ] Dashboard web para administradores
- [ ] Ver jugadores online
- [ ] Kickear/banear jugadores
- [ ] Modificar stats de jugadores
- [ ] Spawn de items/NPCs
- [ ] Logs en tiempo real

### Comandos de GM
- [ ] `/summon <npc_id>` - Invocar NPC
- [ ] `/teleport <x> <y>` - Teletransportar
- [ ] `/give <item_id> <cantidad>` - Dar items
- [ ] `/setlevel <nivel>` - Cambiar nivel
- [ ] `/kick <usuario>` - Expulsar jugador
- [ ] `/ban <usuario>` - Banear jugador

### Herramientas de Desarrollo
- [ ] Hot reload de configuración (sin reiniciar)
- [ ] Modo debug con comandos especiales
- [ ] Generador de mapas
- [ ] Editor de NPCs
- [ ] Editor de items

---

## 📡 Protocolo

### Mejoras de Protocolo
- [ ] Versionado de protocolo (compatibilidad)
- [ ] Compresión de packets (zlib/gzip)
- [ ] Encriptación de comunicación (TLS)
- [ ] Heartbeat para detectar desconexiones
- [ ] Reconexión automática

---

## 📈 Monitoreo y Observabilidad

### Métricas
- [ ] Prometheus para métricas
- [ ] Grafana para dashboards
- [ ] Métricas de jugadores (online, nuevos, activos)
- [ ] Métricas de performance (CPU, RAM, Redis)
- [ ] Alertas automáticas

### Logging
- [ ] Structured logging (JSON)
- [ ] Agregación de logs (ELK stack)
- [ ] Niveles de log configurables por módulo
- [ ] Rotación de logs automática
- [ ] Logs de auditoría

---

## 🌐 Infraestructura

### Escalabilidad
- [ ] Soporte para múltiples instancias del servidor
- [ ] Load balancer
- [ ] Redis Cluster para alta disponibilidad
- [ ] Separación de servicios (microservicios)
- [ ] Message queue (RabbitMQ/Kafka)

### DevOps
- [ ] Docker Compose para desarrollo
- [ ] CI/CD con GitHub Actions
- [ ] Automated testing en CI
- [ ] Automated deployment
- [ ] Rollback automático en errores
- [ ] Health checks y auto-restart

---

## 📚 Documentación

### Docs Faltantes
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Guía de contribución (CONTRIBUTING.md)
- [ ] Guía de deployment
- [ ] Troubleshooting común
- [ ] Changelog detallado
- [ ] **Documentación de movimiento de personajes** - Explicar flujo completo
  - Cliente: _MovePlayer, _CanMoveTo, WriteWalk
  - Servidor: TaskWalk, validaciones, broadcast
  - Paquetes: WALK, CHARACTER_MOVE, CHARACTER_CHANGE, POS_UPDATE
  - Colisiones: can_move_to, get_tile_occupant
  - Heading: guardado en Redis, sincronización cliente-servidor

### Tutoriales
- [ ] Cómo crear un nuevo packet
- [ ] Cómo agregar un nuevo NPC
- [ ] Cómo crear un nuevo hechizo
- [ ] Cómo agregar un nuevo efecto de tick
- [ ] Cómo hacer debugging

---

## 🎨 Contenido

### NPCs
- [ ] Más variedad de monstruos
- [ ] NPCs con diálogos
- [ ] NPCs que dan quests
- [ ] Bosses con mecánicas especiales
- [ ] NPCs aliados (guardias)

### Items
- [ ] Más armas y armaduras
- [ ] Pociones y consumibles
- [ ] Items únicos/legendarios
- [ ] Sets de items con bonos
- [ ] Items craftables

### Mapas
- [ ] Más ciudades y dungeons
- [ ] Mapas con eventos especiales
- [ ] Mapas dinámicos (día/noche)
- [ ] Clima (lluvia, nieve)
- [ ] Portales entre mapas

---

## 💡 Ideas Innovadoras

### Gameplay Único
- [ ] Sistema de clima que afecta stats
- [ ] Eventos mundiales (invasiones, bosses)
- [ ] Economía dinámica (inflación, deflación)
- [ ] Construcción de casas/bases
- [ ] Farming y agricultura
- [ ] Mascotas que ayudan en combate

### Social
- [ ] Chat global con canales
- [ ] Sistema de amigos
- [ ] Mensajes privados
- [ ] Emotes y gestos
- [ ] Ranking de jugadores

### Progresión
- [ ] Sistema de achievements
- [ ] Títulos desbloqueables
- [ ] Skins y cosméticos
- [ ] Battle pass / temporadas
- [ ] Eventos limitados

---

## 📝 Notas y Decisiones Pendientes

### Decisiones de Diseño
- [ ] ¿Usar WebSockets en lugar de TCP raw?
- [ ] ¿Migrar a PostgreSQL para algunos datos?
- [ ] ¿Implementar sharding de jugadores por mapa?
- [ ] ¿Agregar sistema de plugins/mods?

### Investigación Necesaria
- [ ] Mejores prácticas de game server architecture
- [ ] Anti-cheat systems
- [ ] Netcode optimization
- [ ] Database sharding strategies

---

## 📊 Estado Actual del Proyecto

**Versión actual:** 0.5.0-alpha  
**Tests actuales:** 807 (100% pasando)  
**Servicios implementados:** 14+ (StaminaService, NPCFactory)  
**Efectos de tick:** 5 (StaminaRegenEffect)  
**NPCs con loot tables:** 10 (Goblin, Lobo, Orco, Araña, Serpiente, Dragón, Esqueleto, Zombie, Troll, Ogro)  
**Mapas con colisiones:** 290  
**Sistemas completados:** Login, Movimiento, Combate, Loot Tables, Banco, Comercio, Magia, Colisiones, Energía/Stamina

---

**Última actualización:** 2025-01-20  
**Mantenido por:** Equipo PyAO  
**Estado:** 🔄 En desarrollo activo
