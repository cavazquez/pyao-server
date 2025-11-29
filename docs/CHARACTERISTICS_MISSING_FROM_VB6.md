# Características Faltantes del Servidor VB6

**Fecha de Análisis:** 2025-01-31  
**Versión Actual:** 0.9.1-alpha  
**Base de Comparación:** Servidor VB6 Argentum Online 0.13.3

---

## 📊 Resumen Ejecutivo

Este documento lista las características que existen en el servidor VB6 original pero que **aún no están implementadas** en el servidor Python actual.

**Estadísticas:**
- **Total de sistemas VB6 analizados:** 56 archivos `.bas` y `.cls`
- **Sistemas implementados:** ✅ ~70% de funcionalidades core
- **Sistemas faltantes:** ❌ ~30% de funcionalidades (principalmente avanzadas)

---

## ✅ Sistemas Completamente Implementados

### 1. Sistema de Autenticación ✅
- **VB6 Reference:** `Modulo_UsUaRiOs.bas`
- **Estado:** ✅ Completo
- Login, creación de cuentas, sesiones

### 2. Sistema de Personajes ✅
- **VB6 Reference:** `Characters.bas`
- **Estado:** ✅ Completo
- Creación, atributos, stats, hambre/sed

### 3. Sistema de Mapas ✅
- **VB6 Reference:** `GameLogic.bas`, `ModAreas.bas`
- **Estado:** ✅ Completo
- 290 mapas, transiciones, puertas, tiles bloqueados

### 4. Sistema de NPCs ✅
- **VB6 Reference:** `MODULO_NPCs.bas`, `AI_NPC.bas`
- **Estado:** ✅ Completo
- 336 NPCs, spawning, IA básica, respawn, paralización

### 5. Sistema de Combate ✅
- **VB6 Reference:** `SistemaCombate.bas`
- **Estado:** ✅ Completo
- Combate jugador vs NPC, daño, críticos, loot, experiencia

### 6. Sistema de Inventario ✅
- **VB6 Reference:** `Modulo_InventANDobj.bas`, `InvUsuario.bas`
- **Estado:** ✅ Completo
- Gestión de items, stacking, equipamiento, 1,070 items importados

### 7. Sistema de Comercio ✅
- **VB6 Reference:** `Comercio.bas`, `mdlCOmercioConUsuario.bas`
- **Estado:** ✅ Completo
- Compra/venta con mercaderes, validación

### 8. Sistema de Banco ✅
- **VB6 Reference:** `modBanco.bas`
- **Estado:** ✅ Básico implementado
- Depósitos y extracciones funcionando
- ❌ **Falta:** Préstamos, intereses, transferencias entre jugadores

### 9. Sistema de Trabajo ✅
- **VB6 Reference:** `Trabajo.bas`
- **Estado:** ✅ Completo
- Tala, pesca, minería, herramientas, recursos

### 10. Sistema de Hechizos ✅
- **VB6 Reference:** `modHechizos.bas` (97KB)
- **Estado:** ✅ Básico implementado
- 11 hechizos básicos, casteo, validación de rango/mana
- ❌ **Falta:** Escuelas de magia, AOE, DoT, runas, invocaciones (ver "Hechizos Avanzados")

### 11. Sistema de Partys/Grupos ✅
- **VB6 Reference:** `clsParty.cls`, `mdParty.bas`
- **Estado:** ✅ Completo (v0.8.0-alpha)
- Crear, invitar, aceptar, abandonar, exp compartida, loot compartido

### 12. Sistema de Clanes/Guilds ✅
- **VB6 Reference:** `modGuilds.bas`, `clsClan.cls`
- **Estado:** ✅ Core completo (v0.9.0-alpha)
- Crear, invitar, promover, degradar, transferir liderazgo, chat
- ❌ **Falta:** Almacén del clan, alianzas, guerras, edificio del clan

