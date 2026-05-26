# Análisis Cruzado: Cliente Godot + Servidor VB6 → Mejoras para PyAO Server

**Fecha:** 2026-02-08  
**Método:** Análisis automatizado del cliente Godot, servidor VB6 y servidor Python  
**Objetivo:** Identificar features faltantes, packets sin implementar y oportunidades de mejora

---

## Resumen Ejecutivo

- **Packets implementados:** 40 de 130 (30.8%)
- **Spell effects:** 20 de ~100+ del VB6
- **Sistemas completos:** Combate básico, inventario, comercio, banco, party, clan, trabajo
- **Sistemas faltantes:** Level up completo, PvP, facciones, crafting avanzado, mascotas, quests

---

## Fase 1 — Quick Wins (alto impacto, bajo esfuerzo)

### 1.1 Packets de status effects que el cliente ya maneja

El servidor ya tiene los status effects implementados (server-side), pero **no envía los packets al cliente**. El cliente tiene handlers listos para:

| ServerPacketID | Nombre | Formato | Acción |
|----------------|--------|---------|--------|
| 49 | `Blind` | (sin datos) | Activa efecto visual de ceguera |
| 50 | `BlindNoMore` | (sin datos) | Desactiva ceguera |
| 51 | `Dumb` | (sin datos) | Activa efecto de estupidez (no puede castear) |
| 52 | `DumbNoMore` | (sin datos) | Desactiva estupidez |
| 61 | `SetInvisible` | charIndex(u16) + invisible(u8) | Marca personaje invisible |
| 75 | `ParalizeOK` | (sin datos) | Confirma parálisis |

**Archivos a modificar:**
- `src/network/packet_id.py` — Agregar IDs faltantes
- `src/network/msg_player_stats.py` — Build functions para cada packet
- `src/messaging/senders/message_player_stats_sender.py` — Métodos send_*
- `src/messaging/message_sender.py` — Delegación en facade
- Los spell effects que ya aplican estos estados deben llamar al sender correspondiente

### 1.2 Packets de toggle visual

| ServerPacketID | Nombre | Formato |
|----------------|--------|---------|
| 47 | `RestOK` | (sin datos) |
| 61 | `MeditateToggle` | (sin datos) |
| 5 | `NavigateToggle` | (sin datos) |

**Estado actual:** El servidor cambia el estado en Redis pero no notifica al cliente → el jugador medita pero no ve el FX de meditación.

### 1.3 YELL y WHISPER

El cliente envía `YELL` (4) y `WHISPER` (5) pero el servidor solo procesa `TALK` (3).

- `YELL`: Chat con rango ampliado (alcanza más tiles)
- `WHISPER`: Chat privado a un jugador específico (formato: `/USUARIO mensaje`)

**Esfuerzo:** Variantes simples del handler de `TALK` existente.

### 1.4 UpdateTagAndStatus

| ServerPacketID | Nombre | Formato |
|----------------|--------|---------|
| 82 | `UpdateTagAndStatus` | charIndex(u16) + nickColor(u8) + userTag(unicode) |

Permite colorear el nick del jugador (criminal=rojo, ciudadano=azul, newbie=verde). Esencial para PvP.

### 1.5 MOVE_ITEM

El cliente envía `MoveItem` (113) para reordenar slots del inventario. No implementado en el servidor.

---

## Fase 2 — Sistema de Progresión (alto impacto, esfuerzo medio)

### 2.1 Level Up completo con fórmulas VB6

**Referencia VB6:** `Modulo_UsUaRiOs.bas` → `CheckUserLevel`

#### Fórmula de ELU (experiencia para siguiente nivel)

```
Nivel < 15:  ELU = ELU * 1.4
Nivel < 21:  ELU = ELU * 1.35
Nivel < 26:  ELU = ELU * 1.3
Nivel < 35:  ELU = ELU * 1.2
Nivel < 40:  ELU = ELU * 1.3
Nivel >= 40: ELU = ELU * 1.375
```

#### Recompensas por nivel (por clase)

