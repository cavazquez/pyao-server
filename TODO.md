# TODO - PyAO Server

Lista de tareas pendientes, mejoras y próximas funcionalidades para el servidor.

## 🔧 Refactoring y Limpieza de Código

### Análisis de Código
- [ ] **Revisar todos los `# noqa`** - Analizar si son necesarios o si se puede arreglar el código
- [ ] **Revisar todos los `# type: ignore`** - Analizar si se pueden eliminar mejorando los tipos
- [ ] **Dividir MessageSender** - Archivo muy grande, considerar separar en módulos
  - Podría ser: `message_sender_stats.py`, `message_sender_combat.py`, etc.
- [ ] **Analizar complejidad ciclomática** - Métodos con `C901` y `PLR0912`
- [ ] **Reducir variables locales** - Métodos con `PLR0914` (too many local variables)

### Mapas y Datos
- [ ] **Importar mapas del AO Godot** - Convertir archivos `.map` a formato JSON
- [ ] **Script de conversión** - `scripts/convert_map.py` para automatizar
- [ ] **Validar todos los mapas** - Asegurar que tiles bloqueados sean correctos
- [ ] **Optimizar formato de mapas** - Considerar formato binario más eficiente

### Integración de Colisiones
- [ ] **Integrar validación en TaskWalk** - Usar `map_manager.can_move_to()`
- [ ] **Integrar validación en NPCMovementEffect** - Prevenir NPCs encima de jugadores
- [ ] **Cargar mapas al iniciar servidor** - `map_manager.load_map_data()`
- [ ] **Actualizar índice en todos los movimientos** - `update_player_tile()`, `update_npc_tile()`

## 🔥 Prioridad Alta

### Sistema de Combate
- [ ] Implementar `CombatService` para combate jugador vs NPC
- [ ] Calcular daño basado en stats (fuerza, armas, armadura)
- [ ] Sistema de críticos y esquives
- [ ] Animaciones de ataque (FX)
- [ ] Muerte de NPCs y respawn
- [ ] Experiencia y nivel al matar NPCs
- [ ] Packet `ATTACK` para iniciar combate
- [ ] Packet `DAMAGE` para mostrar daño recibido

### Sistema de Loot
- [ ] Drops de oro al matar NPCs
- [ ] Drops de items según tabla de probabilidades
- [ ] Recoger items del suelo (`PICK_UP`)
- [ ] Visualización de items en el mapa
- [ ] Inventario lleno - manejar casos límite

### IA de NPCs Mejorada
- [ ] Pathfinding básico (A* o similar)
- [ ] NPCs que patrullan rutas predefinidas
- [ ] NPCs que huyen cuando tienen poca vida
- [ ] NPCs que llaman refuerzos
- [ ] Diferentes comportamientos por tipo de NPC
- [ ] Rango de agresión configurable por NPC
- [ ] Cooldown entre ataques

## 🎯 Prioridad Media

### Sistema de Comercio
- [ ] `TradeService` para comercio con NPCs
- [ ] Ventana de comercio (comprar/vender)
- [ ] Precios dinámicos según oferta/demanda
- [ ] Inventario de comerciantes
- [ ] Packet `COMMERCE_BUY` y `COMMERCE_SELL`

### Sistema de Banco
- [ ] `BankService` para gestión de banco
- [ ] Depositar/retirar items
- [ ] Depositar/retirar oro
- [ ] Límite de slots en banco
- [ ] Packet `BANK_DEPOSIT` y `BANK_WITHDRAW`

### Sistema de Skills
- [ ] Subir skills con uso (minería, tala, pesca)
- [ ] Experiencia de skills
- [ ] Niveles de skills (0-100)
- [ ] Bonificadores por nivel de skill
- [ ] Packet `WORK` para trabajar

### Sistema de Clases
- [ ] Atributos base por clase (Guerrero, Mago, etc.)
- [ ] Habilidades especiales por clase
- [ ] Restricciones de equipamiento por clase
- [ ] Balance de clases

### Hechizos Avanzados
- [ ] Hechizos de área (AOE)
- [ ] Hechizos de buff/debuff
- [ ] Hechizos de curación
- [ ] Hechizos de invocación
- [ ] Cooldowns de hechizos
- [ ] Animaciones y efectos visuales

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
- [ ] Validar tiles bloqueados antes de mover
- [ ] Cargar datos de mapas desde archivos `.map`
- [ ] Colisiones con objetos del mapa
- [ ] Zonas seguras (no PvP)

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

## 📡 Protocolo

### Mejoras de Protocolo
- [ ] Versionado de protocolo (compatibilidad)
- [ ] Compresión de packets (zlib/gzip)
- [ ] Encriptación de comunicación (TLS)
- [ ] Heartbeat para detectar desconexiones
- [ ] Reconexión automática

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

## 📚 Documentación

### Docs Faltantes
- [ ] API documentation (OpenAPI/Swagger)
- [ ] Guía de contribución (CONTRIBUTING.md)
- [ ] Guía de deployment
- [ ] Troubleshooting común
- [ ] Changelog detallado

### Tutoriales
- [ ] Cómo crear un nuevo packet
- [ ] Cómo agregar un nuevo NPC
- [ ] Cómo crear un nuevo hechizo
- [ ] Cómo agregar un nuevo efecto de tick
- [ ] Cómo hacer debugging

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

## 🔄 Refactoring

### Código
- [ ] Extraer constantes mágicas a configuración
- [ ] Reducir complejidad ciclomática (< 10)
- [ ] Eliminar código duplicado
- [ ] Mejorar nombres de variables/funciones
- [ ] Type hints completos (mypy strict)

### Arquitectura
- [ ] Event-driven architecture para desacoplar
- [ ] Domain-driven design para lógica compleja
- [ ] CQRS para separar lectura/escritura
- [ ] Repository pattern más estricto
- [ ] Dependency injection más clara

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

## 📝 Notas

### Decisiones de Diseño Pendientes
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

## 🎯 Roadmap Sugerido

### Versión 0.2.0 - Combate y Loot
- Sistema de combate completo
- Drops y experiencia
- Muerte y respawn de NPCs

### Versión 0.3.0 - Economía
- Sistema de comercio
- Sistema de banco
- Más items y equipamiento

### Versión 0.4.0 - Social
- Sistema de party
- Chat mejorado
- Sistema de amigos

### Versión 0.5.0 - Contenido
- Más mapas y NPCs
- Sistema de quests
- Eventos mundiales

### Versión 1.0.0 - Producción
- Todas las funcionalidades core
- Performance optimizado
- Seguridad robusta
- Documentación completa

---

**Última actualización:** 2025-10-16  
**Tests actuales:** 374  
**Servicios implementados:** 7  
**Efectos de tick:** 4