### 13. Sistema de Items ✅
- **VB6 Reference:** `obj.dat`
- **Estado:** ✅ Completo
- **1,070 items importados** (1,049 del obj.dat + 21 extras)
- Armas: 53/53 ✅
- Escudos: 11/11 ✅
- Armaduras: 257/257 ✅
- Cascos: 15/15 ✅

---

## ❌ Sistemas Completamente Faltantes

### 1. Sistema de Facciones
- **VB6 Reference:** `ModFacciones.bas` (33KB), `praetorians.bas` (39KB)
- **Prioridad:** 🟡 Media
- **Versión Planeada:** v0.12.0-alpha

**Funcionalidades:**
- [ ] Sistema de facciones (Legión, Caos, Real, Neutral)
- [ ] Guerras automáticas entre facciones
- [ ] Zonas controladas por facciones
- [ ] Beneficios por pertenecer a facción
- [ ] Sistema de prestigio de facción
- [ ] NPCs pretorianos y de facciones
- [ ] Armaduras faccionarias
- [ ] Sistema de rangos de facción (15 rangos)

**Archivos a crear:**
- `src/models/faction.py`
- `src/services/faction_service.py`
- `src/repositories/faction_repository.py`
- `src/tasks/faction/`
- `data/factions.toml`

---

### 2. Sistema de Foro/Noticias
- **VB6 Reference:** `modForum.bas` (14KB)
- **Prioridad:** 🟢 Baja
- **Versión Planeada:** v0.19.0-alpha

**Funcionalidades:**
- [ ] Foro interno del servidor
- [ ] Sistema de noticias y anuncios (máx. 5 anuncios)
- [ ] Mensajes de foro (máx. 30 mensajes por foro)
- [ ] Secciones por facción (REAL, CAOS)
- [ ] Sistema de moderación
- [ ] Búsqueda de posts
- [ ] Posts fijos (pinned)

**Archivos a crear:**
- `src/models/forum_post.py`
- `src/services/forum_service.py`
- `src/repositories/forum_repository.py`
- `data/forums.toml`

---

### 3. Sistema de Quests/Misiones
- **VB6 Reference:** No existe módulo específico (implementación implícita)
- **Prioridad:** 🟡 Media
- **Versión Planeada:** v0.13.0-alpha

**Funcionalidades:**
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

---

### 4. Sistema de Centinelas/Anti-cheat
- **VB6 Reference:** `modCentinela.bas` (23KB), `clsAntiMassClon.cls`
- **Prioridad:** 🟡 Media
- **Versión Planeada:** v0.16.0-alpha

**Funcionalidades:**
- [ ] Detección de speed hack
- [ ] Anti-mass cloning (múltiples cuentas desde misma IP)
- [ ] Detección de movimientos inválidos
- [ ] Sistema de reportes automáticos
- [ ] Baneo temporal/permanente
- [ ] Log de actividades sospechosas

**Archivos a crear:**
- `src/services/centinel_service.py`
- `src/services/anti_cheat_service.py`
- `src/repositories/ban_repository.py`
- `data/anti_cheat_rules.toml`

---

### 5. Sistema de Sonido por Mapa
- **VB6 Reference:** `clsMapSoundManager.cls`
- **Prioridad:** 🟢 Baja
- **Versión Planeada:** v0.18.0-alpha

**Funcionalidades:**
- [ ] Música ambiental por mapa
- [ ] Efectos de sonido por zona
- [ ] Sonidos de combate
- [ ] Sistema de ambientes dinámicos
- [ ] Configuración de sonido por usuario

**Archivos a crear:**
- `src/services/sound_service.py`
- `src/network/msg_sound.py`
- `data/map_sounds.toml`

---

### 6. Sistema de Seguridad IP
- **VB6 Reference:** `SecurityIp.bas` (12KB)
- **Prioridad:** 🟢 Baja
- **Versión Planeada:** v0.20.0-alpha

**Funcionalidades:**
- [ ] Lista blanca/negra de IPs
- [ ] Límite de conexiones por IP
- [ ] Detección de ataques DDoS básicos
- [ ] Sistema de bans por IP/rango
- [ ] Logs de conexiones por IP

