# Análisis de Tests Redundantes

**Fecha de análisis:** 2025-11-30 12:21:53
**Total de líneas cubiertas:** 136,507

> **Nota:** Este análisis compara qué líneas de código cubre cada
> archivo de test. Un archivo de test que no aporta líneas únicas
> puede ser redundante, aunque valide comportamientos diferentes.

## Resumen Ejecutivo

- **Total de archivos de test analizados:** 212
- **Archivos de test completamente redundantes (0 líneas únicas):** 20
- **Archivos de test casi redundantes (<10 líneas únicas):** 44
- **Archivos de test con baja contribución (<50 líneas únicas):** 111
- **Archivos de test con contribución significativa (≥50 líneas únicas):** 37

---

## Archivos de Test Completamente Redundantes

Estos archivos de test pueden eliminarse sin reducir la cobertura total:

| Archivo de Test | Líneas Cubiertas | Líneas Únicas | Recomendación |
|-----------------|-------------------|---------------|---------------|
| `tests/test_init.py` | 111 | 0 | ⚠️ **ELIMINAR** |
| `tests/effects/test_tick_effect.py` | 124 | 0 | ⚠️ **ELIMINAR** |
| `tests/combat/test_combat_reward_calculator.py` | 129 | 0 | ⚠️ **ELIMINAR** |
| `tests/unit/test_dependency_container.py` | 157 | 0 | ⚠️ **ELIMINAR** |
| `tests/network/test_msg_visual_effects.py` | 252 | 0 | ⚠️ **ELIMINAR** |
| `tests/network/test_msg_audio.py` | 255 | 0 | ⚠️ **ELIMINAR** |
| `tests/network/test_msg_console.py` | 264 | 0 | ⚠️ **ELIMINAR** |
| `tests/network/test_msg_map.py` | 277 | 0 | ⚠️ **ELIMINAR** |
| `tests/network/test_msg_character.py` | 292 | 0 | ⚠️ **ELIMINAR** |
| `tests/services/npc/test_npc_sounds.py` | 294 | 0 | ⚠️ **ELIMINAR** |
| `tests/network/test_msg_player_stats.py` | 295 | 0 | ⚠️ **ELIMINAR** |
| `tests/messaging/test_message_console_sender.py` | 310 | 0 | ⚠️ **ELIMINAR** |
| `tests/models/test_character_class.py` | 319 | 0 | ⚠️ **ELIMINAR** |
| `tests/unit/test_config.py` | 327 | 0 | ⚠️ **ELIMINAR** |
| `tests/models/test_item_types.py` | 341 | 0 | ⚠️ **ELIMINAR** |
| `tests/tasks/admin/test_task_gm_commands.py` | 673 | 0 | ⚠️ **ELIMINAR** |
| `tests/integration/test_broadcast_movement.py` | 692 | 0 | ⚠️ **ELIMINAR** |
| `tests/services/npc/test_npc_ai_configurable.py` | 1340 | 0 | ⚠️ **ELIMINAR** |
| `tests/integration/test_class_system_integration.py` | 1395 | 0 | ⚠️ **ELIMINAR** |
| `tests/services/player/test_player_service.py` | 2215 | 0 | ⚠️ **ELIMINAR** |

---

## Archivos de Test Casi Redundantes (<10 líneas únicas)

Estos archivos de test aportan muy poca cobertura única:

