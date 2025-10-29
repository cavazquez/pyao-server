# TODO - PyAO Server

## 📋 Características Faltantes del Servidor VB6

Análisis comparativo entre el servidor VB6 original y nuestro servidor Python basado en los archivos fuente del servidor ArgentumOnline 0.13.3.

---

## 🏰 **Sistema de Clanes/Guilds** - v0.7.0
**Estado**: ❌ No implementado  
**Prioridad**: 🔴 Alta  
**VB6 Reference**: `modGuilds.bas` (71KB), `clsClan.cls` (29KB)

### Funcionalidades a implementar:
- [ ] Creación de clanes
- [ ] Gestión de miembros (invitar, expulsar, promover)
- [ ] Almacén/depósito del clan
- [ ] Chat interno del clan
- [ ] Alianzas entre clanes
- [ ] Guerras de clanes
- [ ] Edificio del clan con NPCs
- [ ] Sistema de rangos jerárquicos

### Archivos a crear:
- `src/models/clan.py`
- `src/services/clan_service.py`
- `src/repositories/clan_repository.py`
- `src/tasks/clan/`
- `data/clans.toml`

---

## 👥 **Sistema de Partys/Grupos** - v0.7.0
**Estado**: ❌ No implementado  
**Prioridad**: 🔴 Alta  
**VB6 Reference**: `clsParty.cls` (19KB), `mdParty.bas` (19KB)

### Funcionalidades a implementar:
- [ ] Creación de parties (2-6 miembros)
- [ ] Sistema de líder de party
- [ ] Exp compartida entre miembros
- [ ] Chat de party
- [ ] Invitar/Expulsar miembros
- [ ] Disolver party automática si líder se desconecta
- [ ] Sistema de loot compartido

### Archivos a crear:
- `src/models/party.py`
- `src/services/party_service.py`
- `src/repositories/party_repository.py`
- `src/tasks/party/`

---

## ⚔️ **Sistema de Facciones** - v0.8.0
**Estado**: ❌ No implementado  
**Prioridad**: 🟡 Media  
**VB6 Reference**: `ModFacciones.bas` (33KB), `praetorians.bas` (39KB)

### Funcionalidades a implementar:
- [ ] Sistema de facciones (Legión, Caos, Real, Neutral)
- [ ] Guerras automáticas entre facciones
- [ ] Zonas controladas por facciones
- [ ] Beneficios por pertenecer a facción
- [ ] Sistema de prestigio de facción
- [ ] NPCs de facciones con comportamiento diferenciado

### Archivos a crear:
- `src/models/faction.py`
- `src/services/faction_service.py`
- `src/repositories/faction_repository.py`
- `data/factions.toml`

---

## 🎭 **Sistema de Hechizos Avanzado** - v0.8.0
**Estado**: 🟡 Parcialmente implementado  
**Prioridad**: 🔴 Alta  
**VB6 Reference**: `modHechizos.bas` (97KB)

### Funcionalidades a implementar:
- [ ] Sistema de escuelas de magia (Fuego, Agua, Tierra, Aire, Luz, Oscuridad)
- [ ] Hechizos de área (AOE)
- [ ] Hechizos con duración y efectos over time
- [ ] Sistema de runas y componentes
- [ ] Hechizos de invocación
- [ ] Protecciones y barreras mágicas
- [ ] Libros de hechizos equipables

### Archivos a modificar:
- `src/models/spell.py` - Expandir funcionalidad
- `src/services/spell_service.py` - Nuevos sistemas
- `data/spells.toml` - Más hechizos

---

## 🏦 **Sistema de Banco Avanzado** - v0.9.0
**Estado**: 🟡 Básico implementado  
**Prioridad**: 🟡 Media  
**VB6 Reference**: `modBanco.bas` (12KB)

### Funcionalidades a implementar:
- [ ] Sistema de préstamos bancarios
- [ ] Intereses sobre depósitos
- [ ] Transferencias entre jugadores
- [ ] Cajas de seguridad privadas
- [ ] Historial de transacciones
- [ ] Límites de depósito por nivel

### Archivos a modificar:
- `src/services/banking_service.py` - Expandir funcionalidad

---

## 📰 **Sistema de Foro/Noticias** - v0.9.0
**Estado**: ❌ No implementado  
**Prioridad**: 🟢 Baja  
**VB6 Reference**: `modForum.bas` (14KB)

### Funcionalidades a implementar:
- [ ] Foro interno del servidor
- [ ] Sistema de noticias y anuncios
- [ ] Secciones por tema (Comercio, Clanes, Ayuda)
- [ ] Sistema de moderación
- [ ] Búsqueda de posts
- [ ] Posts fijos (pinned)

### Archivos a crear:
- `src/models/forum_post.py`
- `src/services/forum_service.py`
- `src/repositories/forum_repository.py`

---

## 🛡️ **Sistema de Centinelas/Anti-cheat** - v0.10.0
**Estado**: ❌ No implementado  
**Prioridad**: 🟡 Media  
**VB6 Reference**: `modCentinela.bas` (23KB), `clsAntiMassClon.cls`