**Archivos a crear:**
- `src/services/ip_security_service.py`
- `src/repositories/ip_ban_repository.py`
- `data/ip_security.toml`

---

### 7. Sistema de Invisibilidad
- **VB6 Reference:** `modInvisibles.bas`
- **Prioridad:** 🟡 Media
- **Versión Planeada:** No asignada aún

**Funcionalidades:**
- [ ] Poner/quitar invisibilidad a jugadores
- [ ] Efecto de poción de invisibilidad (Poción Negra, ObjType 645)
- [ ] Flags de invisibilidad en jugador
- [ ] Broadcast de estado invisible a otros jugadores
- [ ] NPCs no pueden detectar jugadores invisibles (opcional)

**Nota:** El item de poción de invisibilidad existe (ID 645), pero el efecto no está implementado.

**Archivos a crear:**
- `src/services/invisibility_service.py`
- `src/network/msg_invisibility.py`

---

## 🟡 Sistemas Parcialmente Implementados

### 1. Hechizos Avanzados
- **VB6 Reference:** `modHechizos.bas` (97KB - archivo grande)
- **Estado:** ✅ Básico (11 hechizos básicos)
- **Prioridad:** 🔴 Alta
- **Versión Planeada:** v0.11.0-alpha

**Falta implementar:**
- [ ] Sistema de escuelas de magia (Fuego, Agua, Tierra, Aire, Luz, Oscuridad)
- [ ] Hechizos de área (AOE)
- [ ] Hechizos con duración y efectos over time (DoT)
- [ ] Sistema de runas y componentes
- [ ] Hechizos de invocación
- [ ] Protecciones y barreras mágicas
- [ ] Libros de hechizos equipables
- [ ] Hechizos de curación sobre otros jugadores
- [ ] Hechizos de buff/debuff

**Total de hechizos en VB6:** ~100+ (solo 11 básicos importados)

---

### 2. Sistema de Banco Avanzado
- **VB6 Reference:** `modBanco.bas` (12KB)
- **Estado:** ✅ Básico (depósitos/extracciones)
- **Prioridad:** 🟡 Media
- **Versión Planeada:** v0.14.0-alpha

**Falta implementar:**
- [ ] Sistema de préstamos bancarios
- [ ] Intereses sobre depósitos
- [ ] Transferencias entre jugadores
- [ ] Cajas de seguridad privadas
- [ ] Historial de transacciones
- [ ] Límites de depósito por nivel

---

### 3. Sistema de Estadísticas Avanzado
- **VB6 Reference:** `Statistics.bas` (15KB), `clsEstadisticasIPC.cls`
- **Estado:** ✅ Básico implementado
- **Prioridad:** 🟢 Baja
- **Versión Planeada:** v0.17.0-alpha

**Falta implementar:**
- [ ] Estadísticas globales del servidor
- [ ] Rankings (PKs, nivel, riqueza)
- [ ] Estadísticas por facción
- [ ] Historial de eventos importantes
- [ ] Sistema de logros y trofeos
- [ ] API de estadísticas
- [ ] IPC (Inter-Process Communication) para estadísticas

---

### 4. Sistema de Historial/Logs Avanzado
- **VB6 Reference:** `History.bas` (5KB)
- **Estado:** ✅ Básico (logging estándar)
- **Prioridad:** 🟢 Baja
- **Versión Planeada:** v0.11.0-alpha

**Falta implementar:**
- [ ] Historial de acciones del jugador
- [ ] Logs de combate detallados
- [ ] Sistema de búsqueda en historial
- [ ] Exportación de logs
- [ ] Retención automática por tiempo
- [ ] Logs estructurados en JSON

---

### 5. Sistema de Clanes - Features Avanzadas
- **VB6 Reference:** `modGuilds.bas`, `clsClan.cls`
- **Estado:** ✅ Core completo (v0.9.0-alpha)
- **Prioridad:** 🟡 Media

