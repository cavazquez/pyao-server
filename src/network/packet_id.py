"""Definición de IDs de paquetes del protocolo Argentum Online.

Basado en: brian-christopher/ArgentumOnlineGodot
"""

from enum import IntEnum


class ClientPacketID(IntEnum):
    """IDs de paquetes enviados por el cliente según protocolo AO."""

    # Paquetes implementados
    LOGIN = 0  # LoginExistingChar
    THROW_DICES = 1  # ThrowDices
    CREATE_ACCOUNT = 2  # LoginNewChar
    REQUEST_ATTRIBUTES = 13  # RequestAtributes

    # Paquetes del protocolo AO (implementados)
    TALK = 3  # Hablar (chat normal)
    WALK = 6  # Caminar/moverse
    USE_ITEM = 30  # Usar item del inventario
    EQUIP_ITEM = 36  # Equipar/desequipar item
    CHANGE_HEADING = 37  # Cambiar dirección sin moverse

    # Paquetes del protocolo AO (no implementados aún)
    # ruff: noqa: ERA001
    # YELL = 4
    # WHISPER = 5
    REQUEST_POSITION_UPDATE = 7  # Solicitar actualización de posición
    ATTACK = 8  # Atacar (cuerpo a cuerpo)
    PICK_UP = 9  # Recoger item del suelo
    # SAFE_TOGGLE = 10
    # RESUSCITATION_SAFE_TOGGLE = 11
    # REQUEST_GUILD_LEADER_INFO = 12
    # REQUEST_FAME = 14
    # REQUEST_SKILLS = 15
    # REQUEST_MINI_STATS = 16
    COMMERCE_END = 17  # Cerrar ventana de comercio
    # USER_COMMERCE_END = 18
    # USER_COMMERCE_CONFIRM = 19
    # COMMERCE_CHAT = 20
    BANK_END = 21  # Cerrar ventana de banco
    # USER_COMMERCE_OK = 22
    # USER_COMMERCE_REJECT = 23
    DROP = 24  # Tirar item al suelo
    CAST_SPELL = 25  # Lanzar hechizo
    LEFT_CLICK = 26  # Click en personaje/NPC
    DOUBLE_CLICK = 27  # Doble click en inventario (usar item)
    WORK = 28  # Trabajar (talar, minar, pescar)
    # USE_SPELL_MACRO = 29
    # CRAFT_BLACKSMITH = 31
    # CRAFT_CARPENTER = 32
    WORK_LEFT_CLICK = 33  # Click en modo trabajo (con coordenadas)
    # CREATE_NEW_GUILD = 34
    # SPELL_INFO = 35
    # EQUIP_ITEM = 36
    # MODIFY_SKILLS = 38
    # TRAIN = 39
    COMMERCE_BUY = 40  # Comprar item del mercader
    BANK_EXTRACT_ITEM = 41  # Extraer item del banco
    COMMERCE_SELL = 42  # Vender item al mercader
    BANK_DEPOSIT = 43  # Depositar item en el banco
    # FORUM_POST = 44
    MOVE_SPELL = 45  # Reordenar hechizo en el libro
    # MOVE_BANK = 46
    # CLAN_CODEX_UPDATE = 47
    # USER_COMMERCE_OFFER = 48
    # GUILD_ACCEPT_PEACE = 49
    # GUILD_REJECT_ALLIANCE = 50
    # GUILD_REJECT_PEACE = 51
    # GUILD_ACCEPT_ALLIANCE = 52
    # GUILD_OFFER_PEACE = 53
    # GUILD_OFFER_ALLIANCE = 54
    # GUILD_ALLIANCE_DETAILS = 55
    # GUILD_PEACE_DETAILS = 56
    # GUILD_REQUEST_JOINER_INFO = 57
    # GUILD_ALLIANCE_PROP_LIST = 58
    # GUILD_PEACE_PROP_LIST = 59
    # GUILD_DECLARE_WAR = 60
    # GUILD_NEW_WEBSITE = 61
    # GUILD_ACCEPT_NEW_MEMBER = 62
    # GUILD_REJECT_NEW_MEMBER = 63
    # GUILD_KICK_MEMBER = 64
    # GUILD_UPDATE_NEWS = 65
    # GUILD_MEMBER_INFO = 66
    # GUILD_OPEN_ELECTIONS = 67
    # GUILD_REQUEST_MEMBERSHIP = 68
    # GUILD_REQUEST_DETAILS = 69
    ONLINE = 70
    QUIT = 71
    # GUILD_LEAVE = 72
    # REQUEST_ACCOUNT_STATE = 73
    # PET_STAND = 74
    # PET_FOLLOW = 75
    # RELEASE_PET = 76
    # TRAIN_LIST = 77
    # REST = 78
    MEDITATE = 79  # Meditar para recuperar mana
    # RESUSCITATE = 80
    # HEAL = 81
    AYUDA = 82
    REQUEST_STATS = 83
    # COMMERCE_START = 84
    BANK_START = 85  # Abrir ventana de banco
    # ENLIST = 86
    INFORMATION = 87
    # REWARD = 88
    REQUEST_MOTD = 89
    UPTIME = 90
    # PARTY_LEAVE = 91
    # PARTY_CREATE = 92
    # PARTY_JOIN = 93
    # INQUIRY = 94
    # GUILD_MESSAGE = 95
    # PARTY_MESSAGE = 96
    # CENTINEL_REPORT = 97
    # GUILD_ONLINE = 98
    # PARTY_ONLINE = 99
    # COUNCIL_MESSAGE = 100
    # ROLE_MASTER_REQUEST = 101
    # GM_REQUEST = 102
    # BUG_REPORT = 103
    # CHANGE_DESCRIPTION = 104
    # GUILD_VOTE = 105
    # PUNISHMENTS = 106
    # CHANGE_PASSWORD = 107
    # GAMBLE = 108
    # INQUIRY_VOTE = 109
    # LEAVE_FACTION = 110
    BANK_EXTRACT_GOLD = 111  # Retirar oro del banco
    BANK_DEPOSIT_GOLD = 112  # Depositar oro en banco
    # DENOUNCE = 113
    # GUILD_FUNDATE = 114
    # GUILD_FUNDATION = 115
    # PARTY_KICK = 116
    # PARTY_SET_LEADER = 117
    # PARTY_ACCEPT_MEMBER = 118
    PING = 119
    # REQUEST_PARTY_FORM = 120
    # ITEM_UPGRADE = 121
    GM_COMMANDS = 122  # Comandos de Game Master (teletransporte, etc.)
    # INIT_CRAFTING = 123
    # HOME = 124
    # SHOW_GUILD_NEWS = 125
    # SHARE_NPC = 126
    # STOP_SHARING_NPC = 127
    # CONSULTATION = 128
    # MOVE_ITEM = 129


