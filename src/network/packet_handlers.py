"""Mapeo de IDs de paquetes a sus handlers correspondientes."""

from typing import TYPE_CHECKING

from src.network.packet_id import ClientPacketID
from src.tasks.admin.task_gm_commands import TaskGMCommands
from src.tasks.banking.task_bank_deposit import TaskBankDeposit
from src.tasks.banking.task_bank_deposit_gold import TaskBankDepositGold
from src.tasks.banking.task_bank_end import TaskBankEnd
from src.tasks.banking.task_bank_extract import TaskBankExtract
from src.tasks.banking.task_bank_extract_gold import TaskBankExtractGold
from src.tasks.commerce.task_commerce_buy import TaskCommerceBuy
from src.tasks.commerce.task_commerce_end import TaskCommerceEnd
from src.tasks.commerce.task_commerce_sell import TaskCommerceSell
from src.tasks.interaction.task_information import TaskInformation
from src.tasks.interaction.task_left_click import TaskLeftClick
from src.tasks.interaction.task_pickup import TaskPickup
from src.tasks.interaction.task_talk import TaskTalk
from src.tasks.inventory.task_double_click import TaskDoubleClick
from src.tasks.inventory.task_drop import TaskDrop
from src.tasks.inventory.task_equip_item import TaskEquipItem
from src.tasks.inventory.task_use_item import TaskUseItem
from src.tasks.player.task_account import TaskCreateAccount
from src.tasks.player.task_attack import TaskAttack
from src.tasks.player.task_attributes import TaskRequestAttributes
from src.tasks.player.task_change_heading import TaskChangeHeading
from src.tasks.player.task_login import TaskLogin
from src.tasks.player.task_meditate import TaskMeditate
from src.tasks.player.task_request_position_update import TaskRequestPositionUpdate
from src.tasks.player.task_request_stats import TaskRequestStats
from src.tasks.player.task_walk import TaskWalk
from src.tasks.spells.task_cast_spell import TaskCastSpell
from src.tasks.spells.task_move_spell import TaskMoveSpell
from src.tasks.spells.task_spell_info import TaskSpellInfo
from src.tasks.task_ayuda import TaskAyuda
from src.tasks.task_dice import TaskDice
from src.tasks.task_motd import TaskMotd
from src.tasks.task_online import TaskOnline
from src.tasks.task_party_accept_member import TaskPartyAcceptMember
from src.tasks.task_party_create import TaskPartyCreate
from src.tasks.task_party_join import TaskPartyJoin
from src.tasks.task_party_kick import TaskPartyKick
from src.tasks.task_party_leave import TaskPartyLeave
from src.tasks.task_party_message import TaskPartyMessage
from src.tasks.task_party_set_leader import TaskPartySetLeader
from src.tasks.task_ping import TaskPing
from src.tasks.task_quit import TaskQuit
from src.tasks.task_uptime import TaskUptime
from src.tasks.work.task_work import TaskWork
from src.tasks.work.task_work_left_click import TaskWorkLeftClick

if TYPE_CHECKING:
    from src.tasks.task import Task

# Mapeo de PacketID a clase de Task
TASK_HANDLERS: dict[int, type[Task]] = {
    ClientPacketID.LOGIN: TaskLogin,
    ClientPacketID.THROW_DICES: TaskDice,
    ClientPacketID.CREATE_ACCOUNT: TaskCreateAccount,
    ClientPacketID.TALK: TaskTalk,
    ClientPacketID.WALK: TaskWalk,
    ClientPacketID.REQUEST_POSITION_UPDATE: TaskRequestPositionUpdate,  # Solicitar posición
    ClientPacketID.ATTACK: TaskAttack,  # Atacar (cuerpo a cuerpo)
    ClientPacketID.PICK_UP: TaskPickup,  # Recoger item del suelo
    ClientPacketID.DROP: TaskDrop,  # Tirar item al suelo
    ClientPacketID.CAST_SPELL: TaskCastSpell,  # Lanzar hechizo
    ClientPacketID.MOVE_SPELL: TaskMoveSpell,  # Reordenar hechizo en el libro
    ClientPacketID.LEFT_CLICK: TaskLeftClick,  # Click en personaje/NPC
    ClientPacketID.DOUBLE_CLICK: TaskDoubleClick,  # Doble click - item o NPC
    ClientPacketID.USE_ITEM: TaskUseItem,  # Usar ítem del inventario
    ClientPacketID.EQUIP_ITEM: TaskEquipItem,  # Equipar/desequipar item
    ClientPacketID.CHANGE_HEADING: TaskChangeHeading,
    ClientPacketID.WORK: TaskWork,  # Trabajar (talar, minar, pescar)
    ClientPacketID.WORK_LEFT_CLICK: TaskWorkLeftClick,  # Trabajar con click en coordenadas
    ClientPacketID.REQUEST_ATTRIBUTES: TaskRequestAttributes,
    ClientPacketID.SPELL_INFO: TaskSpellInfo,  # Solicitar información de hechizo
    ClientPacketID.COMMERCE_BUY: TaskCommerceBuy,  # Comprar item del mercader
    ClientPacketID.BANK_EXTRACT_ITEM: TaskBankExtract,  # Extraer item del banco
    ClientPacketID.COMMERCE_SELL: TaskCommerceSell,  # Vender item al mercader
    ClientPacketID.BANK_DEPOSIT: TaskBankDeposit,  # Depositar item en el banco
    ClientPacketID.COMMERCE_END: TaskCommerceEnd,  # Cerrar ventana de comercio
    ClientPacketID.BANK_END: TaskBankEnd,  # Cerrar ventana de banco
    ClientPacketID.AYUDA: TaskAyuda,
    ClientPacketID.MEDITATE: TaskMeditate,  # Meditar
    ClientPacketID.REQUEST_STATS: TaskRequestStats,
    ClientPacketID.INFORMATION: TaskInformation,
    ClientPacketID.REQUEST_MOTD: TaskMotd,
    ClientPacketID.UPTIME: TaskUptime,
    ClientPacketID.ONLINE: TaskOnline,
    ClientPacketID.QUIT: TaskQuit,
    ClientPacketID.PING: TaskPing,
    ClientPacketID.BANK_EXTRACT_GOLD: TaskBankExtractGold,  # Retirar oro del banco
    ClientPacketID.BANK_DEPOSIT_GOLD: TaskBankDepositGold,  # Depositar oro en banco
    ClientPacketID.GM_COMMANDS: TaskGMCommands,  # Comandos GM (teletransporte)
    ClientPacketID.PARTY_LEAVE: TaskPartyLeave,  # /SALIRPARTY - Abandonar party
    ClientPacketID.PARTY_CREATE: TaskPartyCreate,  # /CREARPARTY - Crear nueva party
    ClientPacketID.PARTY_JOIN: TaskPartyJoin,  # /PARTY - Invitar a party
    ClientPacketID.PARTY_MESSAGE: TaskPartyMessage,  # /PMSG - Mensaje de party
    ClientPacketID.PARTY_KICK: TaskPartyKick,  # Expulsar miembro de party
    ClientPacketID.PARTY_SET_LEADER: TaskPartySetLeader,  # Transferir liderazgo de party
    ClientPacketID.PARTY_ACCEPT_MEMBER: TaskPartyAcceptMember,  # /ACCEPTPARTY - Aceptar invitación
}
