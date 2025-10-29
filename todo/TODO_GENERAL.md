# TODO General - PyAO Server

**Estado:** 📋 Roadmap de Versiones y Fechas  
**Prioridad:** Mixta  
**Última actualización:** 2025-01-29

---

## 📊 Estado Actual del Proyecto

**Versión:** 0.6.0-alpha (completado)  
**Tests:** 1123 pasando (100%)  
**Cobertura:** 78%  
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
- ✅ IA de NPCs configurable con Pathfinding A*
- ✅ Sistema de Trabajo (Tala, Pesca, Minería)

---

## 📚 Índice de Documentación TODO

Este proyecto tiene varios documentos TODO especializados:

- **TODO_REFACTORING.md** - Refactorings técnicos pendientes
- **TODO_ARQUITECTURA.md** - Mejoras arquitecturales (DI, Event System, etc.)
- **TODO_NPC_FACTORY.md** - Sistema de factory para NPCs
- **TODO_CLIENTE.md** - Mejoras del cliente Godot
- **TODO_CARACTERISTICAS_VB6.md** - 🎯 **Características del servidor VB6 faltantes (DETALLES TÉCNICOS)**
- **TODO_MAP_TRANSITIONS.md** - Sistema de transiciones entre mapas
- **TODO_SPELL_CLICK_TARGETING.md** - Sistema de targeting de hechizos
- **TODO_POST_REORGANIZACION.md** - Mejoras post-reorganización
- **TODO_GENERAL.md** (este archivo) - **Roadmap de versiones y fechas**

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

### ✅ Versión 0.6.0-alpha - IA de NPCs y Sistema de Trabajo (100% COMPLETADO) 🎉
- [x] IA de NPCs configurable (daño, cooldown, aggro_range)
- [x] Pathfinding A* para NPCs (4 direcciones)
- [x] Sistema de trabajo completo (Tala, Pesca, Minería)
- [x] Herramientas equipables y recursos
- [x] Transiciones de mapa por rangos (120+ transiciones)

---

## 📝 Versión 0.7.0-alpha - Sistema Social

### Sistema de Clanes/Guilds
**Detalles técnicos en:** `TODO_CARACTERISTICAS_VB6.md#sistema-de-clanesguilds`
- 📅 **Fecha estimada:** 2-3 semanas
- 🔴 **Prioridad:** Alta
- 📁 **Referencia VB6:** `modGuilds.bas` (71KB), `clsClan.cls` (29KB)

### Sistema de Partys/Grupos
**Detalles técnicos en:** `TODO_CARACTERISTICAS_VB6.md#sistema-de-partysgrupos`
- 📅 **Fecha estimada:** 1-2 semanas
- 🔴 **Prioridad:** Alta
- 📁 **Referencia VB6:** `clsParty.cls` (19KB), `mdParty.bas` (19KB)

### Sistema de Clases
- 📅 **Fecha estimada:** 2-3 semanas
- 🟡 **Prioridad:** Media
- [ ] Atributos base por clase (Guerrero, Mago, Arquero, etc.)
- [ ] Habilidades especiales por clase
- [ ] Restricciones de equipamiento por clase
- [ ] Balance de clases

---

## 📝 Versión 0.8.0-alpha - Expansión de Combate

### Sistema de Facciones
**Detalles técnicos en:** `TODO_CARACTERISTICAS_VB6.md#sistema-de-facciones`
- 📅 **Fecha estimada:** 2-3 semanas
- 🟡 **Prioridad:** Media
- 📁 **Referencia VB6:** `ModFacciones.bas` (33KB), `praetorians.bas` (39KB)

### Hechizos Avanzados
**Detalles técnicos en:** `TODO_CARACTERISTICAS_VB6.md#sistema-de-hechizos-avanzado`
- 📅 **Fecha estimada:** 3-4 semanas
- 🔴 **Prioridad:** Alta
- 📁 **Referencia VB6:** `modHechizos.bas` (97KB)

### Sistema de Quests
- 📅 **Fecha estimada:** 2-3 semanas
- 🟡 **Prioridad:** Media
- [ ] QuestService para misiones
- [ ] Objetivos (matar X NPCs, recolectar Y items)
- [ ] Recompensas (oro, experiencia, items)
- [ ] Cadenas de quests
- [ ] Quest log del jugador

### Social Mejorado
- 📅 **Fecha estimada:** 1-2 semanas
- 🟡 **Prioridad:** Media
- [ ] Chat mejorado con canales (global, local, party)
- [ ] Sistema de amigos
- [ ] Mensajes privados
- [ ] Emotes y gestos