**Skill Points:**
- Nivel 1: 10 puntos
- Nivel 2+: 5 puntos por nivel

**HP por nivel:**
```
Promedio = ModVida(clase) - (21 - Constitucion) * 0.5
Variación: ±2 HP (entero) o ±1.5 HP (semi-entero)
```

**Mana por nivel (según clase):**
- Mago: `+2.8 * Inteligencia`
- Clérigo/Druida/Bardo: `+2 * Inteligencia`
- Paladín/Asesino: `+Inteligencia`
- Bandido: `+Inteligencia / 3 * 2`
- Guerrero/Trabajador: 0

**Stamina por nivel:**
- Trabajador: +40
- Ladrón/Bandido: +18
- Clérigo/Druida/Bardo: +15
- Mago: +14
- Default: +15

**Hit por nivel:**
- Guerrero/Cazador: +3 (nivel 1-35), +2 (nivel 36+)
- Paladín/Asesino/Bandido: +3 (nivel 1-35), +1 (nivel 36+)
- Ladrón: +2
- Mago: +1

**Packet LevelUp:**
```
ServerPacketID.LevelUp (58) = skillPoints(u16)
```

**Packet MODIFY_SKILLS (38):**
El cliente envía la distribución de skill points. No implementado en el servidor.

### 2.2 MiniStats y Fame

**MiniStats (57):**
```
CiudadanosMatados(s32) + CriminalesMatados(s32) + UsuariosMatados(u16) +
NpcsMatados(u16) + Clase(u8) + PenaCarcel(s32)
```

**Fame (56):**
```
7 x s32: AsesinoRep, BandidoRep, BurguesRep, LadronesRep, NobleRep, PlebeRep, Promedio
```

### 2.3 Fórmula de experiencia por combate

**Referencia VB6:** `SistemaCombate.bas` → `CalcularDarExp`

```
ExpaDar = ElDaño * (NPC.GiveEXP / NPC.Stats.MaxHp)
```

La experiencia es proporcional al daño infligido respecto al HP máximo del NPC.

---

## Fase 3 — Combate fiel al VB6 (alto impacto, esfuerzo alto)

### 3.1 Fórmulas de combate

**Referencia VB6:** `SistemaCombate.bas`

#### Hit/Miss

```vb
PoderAtaqueArma = HitMax * ModDañoArmas(Clase) / 100
PoderEvasion = 100 + Agilidad * ModEvasion(Clase) / 100
PoderEvasionEscudo = escudo.MinDef + RandomNumber(1, escudo.MaxDef - escudo.MinDef + 1)
```

#### Modificadores por clase (de Balance.dat)

| Clase | Evasion | AtqArmas | AtqProy | AtqWrest | DañoArmas | DañoProy | DañoWrest | Escudo |
|-------|---------|----------|---------|----------|-----------|----------|-----------|--------|
| (varía) | 0-200 | 0-200 | 0-200 | 0-200 | 0-200 | 0-200 | 0-200 | 0-200 |

#### Ataques especiales

- **Apuñalar (Stab):** Skill de ladrón, daño bonus basado en nivel de skill
- **Acuchillar (Slash):** 20% chance, +20% daño extra (`PROB_ACUCHILLAR = 20`, `DAÑO_ACUCHILLAR = 0.2`)
- **Golpe Crítico:** Bandidos con Espada Vikinga
- **Proyectiles:** Sistema separado con su propio modificador

#### Defensa mágica

Los hechizos de daño consideran defensa mágica de:
- Cascos con resistencia mágica
- Anillos con resistencia mágica
- Fórmula: `daño = daño_base - defensa_magica`

### 3.2 PvP

**Referencia VB6:** `SistemaCombate.bas` → `UsuarioAtacaUsuario`

- `UserDañoUser` — Fórmula de daño jugador vs jugador
- Recompensas: `VictimLevel * 2` experiencia
- Cambios de reputación según alineamiento víctima/atacante
- Sistema criminal: atacar ciudadanos te hace criminal
- Seguro anti-PvP (SafeToggle): previene ataques accidentales

