# TODO General - PyAO Server

**Estado:** 📋 Roadmap de Versiones y Fechas  
**Prioridad:** Mixta  
**Última actualización:** 2025-01-29

---

## 📊 Estado Actual del Proyecto

**Versión:** 0.6.0-alpha (EN PROGRESO - 78% completado)  
**Tests:** 1123 pasando (100%)  
**Cobertura:** 78%  
**Calidad:** Excelente (0 errores linting/mypy)

**Sistemas Completados en 0.6.0:**
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
- ✅ IA de NPCs configurable con Pathfinding A*
- ✅ Sistema de Trabajo (Tala, Pesca, Minería)

**Pendientes para completar 0.6.0:**
- ⏳ Tests faltantes (work/, admin/, map services) → 0.6.1-alpha
- ⏳ Refactorizar secuencia de cambio de mapa → 0.6.2-alpha
- ⏳ Validación de longitud de packets → 0.6.3-alpha
- ⏳ Configuration Management → 0.6.4-alpha

---

## 📚 Índice de Documentación TODO

Este proyecto tiene varios documentos TODO especializados:

- **ROADMAP_VERSIONES.md** - 🎯 **DOCUMENTO MAESTRO - Roadmap completo 0.6.0 → 0.20.0**
- **TODO_GENERAL.md** (este archivo) - Roadmap legacy (ver ROADMAP_VERSIONES.md)
- **TODO_REFACTORING.md** - Refactorings técnicos pendientes
- **TODO_ARQUITECTURA.md** - Mejoras arquitecturales (DI, Event System, etc.)
- **TODO_NPC_FACTORY.md** - Sistema de factory para NPCs
- **TODO_CLIENTE.md** - Mejoras del cliente Godot
- **TODO_CARACTERISTICAS_VB6.md** - Características del servidor VB6 faltantes (DETALLES TÉCNICOS)
- **TODO_MAP_TRANSITIONS.md** - Sistema de transiciones entre mapas
- **TODO_SPELL_CLICK_TARGETING.md** - Sistema de targeting de hechizos
- **TODO_POST_REORGANIZACION.md** - Mejoras post-reorganización

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
- [x] MessageSender refactoring (100% completado)
- [x] PacketReader implementado (100% migrado)
- [x] NPC Factory Pattern
- [x] Sistema de Energía/Stamina - COMPLETADO ✅
- [x] Sistema de críticos basado en agilidad ✅
- [x] Sistema de esquives ✅
- [x] Sistema de transiciones de mapa (funcional) ✅

### ⏳ Versión 0.6.0-alpha - IA de NPCs y Sistema de Trabajo (EN PROGRESO - 78%)
- [x] IA de NPCs configurable (daño, cooldown, aggro_range)
- [x] Pathfinding A* para NPCs (4 direcciones)
- [x] Sistema de trabajo completo (Tala, Pesca, Minería)
- [x] Herramientas equipables y recursos
- [x] Transiciones de mapa por rangos (120+ transiciones)
- [x] Tests faltantes (work/, admin/, map services) - COMPLETADO ✅
- [x] Refactorizar secuencia de cambio de mapa - COMPLETADO ✅
- [ ] Validación de longitud de packets → **0.6.3-alpha**
- [ ] Configuration Management → **0.6.4-alpha**

### 🆕 Pendientes de Stats de Login
- [x] Incluir agilidad y fuerza en el paquete combinado enviado al logearse.
- [x] Implementar paquetes individuales para enviar agilidad y fuerza cuando sea necesario.

---

---

## 🚀 Versiones Futuras

> **NOTA:** Para el roadmap completo y detallado, ver **`ROADMAP_VERSIONES.md`**

### 📝 Versión 0.7.0-alpha - Sistema de Clases
- 📅 **Fecha estimada:** 2-3 semanas
- 🔴 **Prioridad:** Alta
- **Features:** Guerrero, Mago, Arquero, Clérigo con atributos y restricciones

### 📝 Versión 0.8.0-alpha - Sistema de Partys/Grupos
- 📅 **Fecha estimada:** 1-2 semanas
- 🔴 **Prioridad:** Alta
- **Features:** Exp compartida, chat de party, loot compartido

### 📝 Versión 0.9.0-alpha - Sistema de Clanes/Guilds
- 📅 **Fecha estimada:** 2-3 semanas
- 🔴 **Prioridad:** Alta
- **Features:** Creación, rangos, almacén, guerras entre clanes

### 📝 Versión 0.10.0-alpha - Targeting por Click para Hechizos
- 📅 **Fecha estimada:** 1 semana
- 🟡 **Prioridad:** Media
- **Features:** Click para seleccionar target, cursor visual