### Funcionalidades a implementar:
- [ ] Detección de speed hack
- [ ] Anti-mass cloning (múltiples cuentas)
- [ ] Detección de movimientos inválidos
- [ ] Sistema de reportes automáticos
- [ ] Baneo temporal/permanente
- [ ] Log de actividades sospechosas

### Archivos a crear:
- `src/services/centinel_service.py`
- `src/services/anti_cheat_service.py`

---

## 📊 **Sistema de Estadísticas Avanzado** - v0.10.0
**Estado**: 🟡 Básico implementado  
**Prioridad**: 🟢 Baja  
**VB6 Reference**: `Statistics.bas` (15KB), `clsEstadisticasIPC.cls`

### Funcionalidades a implementar:
- [ ] Estadísticas globales del servidor
- [ ] Rankings (PKs, nivel, riqueza)
- [ ] Estadísticas por facción
- [ ] Historial de eventos importantes
- [ ] Sistema de logros y trofeos
- [ ] API de estadísticas

### Archivos a modificar:
- `src/services/statistics_service.py` - Expandir

---

## 🎵 **Sistema de Sonido por Mapa** - v0.11.0
**Estado**: ❌ No implementado  
**Prioridad**: 🟢 Baja  
**VB6 Reference**: `clsMapSoundManager.cls`

### Funcionalidades a implementar:
- [ ] Música ambiental por mapa
- [ ] Efectos de sonido por zona
- [ ] Sonidos de combate
- [ ] Sistema de ambientes dinámicos
- [ ] Configuración de sonido por usuario

### Archivos a crear:
- `src/services/sound_service.py`
- `data/map_sounds.toml`

---

## 📝 **Sistema de Historial/Logs Avanzado** - v0.11.0
**Estado**: 🟡 Básico implementado  
**Prioridad**: 🟢 Baja  
**VB6 Reference**: `History.bas` (5KB)

### Funcionalidades a implementar:
- [ ] Historial de acciones del jugador
- [ ] Logs de combate detallados
- [ ] Sistema de búsqueda en historial
- [ ] Exportación de logs
- [ ] Retención automática por tiempo

### Archivos a modificar:
- `src/utils/logger.py` - Expandir funcionalidad

---

## 🔐 **Sistema de Seguridad IP** - v0.12.0
**Estado**: ❌ No implementado  
**Prioridad**: 🟢 Baja  
**VB6 Reference**: `SecurityIp.bas` (12KB)

### Funcionalidades a implementar:
- [ ] Lista blanca/negra de IPs
- [ ] Límite de conexiones por IP
- [ ] Detección de ataques DDoS básicos
- [ ] Sistema de bans por IP/rango
- [ ] Logs de conexiones por IP

### Archivos a crear:
- `src/services/ip_security_service.py`
- `data/ip_security.toml`

---

## 📅 **Roadmap de Versiones**

### v0.7.0 - Sistema Social
- ✅ Clanes/Guilds
- ✅ Partys/Grupos
- ✅ Chat mejorado

### v0.8.0 - Expansión de Combate
- ✅ Facciones
- ✅ Hechizos avanzados
- ✅ Guerras automáticas

### v0.9.0 - Sistema Económico
- ✅ Banco avanzado
- ✅ Foro/Noticias
- ✅ Mercado global

### v0.10.0 - Seguridad y Estadísticas
- ✅ Anti-cheat/Centinelas
- ✅ Estadísticas avanzadas
- ✅ Sistema de logros

### v0.11.0 - Multimedia
- ✅ Sistema de sonido
- ✅ Historial avanzado
- ✅ Ambientes dinámicos

### v0.12.0 - Seguridad Avanzada
- ✅ Seguridad IP
- ✅ Protección DDoS
- ✅ Logs de seguridad

---

## 🎯 **Criterios de Priorización**

### 🔴 Alta Prioridad
- Impacto directo en gameplay
- Requerido para contenido end-game
- Mejora significativa de experiencia social

### 🟡 Media Prioridad
- Funcionalidades importantes pero no críticas
- Mejoras de sistemas existentes
- Contenido para jugadores avanzados

### 🟢 Baja Prioridad
- Funcionalidades opcionales
- Mejoras cosméticas/de calidad
- Herramientas administrativas

---

## 📝 **Notas de Implementación**

1. **Mantener compatibilidad** con protocolo de cliente existente
2. **Tests obligatorios** para cada nueva funcionalidad
3. **Documentación completa** antes de merge
4. **Performance first** - optimizar para 1000+ jugadores concurrentes
5. **Seguridad** - validar todos los inputs del cliente
6. **Escalabilidad** - diseño para futuras expansiones

---

## 🔗 **Referencias**

- **Servidor VB6**: `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/Codigo/`
- **Cliente Godot**: `clientes/ArgentumOnlineGodot/`
- **Documentación existente**: `docs/`

---

*Última actualización: 2025-01-29*  
*Versión actual: v0.6.0-alpha*
