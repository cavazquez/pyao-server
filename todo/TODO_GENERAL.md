# TODO General - PyAO Server

**Estado:** 📋 Lista maestra de tareas y mejoras  
**Prioridad:** Mixta  
**Última actualización:** 2025-10-20

---

## 📊 Estado Actual del Proyecto

**Versión:** 0.6.0-alpha (en progreso)  
**Tests:** 955 pasando (100%)  
**Cobertura:** 74%  
**Calidad:** Excelente (0 errores linting/mypy)

**Sistemas Completados Recientemente:**
- ✅ Sistema de Energía/Stamina (100%)
- ✅ Sistema de Críticos basado en Agilidad (100%)
- ✅ Sistema de Esquives basado en Agilidad (100%)
- ✅ NPC Factory Pattern
- ✅ Loot Tables Configurables
- ✅ MapTransitionService y PlayerMapService
- ✅ PacketValidator (100%)
- ✅ PacketReader (100%) - ¡Migración completa!
- ✅ Oro en Banco (PacketIDs 111, 112)
- ✅ Refactorización de Validación Centralizada

---

## 📚 Índice de Documentación TODO

Este proyecto tiene varios documentos TODO especializados:

- **TODO_REFACTORING.md** - Refactorings técnicos pendientes
- **TODO_ARQUITECTURA.md** - Mejoras arquitecturales (DI, Event System, etc.)
- **TODO_NPC_FACTORY.md** - Sistema de factory para NPCs
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

---

## 📝 Versión 0.6.0-alpha - Refactorings, IA de NPCs y Economía

### Refactorings Completados ✅
- [x] **MapTransitionService encapsulado** ✅ - Ya implementado en `player_map_service.py`
- [x] **Refactorización de validación de packets** ✅ - Completado (TaskCommerceSell, TaskCommerceBuy, TaskInventoryClick)
  - Validación centralizada en TaskFactory
  - Tasks reciben datos ya validados
  - ~70 líneas de código eliminadas
- [x] **Migración PacketReader 100% completa** ✅
  - Todas las tasks usan PacketReader y PacketValidator
  - Eliminado uso de struct.unpack directo
  - Validación consistente en toda la aplicación

### IA de NPCs Mejorada
- [x] **Parámetros de IA configurables** ✅ - Completado
  - Rango de agresión configurable por NPC
  - Cooldown entre ataques configurable
  - Daño base configurable
  - 11 NPCs balanceados con personalidades únicas
  - Documentación: `docs/NPC_AI_CONFIGURABLE.md`
- [x] **Pathfinding A*** ✅ - Completado
  - Algoritmo A* optimizado para tiles (4 direcciones)
  - NPCs rodean obstáculos inteligentemente
  - Límite de profundidad configurable
  - Fallback a movimiento simple
  - Documentación: `docs/PATHFINDING_ASTAR.md`
- 💡 Las funcionalidades avanzadas de IA (patrullas, huida, refuerzos) se posponen para una versión posterior.

### Sistema de Skills
- [ ] Subir skills con uso (minería, tala, pesca)
- [ ] Experiencia de skills (0-100)
- [ ] Niveles de skills con bonificadores
- [ ] Packet WORK para trabajar

### Economía Avanzada
- [x] **Depositar/retirar oro en banco** ✅ - Completado (PacketIDs 111, 112)
  - TaskBankExtractGold y TaskBankDepositGold implementadas
  - UPDATE_BANK_GOLD (PacketID 19) enviado al cliente
  - Métodos add_gold() y remove_gold() en PlayerRepository y BankRepository
  - Redis como almacenamiento (key: bank:{user_id}:gold)
  - Validación de amount=0 con mensajes claros
  - +10 tests unitarios (955 tests total)
- 💡 Precios dinámicos globales según oferta/demanda se posponen para una versión posterior.

---

## 📝 Versión 0.7.0-alpha - Clases y Hechizos Avanzados

### Sistema de Clases
- [ ] Atributos base por clase (Guerrero, Mago, Arquero, etc.)
- [ ] Habilidades especiales por clase
- [ ] Restricciones de equipamiento por clase
- [ ] Balance de clases