class ServerPacketID(IntEnum):
    """IDs de paquetes enviados por el servidor según protocolo AO."""

    # Paquetes del protocolo AO estándar (implementados)
    LOGGED = 0  # Login exitoso
    # CHANGE_INVENTORY_SLOT = 13  # ID usado en algunas versiones
    UPDATE_STA = 15  # Actualizar stamina
    UPDATE_MANA = 16  # Actualizar mana
    UPDATE_HP = 17  # Actualizar HP
    CHANGE_MAP = 21  # Cambiar mapa del personaje
    POS_UPDATE = 22  # Actualizar posición del personaje
    USER_CHAR_INDEX_IN_SERVER = 28  # Índice del personaje del jugador
    UPDATE_USER_STATS = 45  # Actualizar estadísticas completas del usuario
    ATTRIBUTES = 50  # Enviar atributos del personaje (Atributes en el protocolo)
    ERROR_MSG = 55  # Mensaje de error
    UPDATE_HUNGER_AND_THIRST = 60  # Actualizar hambre y sed
    DICE_ROLL = 67  # Enviar resultado de tirada de dados

    CONSOLE_MSG = 24  # Mensaje de consola/chat
    CHARACTER_CREATE = 29  # Crear personaje en el mapa
    CHARACTER_REMOVE = 30  # Remover personaje del mapa
    CHARACTER_CHANGE = 34  # Cambiar apariencia/dirección del personaje
    PLAY_MIDI = 38  # Reproducir música MIDI
    PLAY_WAVE = 39  # Reproducir sonido WAV
    CREATE_FX = 44  # Crear efecto visual en una posición
    CHANGE_INVENTORY_SLOT = 47  # Actualizar slot de inventario

    # Paquetes del protocolo AO (no implementados aún)
    # ruff: noqa: ERA001
    # REMOVE_DIALOGS = 1
    # REMOVE_CHAR_DIALOG = 2
    # NAVIGATE_TOGGLE = 3
    # DISCONNECT = 4
    COMMERCE_END = 5  # Cerrar ventana de comercio
    BANK_END = 6  # Cerrar ventana de banco
    COMMERCE_INIT = 7  # Abrir ventana de comercio con inventario del mercader
    BANK_INIT = 8  # Abrir ventana de banco
    USER_COMMERCE_INIT = 9  # Iniciar comercio entre usuarios
    USER_COMMERCE_END = 10  # Finalizar comercio entre usuarios
    # SHOW_BLACK_SCREEN = 11
    # SHOW_SIGN = 12
    # CHANGE_INVENTORY_SLOT = 13
    # CHANGE_SPELL_SLOT = 14  # ID incorrecto, el correcto es 49
    # UPDATE_STA = 15  # Ya definido arriba
    UPDATE_BANK_GOLD = 19  # Actualizar oro del banco
    UPDATE_EXP = 20  # Actualizar experiencia
    # GUILD_CHAT = 25
    # SHOW_MESSAGE_BOX = 26
    # USER_INDEX_IN_SERVER = 27
    # USER_CHAR_INDEX_IN_SERVER = 28
    # CHARACTER_CHANGE_NICK = 31
    CHARACTER_MOVE = 32
    # FORCE_CHAR_MOVE = 33
    OBJECT_CREATE = 35
    OBJECT_DELETE = 36
    BLOCK_POSITION = 37
    # GUILD_LIST = 40
    # AREA_CHANGED = 41
    # PAUSE_TOGGLE = 42
    # RAIN_TOGGLE = 43
    # CREATE_FX = 44
    # WORK_REQUEST_TARGET = 46  # Ya no se usa, WorkRequestTarget va en MULTI_MESSAGE (104)
    # CHANGE_INVENTORY_SLOT = 47
    CHANGE_BANK_SLOT = 48  # Actualizar slot de la bóveda bancaria
    CHANGE_SPELL_SLOT = 49  # Actualizar slot de hechizo
    # BLACKSMITH_WEAPONS = 51
    # BLACKSMITH_ARMORS = 52
    # CARPENTER_OBJECTS = 53
    # REST_OK = 54
    # BLIND = 56
    # DUMB = 57
    # SHOW_SIGNAL = 58
    CHANGE_NPC_INVENTORY_SLOT = 59  # Actualizar slot del inventario del mercader
    # UPDATE_HUNGER_AND_THIRST = 60
    # FAME = 61
    # MINI_STATS = 62
    # LEVEL_UP = 63
    # ADD_FORUM_MSG = 64
    # SHOW_FORUM_FORM = 65
    # SET_INVISIBLE = 66
    MEDITATE_TOGGLE = 68  # Toggle meditación
    # BLIND_NO_MORE = 69
    # DUMB_NO_MORE = 70
    # SEND_SKILLS = 71
    # TRAINER_CREATURE_LIST = 72
    # GUILD_NEWS = 73
    # OFFER_DETAILS = 74
    # ALIANCE_PROPOSALS_LIST = 75
    # PEACE_PROPOSALS_LIST = 76
    # CHARACTER_INFO = 77
    # GUILD_LEADER_INFO = 78
    # GUILD_MEMBER_INFO = 79
    # GUILD_DETAILS = 80
    # SHOW_GUILD_FUNDATION_FORM = 81
    # PARALIZE_OK = 82
    # SHOW_USER_REQUEST = 83
    # TRADE_OK = 84
    BANK_OK = 85  # Confirmar operación bancaria
    # CHANGE_USER_TRADE_SLOT = 86
    # SEND_NIGHT = 87
    PONG = 88
    # UPDATE_TAG_AND_STATUS = 89
    # SPAWN_LIST = 90
    # SHOW_SOS_FORM = 91
    # SHOW_MOTD_EDITION_FORM = 92
    # SHOW_GM_PANEL_FORM = 93
    # USER_NAME_LIST = 94
    # SHOW_DENOUNCES = 95
    # RECORD_LIST = 96
    # RECORD_DETAILS = 97
    # SHOW_GUILD_ALIGN = 98
    # SHOW_PARTY_FORM = 99
    # UPDATE_STRENGTH_AND_DEXTERITY = 100
    # UPDATE_STRENGTH = 101
    # UPDATE_DEXTERITY = 102
    # ADD_SLOTS = 103
    MULTI_MESSAGE = 104  # Mensaje multipropósito con subtipos
    # STOP_WORKING = 105
    # CANCEL_OFFER_ITEM = 106
