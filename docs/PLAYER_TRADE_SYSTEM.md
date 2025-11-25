## Sistema de Comercio entre Jugadores

### Resumen
- Comando ` /COMERCIAR <nombre>` abre una sesión contra otro jugador en línea.
- Packets involucrados:
  - `ClientPacketID.COMMERCE_START (84)` → inicia solicitud.
  - `ServerPacketID.USER_COMMERCE_INIT (9)` → abre la ventana en ambos clientes.
  - `ClientPacketID.USER_COMMERCE_OFFER (48)` → envía cambios de oferta (slot o `0` para oro).
  - `ClientPacketID.USER_COMMERCE_CONFIRM (19)` / `USER_COMMERCE_OK (22)` → marca listo.
  - `ClientPacketID.USER_COMMERCE_END (18)` / `USER_COMMERCE_REJECT (23)` → cancela.
  - `ServerPacketID.USER_COMMERCE_END (10)` → cierra la ventana y resetea estado.

### Flujo
1. `TalkCommand` detecta `/COMERCIAR` y delega en `StartPlayerTradeCommandHandler`.
2. `TradeService.request_trade()` valida estado y crea `TradeSession`.
3. `TaskUserCommerceOffer` recibe packet 48 y llama a `UpdateTradeOfferCommandHandler → TradeService.update_offer`.
   - Slot `0` representa oro.
   - Las ofertas resetean confirmaciones si cambian.
4. `TaskUserCommerceConfirm/Ok` marcan cada lado como listo.
   - En cuanto ambos confirman, `TradeService`:
     - Vuelve a validar inventario/oro.
     - Reserva items/oro.
     - Entrega al otro participante, aplicando rollback si algo falla.
5. `TaskUserCommerceEnd/Reject` cancela la sesión y envía `USER_COMMERCE_END`.

### Validaciones Clave
- Jugadores no pueden comerciar consigo mismos.
- No se puede abrir más de una sesión por jugador.
- Para ofertas:
  - Slot debe existir y cantidad no puede superar lo disponible.
  - Oro ofrecido no puede superar el saldo actual.
  - Cambios de oferta eliminan confirmaciones previas.
- Confirmaciones dobles disparan el intercambio:
  - Usa `InventoryRepository.remove_item`/`add_item`.
  - Usa `PlayerRepository.remove_gold`/`add_gold`.
  - Rollback garantizado si algún paso falla.

### Tests relevantes
- `tests/services/test_trade_service.py` cubre:
  - Creación de sesión y duplicados.
  - Validaciones de oferta y oro.
  - Intercambio real de items y oro.
- `tests/command_handlers/test_update_trade_offer_handler.py` asegura que el handler propaga errores y notificaciones.

### Uso manual
1. Jugador A escribe `/COMERCIAR B`.
2. Ambos ven la ventana; cada uno selecciona slots y/o oro.
3. Cuando los dos confirman, el intercambio se aplica y se envía mensaje de éxito; si falla, se muestran los motivos en consola.

