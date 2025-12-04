"""Constantes de gameplay del juego.

Este módulo centraliza todas las constantes de balance y límites del juego
que estaban dispersas en múltiples archivos.
"""

# =============================================================================
# INVENTARIO Y SLOTS
# =============================================================================

MAX_INVENTORY_SLOTS = 20  # Slots de inventario del jugador
MAX_BANK_SLOTS = 20  # Slots de banco del jugador
MAX_MERCHANT_SLOTS = 20  # Slots de inventario de mercader
MAX_SPELL_SLOTS = 35  # Slots del libro de hechizos
MAX_ITEMS_PER_TILE = 10  # Límite de items en un tile del suelo

# =============================================================================
# COMBATE
# =============================================================================

BASE_FIST_DAMAGE = 2  # Daño base sin arma (puños)
BASE_ARMOR_REDUCTION = 0.1  # 10% reducción base de armadura
CRITICAL_HIT_CHANCE = 0.1  # 10% probabilidad de crítico

# =============================================================================
# HECHIZOS Y ATRIBUTOS
# =============================================================================

MIN_ATTRIBUTE_MODIFIER = 2  # Modificador mínimo de agilidad/fuerza por pociones/hechizos
MAX_ATTRIBUTE_MODIFIER = 5  # Modificador máximo de agilidad/fuerza por pociones/hechizos
MAX_SPELL_RANGE = 10  # Rango máximo de hechizos en tiles

# =============================================================================
# NPCS Y MASCOTAS
# =============================================================================

MAX_PETS = 3  # Límite de mascotas por jugador (MAXMASCOTAS en VB6)
NPC_AGGRO_RANGE = 5  # Rango de agro de NPCs hostiles
NPC_RESPAWN_COOLDOWN = 60.0  # Segundos para respawn de NPCs
MAX_SPAWN_ATTEMPTS = 10  # Intentos máximos para encontrar tile libre al spawnear

# =============================================================================
# MOVIMIENTO Y SEGUIMIENTO
# =============================================================================

MAX_PET_FOLLOW_DISTANCE = 5  # Distancia máxima para que mascota siga al dueño

# =============================================================================
# PARTY - GRUPO
# =============================================================================

MAX_PARTY_MEMBERS = 5  # Máximo de miembros en un grupo
MIN_LEVEL_TO_CREATE_PARTY = 1  # Nivel mínimo para crear grupo (15 en VB6, reducido para testing)
MIN_LEADERSHIP_SCORE = 100  # Carisma * Liderazgo >= 100 para crear grupo
MAX_PARTY_LEVEL_DIFFERENCE = 10  # Diferencia máxima de nivel entre miembros
MAX_EXP_SHARING_DISTANCE = 30  # Distancia máxima para recibir experiencia del grupo
PARTY_INVITATION_TIMEOUT = 30  # Segundos para que expire invitación a grupo

# =============================================================================
# CLAN
# =============================================================================

MAX_CLAN_MEMBERS = 50  # Máximo de miembros en un clan
MIN_LEVEL_TO_CREATE_CLAN = 13  # Nivel mínimo para crear clan
MIN_LEVEL_TO_JOIN_CLAN = 1  # Nivel mínimo para unirse a clan
MAX_CLAN_NAME_LENGTH = 30  # Longitud máxima del nombre del clan
MAX_CLAN_DESCRIPTION_LENGTH = 200  # Longitud máxima de la descripción
CLAN_INVITATION_TIMEOUT = 60  # Segundos para que expire invitación a clan

# =============================================================================
# CUENTAS Y VALIDACIÓN
# =============================================================================

MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 20
MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 32

# =============================================================================
# CHAT
# =============================================================================

MAX_CHAT_MESSAGE_LENGTH = 255  # Longitud máxima del mensaje de chat

# =============================================================================
# PROCESAMIENTO DE NPCS
# =============================================================================

DEFAULT_MAX_NPCS_PER_TICK = 10  # Máximo de NPCs procesados por tick de movimiento
DEFAULT_NPC_CHUNK_SIZE = 5  # Tamaño de chunk para procesamiento paralelo

# =============================================================================
# IDS DE REPOSITORIOS
# =============================================================================

MAX_PARTY_ID = 999999  # ID máximo de party antes de reset
MAX_CLAN_ID = 999999  # ID máximo de clan antes de reset
