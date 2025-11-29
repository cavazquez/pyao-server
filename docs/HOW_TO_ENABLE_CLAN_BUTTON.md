# Cómo Habilitar el Botón de Clanes

**Cuando el cliente Godot implemente el handler para el packet 80 (GuildDetails)**

---

## Paso 1: Modificar LoginCommandHandler

En `src/command_handlers/login_handler.py`, agregar `clan_service` al constructor y enviar el packet:

```python
# En el constructor, agregar:
clan_service: "ClanService | None" = None,

# Y guardar:
self.clan_service = clan_service
```

Luego, en `_finalize_login()`, después de enviar `SHOW_PARTY_FORM`, agregar:

```python
# Enviar detalles del clan si el jugador pertenece a uno (habilitar botón de clan)
if self.clan_service:
    clan = await self.clan_service.clan_repo.get_user_clan(user_id)
    if clan:
        logger.info(
            "Enviando CLAN_DETAILS para habilitar botón CLAN (user_id: %d, clan: %s)",
            user_id,
            clan.name,
        )
        await self.message_sender.send_clan_details(clan)
```

## Paso 2: Modificar TaskFactory

En `src/tasks/task_factory.py`, en `_get_login_handler()`, agregar `clan_service`:

```python
clan_service=self.deps.clan_service,
```

## Paso 3: Verificar

1. El packet `CLAN_DETAILS` (80) ya está implementado en `src/network/msg_clan.py`
2. Los métodos `send_clan_details()` ya existen en `MessageSender` y `SessionMessageSender`
3. Solo falta habilitar el envío cuando el cliente esté listo

---

**Ver:** `docs/CLAN_BUTTON_ENABLING.md` para más detalles del formato del packet.