| Archivo de Test | Líneas Cubiertas | Líneas Únicas | Recomendación |
|-----------------|-------------------|---------------|---------------|
| `tests/effects/test_meditation_effect.py` | 142 | 1 | 🔍 Revisar |
| | | Ejemplo: src/effects/meditation_effect.py:42 | |
| `tests/effects/test_npc_ai_effect.py` | 142 | 1 | 🔍 Revisar |
| | | Ejemplo: src/effects/npc_ai_effect.py:44 | |
| `tests/messaging/test_message_visual_effects_sender.py` | 324 | 1 | 🔍 Revisar |
| | | Ejemplo: src/messaging/senders/message_visual_effects_sender.py:55 | |
| `tests/models/test_items_catalog.py` | 381 | 1 | 🔍 Revisar |
| | | Ejemplo: src/models/items_catalog.py:305 | |
| `tests/services/npc/test_npc_ai_combat_effects.py` | 878 | 1 | 🔍 Revisar |
| | | Ejemplo: src/services/npc/npc_ai_service.py:259 | |
| `tests/tasks/spells/test_spell_targeting.py` | 583 | 1 | 🔍 Revisar |
| | | Ejemplo: src/tasks/spells/task_cast_spell.py:130 | |
| `tests/combat/test_combat_damage_calculator.py` | 383 | 2 | 🔍 Revisar |
| | | Ejemplo: src/combat/combat_damage_calculator.py:60, src/combat/combat_critical_calculator.py:121 | |
| `tests/combat/test_combat_validator.py` | 345 | 2 | 🔍 Revisar |
| | | Ejemplo: src/combat/combat_validator.py:63, src/combat/combat_validator.py:64 | |
| `tests/game/test_map_manager_exit_tiles.py` | 278 | 2 | 🔍 Revisar |
| | | Ejemplo: src/game/map_manager.py:812, src/game/map_manager_spatial.py:37 | |
| `tests/messaging/test_message_audio_sender.py` | 347 | 2 | 🔍 Revisar |
| | | Ejemplo: src/messaging/senders/message_audio_sender.py:73, src/messaging/senders/message_audio_sender.py:69 | |
| `tests/network/test_client_connection.py` | 134 | 2 | 🔍 Revisar |
| | | Ejemplo: src/network/client_connection.py:67, src/network/client_connection.py:71 | |
| `tests/tasks/spells/test_task_cast_spell.py` | 584 | 2 | 🔍 Revisar |
| | | Ejemplo: src/tasks/spells/task_cast_spell.py:109, src/tasks/spells/task_cast_spell.py:110 | |
| `tests/network/test_msg_session.py` | 277 | 3 | 🔍 Revisar |
| | | Ejemplo: src/network/msg_session.py:101, src/network/msg_session.py:102, src/network/msg_session.py:103 | |
| `tests/services/map/test_map_transition_steps.py` | 944 | 3 | 🔍 Revisar |
| | | Ejemplo: src/services/map/map_transition_steps.py:277, src/services/map/map_transition_steps.py:278, src/services/map/map_transition_steps.py:279 | |
| `tests/unit/test_music.py` | 900 | 3 | 🔍 Revisar |
| | | Ejemplo: src/messaging/message_sender.py:531, src/messaging/message_sender.py:527, src/messaging/message_sender.py:523 | |
| `tests/utils/test_sounds.py` | 902 | 3 | 🔍 Revisar |
| | | Ejemplo: src/messaging/message_sender.py:502, src/messaging/message_sender.py:498, src/messaging/message_sender.py:506 | |
| `tests/utils/test_visual_effects.py` | 904 | 3 | 🔍 Revisar |
| | | Ejemplo: src/messaging/message_sender.py:548, src/messaging/message_sender.py:544, src/messaging/message_sender.py:540 | |
| `tests/models/test_item_catalog.py` | 326 | 4 | 🔍 Revisar |
| | | Ejemplo: src/models/item_catalog.py:63, src/models/item_catalog.py:99, src/models/item_catalog.py:61... | |
| `tests/utils/test_password_utils.py` | 122 | 4 | 🔍 Revisar |
| | | Ejemplo: src/utils/password_utils.py:32, src/utils/password_utils.py:33, src/utils/password_utils.py:30... | |
| `tests/command_handlers/test_motd_handler.py` | 190 | 5 | 🔍 Revisar |
| | | Ejemplo: src/command_handlers/motd_handler.py:64, src/command_handlers/motd_handler.py:53, src/command_handlers/motd_handler.py:66... | |
| `tests/command_handlers/test_start_player_trade_handler.py` | 187 | 5 | 🔍 Revisar |
| | | Ejemplo: src/command_handlers/start_player_trade_handler.py:40, src/command_handlers/start_player_trade_handler.py:43, src/command_handlers/start_player_trade_handler.py:62... | |
| `tests/effects/test_effect_gold_decay.py` | 167 | 5 | 🔍 Revisar |
| | | Ejemplo: src/effects/effect_gold_decay.py:100, src/effects/effect_gold_decay.py:64, src/effects/effect_gold_decay.py:112... | |
| `tests/models/test_spell_catalog.py` | 327 | 5 | 🔍 Revisar |
| | | Ejemplo: src/models/spell_catalog.py:95, src/models/spell_catalog.py:31, src/models/spell_catalog.py:87... | |
| `tests/effects/test_effect_hunger_thirst.py` | 416 | 6 | 🔍 Revisar |
| | | Ejemplo: src/effects/effect_hunger_thirst.py:170, src/effects/effect_hunger_thirst.py:171, src/effects/effect_hunger_thirst.py:123... | |
| `tests/messaging/test_message_session_sender.py` | 334 | 6 | 🔍 Revisar |
| | | Ejemplo: src/messaging/senders/message_session_sender.py:83, src/messaging/senders/message_session_sender.py:92, src/messaging/senders/message_session_sender.py:76... | |
| `tests/repositories/test_merchant_repository.py` | 953 | 6 | 🔍 Revisar |
| | | Ejemplo: src/repositories/merchant_repository.py:51, src/repositories/merchant_repository.py:50, src/repositories/merchant_repository.py:56... | |
| `tests/services/combat/test_combat_weapon_service.py` | 680 | 6 | 🔍 Revisar |
| | | Ejemplo: src/services/combat/combat_weapon_service.py:64, src/services/combat/combat_weapon_service.py:67, src/services/combat/combat_weapon_service.py:63... | |
| `tests/tasks/commerce/test_task_commerce_end.py` | 943 | 6 | 🔍 Revisar |
| | | Ejemplo: src/tasks/commerce/task_commerce_end.py:35, src/tasks/commerce/task_commerce_end.py:44, src/tasks/commerce/task_commerce_end.py:52... | |
| `tests/tasks/interaction/test_task_information.py` | 943 | 6 | 🔍 Revisar |
| | | Ejemplo: src/tasks/interaction/task_information.py:35, src/tasks/interaction/task_information.py:44, src/tasks/interaction/task_information.py:49... | |
| `tests/tasks/test_task_ayuda.py` | 942 | 6 | 🔍 Revisar |
| | | Ejemplo: src/tasks/task_ayuda.py:49, src/tasks/task_ayuda.py:55, src/tasks/task_ayuda.py:52... | |