**Packet SafeToggle (10):** El cliente lo envía pero el server no lo procesa.

### 3.3 Sistema de muerte completo

**Referencia VB6:** `Modulo_UsUaRiOs.bas` → `UserDie`

Al morir:
1. HP y Stamina = 0
2. `flags.Muerto = 1`
3. Limpiar todos los status effects (veneno, parálisis, ceguera, estupidez)
4. Remover invisibilidad/sigilo
5. Resetear contadores de trabajo
6. Desequipar todo el equipo
7. Cambiar apariencia a cuerpo muerto (`iCuerpoMuerto`, `iCabezaMuerto`)
8. Matar todas las mascotas/invocaciones
9. Resetear mimetismo y pociones de atributos
10. Limpiar efectos FX

**Drop de items:**
- Todos los items caen al piso (excepto newbies nivel < 12)
- En arenas (`TriggerZonaPelea`) no se pierden items
- Seguro de resurrección (`ResuscitationSafe`) previene pérdida

**Penalidad de party:** `-10 * Level * PartyMembers` experiencia

**Teletransporte:** Si el mapa tiene `OnDeathGoTo`, el jugador se teletransporta al morir

**Resurrección (`RevivirUsuario`):**
- HP = Constitución (o MaxHP si es menor)
- Restaurar apariencia (cuerpo desnudo o barco)
- Actualizar stats y enviar al cliente

---

## Fase 4 — Sistemas Avanzados

### 4.1 Crafting completo

**Referencia VB6:** `Trabajo.bas`

- **Herrería:** `HerreroConstruirItem` — Fabricar armas/armaduras con lingotes
- **Carpintería:** `CarpinteroConstruirItem` — Fabricar con madera
- **Fundición:** `FundirArmas` — Desmontar armas para recuperar materiales
- **Fundición de minerales:** `FundirMineral` — Convertir minerales en lingotes
- **Upgrade:** `DoUpgrade` — Mejorar items (85% recuperación de materiales)

**Packets involucrados:**
- Cliente envía: `CRAFT_BLACKSMITH` (31), `CRAFT_CARPENTER` (32), `INIT_CRAFTING` (107), `ITEM_UPGRADE` (105)
- Servidor envía: `ShowBlacksmithForm` (6), `ShowCarpenterForm` (7), `BlacksmithWeapons` (44), `BlacksmithArmors` (45), `CarpenterObjects` (46)

**Formato de BlacksmithWeapons/Armors:**
```
count(u16) + [name(unicode) + grh_index(u16) + lin_h(u16) + lin_p(u16) +
              lin_o(u16) + obj_index(u16) + upgrade(u16)] * count
```

**Formato de CarpenterObjects:**
```
count(u16) + [name(unicode) + grh_index(u16) + madera(u16) +
              madera_elfica(u16) + obj_index(u16) + upgrade(u16)] * count
```

### 4.2 Mascotas (Taming)

**Referencia VB6:** `Trabajo.bas` → `DoDomar`

- Skill de domar: check contra nivel del NPC
- Máximo 3 mascotas (`MAXMASCOTAS = 3`)
- Comandos: `PET_STAND`, `PET_FOLLOW`, `RELEASE_PET`
- Las mascotas siguen al dueño (`SigueAmo` AI)
- Mascotas atacan al agresor del dueño (`SeguirAgresor` AI)
- Las mascotas mueren si el dueño muere

### 4.3 Skills faltantes

De los 20 skills del cliente, varios no están implementados en el server:

| Skill | Nombre | Estado |
|-------|--------|--------|
| 2 | Robar | No implementado |
| 3 | Tácticas | No implementado |
| 6 | Apuñalar | No implementado |
| 7 | Ocultarse | No implementado |
| 10 | Comerciar | No implementado |
| 11 | Defensa con escudo | No implementado |
| 17 | Domar | No implementado |
| 18 | Proyectiles | No implementado |
| 19 | Wrestling | No implementado |
| 20 | Navegación | No implementado |

### 4.4 Sistema de facciones

**Referencia VB6:** `ModFacciones.bas`