### IA avanzada (pospuesta desde 0.6.0)
- [ ] NPCs que patrullan rutas predefinidas
- [ ] NPCs que huyen cuando tienen poca vida
- [ ] NPCs que llaman refuerzos

### Hechizos Avanzados
- [ ] Hechizos de área (AOE)
- [ ] Hechizos de buff/debuff
- [ ] Hechizos de curación
- [ ] Hechizos de invocación
- [ ] Cooldowns de hechizos
- [ ] Animaciones y efectos visuales mejorados

---

## 📝 Versión 0.8.0-alpha - Social y Multiplayer

### Sistema de Party
- [ ] Crear/unirse a party
- [ ] Compartir experiencia
- [ ] Chat de party
- [ ] Líder de party
- [ ] Expulsar miembros

### Sistema de Quests
- [ ] QuestService para misiones
- [ ] Objetivos (matar X NPCs, recolectar Y items)
- [ ] Recompensas (oro, experiencia, items)
- [ ] Cadenas de quests
- [ ] Quest log del jugador

### Social
- [ ] Chat mejorado con canales (global, local, party)
- [ ] Sistema de amigos
- [ ] Mensajes privados
- [ ] Emotes y gestos

### Economía dinámica (pospuesta desde 0.6.0)
- [ ] Precios dinámicos según oferta/demanda en todo el juego

---

## 📝 Versión 0.9.0-alpha - Seguridad, Testing y Optimización

### Seguridad
- [ ] Rate limiting por IP (anti-spam)
- [x] Hash de passwords con argon2
- [ ] Validación de rangos en todos los packets
- [ ] Sanitización de strings (nombres, chat)
- [ ] Prevención de exploits conocidos
- [ ] Tokens de sesión con expiración
- [ ] Límite de intentos de login fallidos

### Testing y Calidad
- [ ] Tests de integración end-to-end
- [ ] Tests de carga (múltiples jugadores simultáneos)
- [ ] Tests de stress (límites del servidor)
- [ ] Tests de concurrencia (race conditions)
- [ ] Coverage > 90%
- [ ] Bot de prueba automatizado (simula cliente)

### Optimización
- [ ] Broadcast inteligente (solo jugadores en rango visible 15x15)
- [ ] Batch de múltiples updates en un solo packet
- [ ] Throttling de movimiento
- [ ] Pipeline de comandos Redis
- [ ] Caché en memoria para datos frecuentes
- [ ] TTL automático para datos temporales

### Refactoring y Limpieza
- [ ] **Revisar y limpiar todos los `# noqa`** - Analizar si son necesarios
- [ ] **Revisar y limpiar todos los `# type: ignore`** - Mejorar tipos
- [ ] **Analizar complejidad ciclomática** - Simplificar métodos con C901, PLR0912
- [ ] **Reducir variables locales** - Refactorizar métodos con PLR0914
- [ ] **Reorganizar datos en Redis** - Estandarizar nomenclatura de keys

---

## 📝 Versión 1.0.0 - Producción

### Documentación
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Guía de contribución (CONTRIBUTING.md)
- [ ] Guía de deployment completa
- [ ] Troubleshooting común
- [ ] Changelog detallado
- [ ] Tutoriales (crear packet, agregar NPC, crear hechizo)

### CI/CD y DevOps
- [ ] CI/CD robusto con GitHub Actions
- [ ] Automated testing en CI
- [ ] Automated deployment
- [ ] Rollback automático en errores
- [ ] Health checks y auto-restart
- [ ] Docker Compose para desarrollo

### Monitoreo y Observabilidad
- [ ] Prometheus para métricas
- [ ] Grafana para dashboards
- [ ] Métricas de jugadores (online, nuevos, activos)
- [ ] Métricas de performance (CPU, RAM, Redis)
- [ ] Alertas automáticas
- [ ] Structured logging (JSON)
- [ ] Agregación de logs (ELK stack)

### Performance Final
- [ ] Performance optimizado y validado
- [ ] Profiling de código (identificar cuellos de botella)
- [ ] Validaciones de mapa optimizadas
- [ ] Cargar mapas al iniciar servidor