... y 14 archivos más.

---

## Archivos de Test con Baja Contribución (<50 líneas únicas)

Lista de archivos de test que aportan menos de 50 líneas únicas (mostrando primeros 50):

| Archivo de Test | Líneas Cubiertas | Líneas Únicas |
|-----------------|-------------------|---------------|
| `tests/config/test_game_config.py` | 334 | 10 |
| `tests/tasks/test_task_null.py` | 906 | 10 |
| `tests/command_handlers/test_commerce_end_handler.py` | 186 | 11 |
| `tests/command_handlers/test_invite_clan_handler.py` | 182 | 11 |
| `tests/command_handlers/test_ping_handler.py` | 186 | 11 |
| `tests/command_handlers/test_reject_clan_handler.py` | 181 | 11 |
| `tests/command_handlers/test_update_trade_offer_handler.py` | 171 | 11 |
| `tests/models/test_npc_catalog.py` | 339 | 11 |
| `tests/services/game/test_class_service.py` | 939 | 11 |
| `tests/services/map/test_map_resources_service_additional.py` | 1081 | 11 |
| `tests/services/npc/test_npc_death_service.py` | 957 | 11 |
| `tests/tasks/banking/test_task_bank_end.py` | 209 | 11 |
| `tests/tasks/test_task_online.py` | 971 | 11 |
| `tests/command_handlers/test_ayuda_handler.py` | 187 | 12 |
| `tests/network/test_session_manager.py` | 150 | 12 |
| `tests/unit/test_packet_reader.py` | 171 | 12 |
| `tests/command_handlers/test_accept_clan_handler.py` | 445 | 13 |
| `tests/command_handlers/test_demote_clan_member_handler.py` | 184 | 13 |
| `tests/command_handlers/test_kick_clan_member_handler.py` | 184 | 13 |
| `tests/command_handlers/test_leave_clan_handler.py` | 183 | 13 |
| `tests/command_handlers/test_promote_clan_member_handler.py` | 184 | 13 |
| `tests/command_handlers/test_transfer_clan_leadership_handler.py` | 184 | 13 |
| `tests/services/npc/test_loot_table_service.py` | 872 | 13 |
| `tests/command_handlers/test_create_clan_handler.py` | 448 | 14 |
| `tests/messaging/test_message_combat_sender.py` | 492 | 14 |
| `tests/tasks/admin/test_gm_commands.py` | 695 | 14 |
| `tests/tasks/player/test_task_meditate.py` | 234 | 14 |
| `tests/tasks/test_task_dice.py` | 952 | 14 |
| `tests/unit/test_task_request_position_update.py` | 997 | 14 |
| `tests/command_handlers/test_bank_end_handler.py` | 191 | 15 |
| `tests/command_handlers/test_party_leave_handler.py` | 191 | 15 |
| `tests/tasks/spells/test_task_spell_info.py` | 521 | 15 |
| `tests/unit/test_task_pickup.py` | 236 | 15 |
| `tests/command_handlers/test_party_join_handler.py` | 193 | 16 |
| `tests/command_handlers/test_party_kick_handler.py` | 193 | 16 |
| `tests/command_handlers/test_party_set_leader_handler.py` | 193 | 16 |
| `tests/models/test_merchant_data_loader.py` | 423 | 16 |
| `tests/repositories/test_server_repository.py` | 960 | 16 |
| `tests/tasks/banking/test_task_bank_deposit_gold.py` | 216 | 16 |
| `tests/tasks/banking/test_task_bank_extract_gold.py` | 216 | 16 |
| `tests/test_packet_length_validator.py` | 152 | 16 |
| `tests/command_handlers/test_party_create_handler.py` | 380 | 17 |
| `tests/command_handlers/test_party_message_handler.py` | 194 | 17 |
| `tests/tasks/commerce/test_task_commerce_buy.py` | 218 | 17 |
| `tests/tasks/commerce/test_task_commerce_sell.py` | 218 | 17 |
| `tests/tasks/player/test_task_request_stats.py` | 979 | 17 |
| `tests/utils/test_inventory_stacking_strategy.py` | 206 | 17 |
| `tests/command_handlers/test_request_position_update_handler.py` | 194 | 18 |
| `tests/effects/test_effect_attribute_modifiers.py` | 157 | 18 |
| `tests/network/test_packet_validator_complete.py` | 498 | 18 |

... y 61 archivos más.

---

## Recomendaciones

1. **Archivos completamente redundantes**: Pueden eliminarse inmediatamente si
   no aportan cobertura única.
2. **Archivos casi redundantes**: Revisar si las líneas únicas son críticas
   antes de eliminar.
3. **Este análisis es aproximado**: Dos archivos de test pueden cubrir las
   mismas líneas pero validar comportamientos diferentes (diferentes datos,
   casos edge, validaciones).
4. **Se recomienda revisión manual**: Antes de eliminar archivos de test,
   verificar que realmente validan lo mismo.

## Metodología

Este análisis compara qué líneas de código cubre cada archivo de test.
Un archivo de test que no aporta líneas únicas (todas sus líneas están
cubiertas por otros tests) es completamente redundante desde el punto de
vista de cobertura.

**Limitaciones:**
- Este análisis no considera diferencias en datos de entrada o casos edge.
- Tests que cubren las mismas líneas pero validan comportamientos diferentes
  pueden aparecer como redundantes.
- El análisis es por archivo de test, no por test individual.
- Se recomienda revisión manual antes de eliminar archivos de test.