- Facciones: Real (Ejército), Caos (Legión Oscura)
- Enlistarse: `ENLIST` packet
- Dejar facción: `LEAVE_FACTION` packet
- Recompensas por rango: configurables en `Balance.dat`
- Restricciones: nivel 25+ expulsado de clan alineado al subir

### 4.5 Comercio entre jugadores (Player Trade)

**Estado actual:** Tasks existen (`TaskUserCommerceOk`, etc.) pero la lógica está parcialmente implementada.

**Referencia VB6:** `mdlCOmercioConUsuario.bas`

**Packets:**
- `UserCommerceInit` (10) — Servidor inicia ventana de trade
- `UserCommerceEnd` (11) — Cerrar ventana
- `UserCommerceOffer` (48) — Agregar item/oro a oferta
- `UserCommerceConfirm` (19) — Confirmar oferta
- `UserCommerceOk` (22) — Aceptar trade
- `UserCommerceReject` (23) — Rechazar trade

---

## Constantes importantes del VB6

```
MAXEXP = 99999999        # Experiencia máxima
MAXORO = 90000000        # Oro máximo
MAXREP = 6000000         # Reputación máxima
MAXATRIBUTOS = 40        # Atributos máximos
MINATRIBUTOS = 6         # Atributos mínimos
MAXSKILLPOINTS = 100     # Skill points máximos
MAXMASCOTAS = 3          # Mascotas máximas
LimiteNewbie = 12        # Nivel límite de newbie
STAT_MAXHP = 30000       # HP máximo
PROB_ACUCHILLAR = 20     # Probabilidad de slash (20%)
DAÑO_ACUCHILLAR = 0.2    # Daño extra de slash (20%)
PORCENTAJE_MATERIALES_UPGRADE = 0.85  # Recuperación de materiales (85%)
```

**Costos de stamina por trabajo:**
```
EsfuerzoTalarGeneral = 4      EsfuerzoTalarLeñador = 2
EsfuerzoPescarGeneral = 3     EsfuerzoPescarPescador = 1
EsfuerzoExcavarGeneral = 5    EsfuerzoExcavarMinero = 2
```

---

## Skills del cliente (referencia completa)

```gdscript
enum Skill {
    Magia = 1,          Robar = 2,         Tacticas = 3,
    Armas = 4,          Meditar = 5,        Apunalar = 6,
    Ocultarse = 7,      Supervivencia = 8,  Talar = 9,
    Comerciar = 10,     Defensa = 11,       Pesca = 12,
    Mineria = 13,       Carpinteria = 14,   Herreria = 15,
    Liderazgo = 16,     Domar = 17,         Proyectiles = 18,
    Wrestling = 19,     Navegacion = 20
}
```

---

## Prioridad de implementación recomendada

### Inmediato (1-2 días cada uno)
1. ✅ Enviar packets de Blind/Dumb/Invisible al cliente
2. ✅ YELL y WHISPER
3. ✅ MeditateToggle / RestOK / NavigateToggle
4. ✅ UpdateTagAndStatus (colores de nick)
5. ✅ MOVE_ITEM

### Corto plazo (1-2 semanas cada uno)
6. Level up completo con fórmulas VB6
7. LevelUp packet + MODIFY_SKILLS
8. MiniStats y Fame packets
9. MultiMessage system

### Mediano plazo (2-3 semanas cada uno)
10. Fórmulas de combate VB6 reales
11. PvP con sistema criminal/ciudadano
12. Sistema de muerte completo
13. Crafting (herrería + carpintería)

### Largo plazo (3-4 semanas cada uno)
14. Mascotas (domar + comandos)
15. Skills faltantes (robar, ocultarse, apuñalar, etc.)
16. Sistema de facciones
17. Comercio entre jugadores (completar)

---

**Referencia VB6:** `clientes/ArgentumOnline0.13.3-Cliente-Servidor/server/`  
**Referencia Godot:** `clientes/ArgentumOnlineGodot/`  
**Generado por:** Análisis automatizado cruzando 3 codebases