### Últimos Fixes
- [ ] Revisión final de bugs
- [ ] Validación de seguridad
- [ ] Testing exhaustivo

---

## 📋 Features Post-1.0.0 (Expansiones Futuras)

### 🐉 Sistema de NPCs por Bioma
**Requisito:** Cliente terminado con soporte de biomas

- [ ] Definir biomas en mapas (forest, dungeon, desert, snow, swamp, cave)
- [ ] Configuración por bioma en `data/npc_spawns_by_biome.toml`
- [ ] NPCBiomeSpawnService para spawn automático
- [ ] Spawn zones configurables por mapa
- [ ] Respawn automático según bioma
- [ ] Selección ponderada de NPCs (weights)
- [ ] Nivel aleatorio (min_level/max_level)

**Esfuerzo estimado:** 4-6 horas  
**Beneficios:** Mundo más dinámico, configurable, balance por nivel

### Sistema de Guild (Largo plazo)
- [ ] Crear/unirse a guild
- [ ] Rangos en guild
- [ ] Chat de guild
- [ ] Guerra entre guilds
- [ ] Territorio de guild

### PvP (Largo plazo)
- [ ] Combate jugador vs jugador
- [ ] Zonas PvP/seguras
- [ ] Sistema de karma/criminal
- [ ] Penalizaciones por matar jugadores
- [ ] Duelos 1v1

### Panel de Administración (Largo plazo)
- [ ] Dashboard web para administradores
- [ ] Ver jugadores online
- [ ] Kickear/banear jugadores
- [ ] Modificar stats de jugadores
- [ ] Spawn de items/NPCs
- [ ] Logs en tiempo real

### Protocolo Avanzado (Largo plazo)
- [ ] Versionado de protocolo (compatibilidad)
- [ ] Compresión de packets (zlib/gzip)
- [ ] Encriptación de comunicación (TLS)
- [ ] Heartbeat para detectar desconexiones
- [ ] Reconexión automática

### Escalabilidad (Largo plazo)
- [ ] Soporte para múltiples instancias del servidor
- [ ] Load balancer
- [ ] Redis Cluster para alta disponibilidad
- [ ] Separación de servicios (microservicios)
- [ ] Message queue (RabbitMQ/Kafka)

---

## 📚 Mapas y Contenido (Tareas Técnicas)

### Mapas y Datos
- [ ] **Importar mapas del AO Godot** - Convertir archivos `.map` a formato JSON
- [ ] **Script de conversión** - `scripts/convert_map.py` para automatizar
- [ ] **Validar todos los mapas** - Asegurar que tiles bloqueados sean correctos
- [ ] **Optimizar formato de mapas** - Considerar formato binario más eficiente
- [ ] **Cargar mapas al iniciar servidor** - `map_manager.load_map_data()`

### Contenido (NPCs, Items, Mapas)
- [ ] Más variedad de monstruos
- [ ] NPCs con diálogos
- [ ] NPCs que dan quests
- [ ] Bosses con mecánicas especiales
- [ ] Más armas y armaduras
- [ ] Pociones y consumibles variados
- [ ] Items únicos/legendarios
- [ ] Más ciudades y dungeons

---

## 📊 Estadísticas del Proyecto

**Versión actual:** 0.5.0-alpha (100% completado)  
**Próxima versión:** 0.6.0-alpha (Refactorings, IA de NPCs, Skills)

**Tests actuales:** 945 (100% pasando)  
**Cobertura:** 74%  
**Servicios implementados:** 14+ (StaminaService, NPCFactory, PlayerMapService)  
**Efectos de tick:** 5 (StaminaRegenEffect)  
**NPCs con loot tables:** 10  
**Mapas con colisiones:** 290  

**Sistemas completados:**  
Login, Movimiento, Combate, Loot Tables, Banco, Comercio, Magia, Colisiones, Energía/Stamina, Transiciones de Mapa

---

**Última actualización:** 2025-10-20  
**Mantenido por:** Equipo PyAO  
**Estado:** 🔄 En desarrollo activo
