# Mapa de Migración MessageSender → Componentes

## ConsoleMessageSender
- send_console_msg → console.send_console_msg
- send_multiline_console_msg → console.send_multiline_console_msg
- send_error_msg → console.send_error_msg
- send_update_gold → console.send_update_gold (mensaje de oro ganado)

## AudioMessageSender
- send_play_midi → audio.send_play_midi
- send_play_wave → audio.send_play_wave
- play_sound_login → audio.play_sound_login
- play_sound_click → audio.play_sound_click
- play_sound_level_up → audio.play_sound_level_up
- play_sound_error → audio.play_sound_error
- play_sound_gold_pickup → audio.play_sound_gold_pickup
- play_sound_item_pickup → audio.play_sound_item_pickup
- play_music_main_theme → audio.play_music_main_theme
- play_music_battle → audio.play_music_battle
- play_music_town → audio.play_music_town
- play_music_dungeon → audio.play_music_dungeon

## VisualEffectsMessageSender
- send_create_fx → visual_effects.send_create_fx
- send_create_fx_at_position → visual_effects.send_create_fx_at_position
- play_effect_spawn → visual_effects.play_effect_spawn
- play_effect_heal → visual_effects.play_effect_heal
- play_effect_meditation → visual_effects.play_effect_meditation
- play_effect_explosion → visual_effects.play_effect_explosion

## PlayerStatsMessageSender
- send_update_hp → player_stats.send_update_hp
- send_update_mana → player_stats.send_update_mana
- send_update_sta → player_stats.send_update_sta
- send_update_exp → player_stats.send_update_exp
- send_update_hunger_and_thirst → player_stats.send_update_hunger_and_thirst
- send_update_user_stats → player_stats.send_update_user_stats
- send_logged → player_stats.send_logged (confirma login exitoso)

## CharacterMessageSender
- send_character_create → character.send_character_create
- send_character_change → character.send_character_change
- send_character_remove → character.send_character_remove
- send_character_move → character.send_character_move
- send_dice_roll → character.send_dice_roll (genera atributos)
- send_attributes → character.send_attributes (envía atributos)
- send_user_char_index_in_server → character.send_user_char_index_in_server

## InventoryMessageSender
- send_change_inventory_slot → inventory.send_change_inventory_slot
- send_change_bank_slot → inventory.send_change_bank_slot
- send_change_npc_inventory_slot → inventory.send_change_npc_inventory_slot
- send_bank_init_empty → inventory.send_bank_init_empty
- send_bank_end → inventory.send_bank_end
- send_commerce_init → inventory.send_commerce_init (abrir comercio con items)
- send_commerce_init_empty → inventory.send_commerce_init_empty
- send_commerce_end → inventory.send_commerce_end
- send_change_spell_slot → inventory.send_change_spell_slot
- send_meditate_toggle → inventory.send_meditate_toggle

## MapMessageSender
- send_change_map → map.send_change_map
- send_pos_update → map.send_pos_update
- send_object_create → map.send_object_create
- send_object_delete → map.send_object_delete
- send_block_position → map.send_block_position

## Métodos Especiales (asignar a componentes)
- send_dice_roll → **CharacterMessageSender** (genera atributos de personaje)
- send_attributes → **CharacterMessageSender** (envía atributos del personaje)
- send_logged → **PlayerStatsMessageSender** (confirma login y estado inicial)
- send_user_char_index_in_server → **CharacterMessageSender** (índice del personaje)
- send_commerce_init → **InventoryMessageSender** (comercio es parte de inventario)
- send_update_gold → **ConsoleMessageSender** (es solo un mensaje de consola)

## Estrategia de Migración (Incremental)

### Proceso por Componente

1. **Crear MessageSenderComponents** (facade vacío inicialmente)
   - Agregar ClientConnection
   - Mantener compatibilidad con MessageSender existente

2. **Por cada componente** (uno a la vez):
   - Crear el componente especializado (ej: ConsoleMessageSender)
   - Agregar sus métodos al componente
   - Agregar el componente a MessageSenderComponents
   - Migrar TODO el código que usa esos métodos
   - Ejecutar tests: `./run_tests.sh`
   - ✅ Si pasan: `git commit` y `git push`
   - Eliminar métodos migrados de MessageSender original
   - Pasar al siguiente componente

3. **Orden sugerido de migración**:
   1. ConsoleMessageSender (4 métodos - simple)
   2. AudioMessageSender (10 métodos - independiente)
   3. VisualEffectsMessageSender (6 métodos - independiente)
   4. PlayerStatsMessageSender (8 métodos - crítico, incluye send_logged)
   5. MapMessageSender (5 métodos - simple)
   6. InventoryMessageSender (10 métodos - complejo, incluye send_commerce_init)
   7. CharacterMessageSender (7 métodos - complejo, incluye dice_roll y attributes)

4. **Al final**: MessageSender desaparece completamente
   - Todos los métodos migrados a componentes
   - MessageSenderComponents es el único punto de entrada

### Ventajas de este enfoque
- ✅ Commits pequeños y seguros
- ✅ Tests pasando en cada paso
- ✅ Fácil de revertir si algo falla
- ✅ Progreso visible y medible
- ✅ No rompe el código existente