### 📝 Versión 0.11.0-alpha - Hechizos Avanzados
- 📅 **Fecha estimada:** 3-4 semanas
- 🔴 **Prioridad:** Alta
- **Features:** Escuelas de magia, AoE, DoT, invocaciones

### 📝 Versión 0.12.0-alpha - Sistema de Facciones
- 📅 **Fecha estimada:** 2-3 semanas
- 🟡 **Prioridad:** Media
- **Features:** Legión/Caos/Real/Neutral, guerras, zonas controladas

### 📝 Versión 0.13.0-alpha - Sistema de Quests
- 📅 **Fecha estimada:** 2-3 semanas
- 🟡 **Prioridad:** Media
- **Features:** Misiones, objetivos, recompensas, cadenas de quests

### 📝 Versión 0.14.0-alpha - Banco Avanzado
- 📅 **Fecha estimada:** 1-2 semanas
- 🟡 **Prioridad:** Media
- **Features:** Préstamos, intereses, transferencias

### 📝 Versión 0.15.0-alpha - Chat Mejorado
- 📅 **Fecha estimada:** 1-2 semanas
- 🟡 **Prioridad:** Media
- **Features:** Canales, amigos, mensajes privados

### 📝 Versión 0.16.0-alpha - Sistema Anti-cheat
- 📅 **Fecha estimada:** 2-3 semanas
- 🟡 **Prioridad:** Media
- **Features:** Speed hack detection, anti-mass cloning

### 📝 Versión 0.17.0-alpha - Estadísticas Avanzadas
- 📅 **Fecha estimada:** 1-2 semanas
- 🟢 **Prioridad:** Baja
- **Features:** Rankings, logros, API de estadísticas

### 📝 Versión 0.18.0-alpha - Sistema de Sonido
- 📅 **Fecha estimada:** 1 semana
- 🟢 **Prioridad:** Baja
- **Features:** Música ambiental por mapa, efectos de sonido

### 📝 Versión 0.19.0-alpha - Foro/Noticias
- 📅 **Fecha estimada:** 1 semana
- 🟢 **Prioridad:** Baja
- **Features:** Foro interno, anuncios, moderación

### 📝 Versión 0.20.0-alpha - Seguridad IP
- 📅 **Fecha estimada:** 1 semana
- 🟢 **Prioridad:** Baja
- **Features:** Whitelist/blacklist, límite de conexiones por IP


---

## 🎯 **Criterios de Priorización y Planificación**

### 🔴 **Alta Prioridad** (Implementar primero)
- Impacto directo en gameplay
- Requerido para contenido end-game
- Mejora significativa de experiencia social
- Referencias claras en servidor VB6

### 🟡 **Media Prioridad** (Implementar después)
- Funcionalidades importantes pero no críticas
- Mejoras de sistemas existentes
- Contenido para jugadores avanzados

### 🟢 **Baja Prioridad** (Implementar al final)
- Funcionalidades opcionales
- Mejoras cosméticas/de calidad
- Herramientas administrativas

---

## 📊 **Métricas de Progreso**

- **Features Completados:** 45/67 (67%)
- **Sistemas Críticos:** 28/35 (80%)
- **Contenido End-game:** 8/25 (32%)
- **Sistemas Sociales:** 3/15 (20%)

---

## 🧭 Backlog Adicional

### Carga diferida de mapas
- 🔶 **Prioridad:** Media
- ⏱️ **Esfuerzo estimado:** 6-8 horas
- 📝 **Descripción:** Ajustar el ciclo de vida de `MapResourcesService` y de los loaders asociados para que el mapa se cargue recién cuando el primer jugador ingrese a él, evitando el pre-load durante el arranque del servidor.
- ✅ **Beneficios:** Reduce el tiempo de inicio, baja el consumo de memoria inicial y permite distribuir el costo de carga en tiempo de ejecución.

---

## 🔗 **Referencias Principales**

- **Servidor VB6:** `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Codigo/`
- **Características Faltantes:** `todo/TODO_CARACTERISTICAS_VB6.md` 🎯
- **Documentación Técnica:** `docs/`
- **Cliente Godot:** `clientes/ArgentumOnlineGodot/`

---

*Última actualización: 2025-01-29*  
*Versión actual: v0.6.0-alpha (EN PROGRESO - 78%)*  
*Próxima versión: v0.7.0-alpha (Sistema de Clases)*

---

## 📌 Nota Importante

**Para el roadmap completo y detallado de todas las versiones (0.6.0 → 0.20.0), ver:**
- **`ROADMAP_VERSIONES.md`** - Documento maestro con todas las features, dependencias y detalles técnicos