---

## 📝 Versión 0.9.0-alpha - Economía Avanzada

### Banco Avanzado
**Detalles técnicos en:** `TODO_CARACTERISTICAS_VB6.md#sistema-de-banco-avanzado`
- 📅 **Fecha estimada:** 1-2 semanas
- 🟡 **Prioridad:** Media
- 📁 **Referencia VB6:** `modBanco.bas` (12KB)

### Sistema de Foro/Noticias
**Detalles técnicos en:** `TODO_CARACTERISTICAS_VB6.md#sistema-de-foronoticias`
- 📅 **Fecha estimada:** 1 semana
- 🟢 **Prioridad:** Baja
- 📁 **Referencia VB6:** `modForum.bas` (14KB)

### Economía Dinámica
- 📅 **Fecha estimada:** 2-3 semanas
- 🟡 **Prioridad:** Media
- [ ] Precios dinámicos según oferta/demanda en todo el juego
- [ ] Sistema de inflación/deflación
- [ ] Eventos económicos globales

---

## 📝 Versión 0.10.0-alpha - Seguridad y Estadísticas

### Sistema de Centinelas/Anti-cheat
**Detalles técnicos en:** `TODO_CARACTERISTICAS_VB6.md#sistema-de-centinelasanti-cheat`
- 📅 **Fecha estimada:** 2-3 semanas
- 🟡 **Prioridad:** Media
- 📁 **Referencia VB6:** `modCentinela.bas` (23KB), `clsAntiMassClon.cls`

### Estadísticas Avanzadas
**Detalles técnicos en:** `TODO_CARACTERISTICAS_VB6.md#sistema-de-estadísticas-avanzado`
- 📅 **Fecha estimada:** 1-2 semanas
- 🟢 **Prioridad:** Baja
- 📁 **Referencia VB6:** `Statistics.bas` (15KB), `clsEstadisticasIPC.cls`

### Seguridad Mejorada
- 📅 **Fecha estimada:** 1-2 semanas
- 🟡 **Prioridad:** Media
- [ ] Rate limiting por IP (anti-spam)
- [ ] Validación avanzada de packets
- [ ] Logs de seguridad
- [ ] Sistema de bans automáticos

---

## 📝 Versión 0.11.0-alpha - Multimedia y Calidad

### Sistema de Sonido por Mapa
**Detalles técnicos en:** `TODO_CARACTERISTICAS_VB6.md#sistema-de-sonido-por-mapa`
- 📅 **Fecha estimada:** 1 semana
- 🟢 **Prioridad:** Baja
- 📁 **Referencia VB6:** `clsMapSoundManager.cls`

### Historial y Logs Avanzados
**Detalles técnicos en:** `TODO_CARACTERISTICAS_VB6.md#sistema-de-historiallogs-avanzado`
- 📅 **Fecha estimada:** 1 semana
- 🟢 **Prioridad:** Baja
- 📁 **Referencia VB6:** `History.bas` (5KB)

### Mejoras de UI/UX
- 📅 **Fecha estimada:** 1-2 semanas
- 🟢 **Prioridad:** Baja
- [ ] Animaciones de combate mejoradas
- [ ] Efectos visuales especiales
- [ ] Interfaz de administración web
- [ ] Sistema de tutoriales

---

## 📝 Versión 0.12.0-alpha - Seguridad Avanzada

### Seguridad IP
**Detalles técnicos en:** `TODO_CARACTERISTICAS_VB6.md#sistema-de-seguridad-ip`
- 📅 **Fecha estimada:** 1 semana
- 🟢 **Prioridad:** Baja
- 📁 **Referencia VB6:** `SecurityIp.bas` (12KB)

### Protección DDoS
- 📅 **Fecha estimada:** 2-3 semanas
- 🟡 **Prioridad:** Media
- [ ] Detección de ataques DDoS básicos
- [ ] Rate limiting avanzado
- [ ] Sistema de whitelist/blacklist IP

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

## 🔗 **Referencias Principales**

- **Servidor VB6:** `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Codigo/`
- **Características Faltantes:** `todo/TODO_CARACTERISTICAS_VB6.md` 🎯
- **Documentación Técnica:** `docs/`
- **Cliente Godot:** `clientes/ArgentumOnlineGodot/`

---

*Última actualización: 2025-01-29*  
*Versión actual: v0.6.0-alpha (completado)*  
*Próxima versión: v0.7.0-alpha (Sistema Social)*