**Falta implementar:**
- [ ] Almacén/depósito del clan
- [ ] Alianzas entre clanes
- [ ] Guerras de clanes
- [ ] Edificio del clan con NPCs
- [ ] Clanes Pretorianos (sistema especial)
- [ ] Sistema de fortalezas pretorianas

**Nota:** Los modelos tienen métodos para alianzas y guerras, pero falta la UI/comandos.

---

## 📊 Tabla Comparativa Resumida

| Sistema | VB6 | Python | Estado | Prioridad |
|---------|-----|--------|--------|-----------|
| Autenticación | ✅ | ✅ | Completo | - |
| Personajes | ✅ | ✅ | Completo | - |
| Mapas | ✅ | ✅ | Completo | - |
| NPCs | ✅ | ✅ | Completo | - |
| Combate | ✅ | ✅ | Completo | - |
| Inventario | ✅ | ✅ | Completo | - |
| Comercio | ✅ | ✅ | Completo | - |
| Banco | ✅ | 🟡 | Básico | Media |
| Trabajo | ✅ | ✅ | Completo | - |
| Hechizos Básicos | ✅ | ✅ | Completo | - |
| Hechizos Avanzados | ✅ | ❌ | No | Alta |
| Partys | ✅ | ✅ | Completo | - |
| Clanes (Core) | ✅ | ✅ | Completo | - |
| Clanes (Avanzado) | ✅ | ❌ | No | Media |
| Facciones | ✅ | ❌ | No | Media |
| Foro | ✅ | ❌ | No | Baja |
| Quests | ✅ | ❌ | No | Media |
| Anti-cheat | ✅ | ❌ | No | Media |
| Sonido | ✅ | ❌ | No | Baja |
| Seguridad IP | ✅ | ❌ | No | Baja |
| Invisibilidad | ✅ | ❌ | No | Media |
| Estadísticas | ✅ | 🟡 | Básico | Baja |
| Historial | ✅ | 🟡 | Básico | Baja |

**Leyenda:**
- ✅ = Implementado completamente
- 🟡 = Implementado parcialmente
- ❌ = No implementado

---

## 🎯 Priorización Recomendada

### 🔴 Alta Prioridad (Gameplay Core)
1. **Hechizos Avanzados** (v0.11.0) - Sistema de magia completo
2. **Invisibilidad** - Feature básica de gameplay

### 🟡 Media Prioridad (Contenido End-game)
3. **Sistema de Facciones** (v0.12.0) - Guerras y PvP
4. **Sistema de Quests** (v0.13.0) - Contenido narrativo
5. **Banco Avanzado** (v0.14.0) - Sistema económico
6. **Anti-cheat** (v0.16.0) - Seguridad y estabilidad
7. **Clanes Avanzados** - Features sociales

### 🟢 Baja Prioridad (Polish y Extras)
8. **Foro/Noticias** (v0.19.0) - Social
9. **Sonido** (v0.18.0) - Inmersión
10. **Seguridad IP** (v0.20.0) - Administración
11. **Estadísticas Avanzadas** (v0.17.0) - Análisis

---

## 📝 Notas Importantes

1. **Compatibilidad:** Todos los sistemas deben mantener compatibilidad con el protocolo VB6 existente.

2. **Tests:** Cada nuevo sistema debe tener tests completos antes de merge.

3. **Documentación:** Documentar cada sistema en `docs/` antes de completar.

4. **Performance:** Optimizar para 1000+ jugadores concurrentes.

5. **Seguridad:** Validar todos los inputs del cliente.

---

## 🔗 Referencias

- **Servidor VB6:** `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Codigo/`
- **Roadmap de Versiones:** `todo/ROADMAP_VERSIONES.md`
- **Estado Actual:** `ESTADO_ACTUAL.md`
- **TODOs:** `todo/TODO_CARACTERISTICAS_VB6.md`

---

**Última actualización:** 2025-01-31  
**Autor:** Análisis comparativo VB6 vs Python Server

