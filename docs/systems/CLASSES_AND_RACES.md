# Clases y Razas

Este documento describe las **razas** y **clases de personaje** disponibles en PyAO Server y cómo se relacionan los datos entre el cliente Godot, el servidor Python y los archivos TOML extraídos del cliente VB6 original.

## Razas

Las razas se cargan desde `data/classes_balance.toml` en la sección `[racial_modifiers]` y son utilizadas por `BalanceService` (`src/services/game/balance_service.py`).

Razas actuales:

- **Humano** – STR +1, AGI +1, CON +2
- **Elfo** – STR -1, AGI +3, INT +2, CHA +2, CON +1
- **Drow** – STR +2, AGI +3, INT +2, CHA -3
- **Enano** – STR +3, INT -2, CHA -2, CON +3
- **Gnomo** – STR -2, AGI +3, INT +4, CHA +1

Estos modificadores se aplican sobre los atributos base al crear el personaje.

## Clases

Las clases se cargan desde `data/classes_balance.toml` en la sección `[class_modifiers]`. Cada clase define modificadores de combate que luego usa `BalanceService`:

- `evasion`
- `ataquearmas`
- `ataqueproyectiles`
- `ataquewrestling`
- `damagearmas`
- `damageproyectiles`
- `escudo`
- `vida`

Clases actuales:

- **Guerrero** – melee físico, buena vida y escudo.
- **Cazador** – daño a distancia, enfocado en proyectiles.
- **Paladin** – tanque híbrido, buena defensa.
- **Bandido** – melee con wrestling alto.
- **Asesino** – muy evasivo, menos vida.
- **Pirata** – ágil, con buena evasión.
- **Ladron** – evasivo, vida algo mayor.
- **Clerigo** – híbrido físico/mágico con buen escudo.
- **Bardo** – soporte, vida baja.
- **Mago** – caster puro, vida muy baja.
- **Druida** – híbrido mágico con algo más de defensa.
- **Trabajador** – clase orientada a sistema de trabajo (pesca/tala/minería).

`BalanceService` expone:

- `get_available_races()` / `get_available_classes()` – listas válidas.
- `get_racial_modifier(race, stat)` – modificadores raciales.
- `get_class_modifier(class, modifier)` – modificadores de clase.
- `calculate_damage`, `calculate_evasion`, `calculate_max_health`.

## IDs de Clase en el Cliente Godot

El cliente Godot maneja **IDs numéricos** de clase y los muestra en UI. Un ejemplo de mapping puede verse en `clientes/ArgentumOnlineGodot/ui/hub/stats_window.gd`:

```gdscript
const CLASS_NAMES := {
    0: "-",
    1: "Guerrero",
    2: "Mago",
    3: "Clérigo",
    4: "Asesino",
    5: "Bardo",
    6: "Druida",
    7: "Paladín",
    8: "Cazador",
}
```

El servidor, en cambio, trabaja con **nombres de clase** tal como figuran en `classes_balance.toml` (por ejemplo `"Guerrero"`, `"Mago"`, `"Clerigo"`). Es importante mantener consistente el mapeo **ID cliente → nombre de clase en servidor**.

En el packet de creación de cuenta (`TaskAccount`), el cliente envía un byte `job` que representa el ID de clase. El servidor lo guarda como `char_job` (en Redis) y puede luego traducirlo al nombre de clase para aplicar los modificadores de `BalanceService`.

## Uso Práctico

- Si querés **ajustar el balance** de una clase, modificá los valores correspondientes en `data/classes_balance.toml`.
- Si agregás una clase nueva, recordá:
  - Agregarla en `classes_balance.toml`.
  - Ajustar el cliente Godot (`Consts.ClassNames`, `CLASS_NAMES`, etc.).
  - Añadir lógica de mapping ID ↔ nombre en el servidor si es necesario.

Este documento sirve como referencia rápida para entender qué razas y clases existen, cómo se balancean y cómo se conectan los datos entre cliente y servidor.
