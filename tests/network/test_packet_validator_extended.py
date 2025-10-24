"""Tests extendidos para PacketValidator - Cobertura completa de todos los validadores."""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator

if TYPE_CHECKING:
    import pytest


class TestValidateCreateAccountPacket:
    """Tests para validate_create_account_packet."""

    def test_create_account_valid(self) -> None:
        """Test con datos válidos de creación de cuenta."""
        username = "testuser"
        password = "password123"
        email = "test@example.com"

        username_bytes = username.encode("utf-8")
        password_bytes = password.encode("utf-8")
        email_bytes = email.encode("utf-8")

        data = (
            bytes([2])  # PacketID
            + struct.pack("<H", len(username_bytes))
            + username_bytes
            + struct.pack("<H", len(password_bytes))
            + password_bytes
            + bytes([1])  # race
            + struct.pack("<H", 0)  # unknown
            + bytes([1])  # gender
            + bytes([1])  # job
            + bytes([0])  # unknown
            + struct.pack("<H", 1)  # head
            + struct.pack("<H", len(email_bytes))
            + email_bytes
            + bytes([1])  # home
        )

        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_create_account_packet()

        assert result.success is True
        assert result.data is not None
        assert result.data["username"] == username
        assert result.data["password"] == password
        assert result.data["email"] == email
        assert result.data["race"] == 1
        assert result.data["gender"] == 1
        assert result.data["job"] == 1
        assert result.data["head"] == 1
        assert result.data["home"] == 1

    def test_create_account_username_too_short(self) -> None:
        """Test con username muy corto."""
        username = "ab"  # Muy corto (mínimo 3)
        password = "password123"
        email = "test@example.com"

        username_bytes = username.encode("utf-8")
        password_bytes = password.encode("utf-8")
        email_bytes = email.encode("utf-8")

        data = (
            bytes([2])
            + struct.pack("<H", len(username_bytes))
            + username_bytes
            + struct.pack("<H", len(password_bytes))
            + password_bytes
            + bytes([1, 0, 0, 1, 1, 0])
            + struct.pack("<H", 1)
            + struct.pack("<H", len(email_bytes))
            + email_bytes
            + bytes([1])
        )

        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_create_account_packet()

        assert result.success is False
        assert result.data is None
        assert "muy corto" in result.error_message.lower()


class TestValidateThrowDicesPacket:
    """Tests para validate_throw_dices_packet."""

    def test_throw_dices_valid(self) -> None:
        """Test con packet válido."""
        data = bytes([1])  # PacketID
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_throw_dices_packet()

        assert result.success is True
        assert result.data == {}


class TestValidateRequestAttributesPacket:
    """Tests para validate_request_attributes_packet."""

    def test_request_attributes_valid(self) -> None:
        """Test con packet válido."""
        data = bytes([13])  # PacketID
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_request_attributes_packet()

        assert result.success is True
        assert result.data == {}


class TestValidateCommerceEndPacket:
    """Tests para validate_commerce_end_packet."""

    def test_commerce_end_valid(self) -> None:
        """Test con packet válido."""
        data = bytes([17])  # PacketID
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_commerce_end_packet()

        assert result.success is True
        assert result.data == {}


class TestValidateBankEndPacket:
    """Tests para validate_bank_end_packet."""

    def test_bank_end_valid(self) -> None:
        """Test con packet válido."""
        data = bytes([21])  # PacketID
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_bank_end_packet()

        assert result.success is True
        assert result.data == {}


class TestValidateRequestPositionUpdatePacket:
    """Tests para validate_request_position_update_packet."""

    def test_request_position_update_valid(self) -> None:
        """Test con packet válido."""
        data = bytes([7])  # PacketID
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_request_position_update_packet()

        assert result.success is True
        assert result.data == {}


class TestValidateGMCommandsPacket:
    """Tests para validate_gm_commands_packet."""

    def test_gm_commands_valid(self) -> None:
        """Test con comando GM válido."""
        username = "testuser"
        username_bytes = username.encode("utf-16le")

        data = (
            bytes([122])  # PacketID GM_COMMANDS
            + bytes([1])  # subcommand
            + struct.pack("<H", len(username_bytes))
            + username_bytes
            + struct.pack("<H", 1)  # map_id
            + bytes([50])  # x
            + bytes([50])  # y
        )

        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_gm_commands_packet()

        assert result.success is True
        assert result.data is not None
        assert result.data["subcommand"] == 1
        assert result.data["username"] == username
        assert result.data["map_id"] == 1
        assert result.data["x"] == 50
        assert result.data["y"] == 50


class TestValidateMeditatePacket:
    """Tests para validate_meditate_packet."""

    def test_meditate_valid(self) -> None:
        """Test con packet válido."""
        data = bytes([79])  # PacketID
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_meditate_packet()

        assert result.success is True
        assert result.data == {}


class TestValidateRequestStatsPacket:
    """Tests para validate_request_stats_packet."""

    def test_request_stats_valid(self) -> None:
        """Test con packet válido."""
        data = bytes([83])  # PacketID
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_request_stats_packet()

        assert result.success is True
        assert result.data == {}


class TestValidateInformationPacket:
    """Tests para validate_information_packet."""

    def test_information_valid(self) -> None:
        """Test con packet válido."""
        data = bytes([87])  # PacketID
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_information_packet()

        assert result.success is True
        assert result.data == {}


class TestValidateRequestMotdPacket:
    """Tests para validate_request_motd_packet."""

    def test_request_motd_valid(self) -> None:
        """Test con packet válido."""
        data = bytes([89])  # PacketID
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_request_motd_packet()

        assert result.success is True
        assert result.data == {}


class TestValidateUptimePacket:
    """Tests para validate_uptime_packet."""

    def test_uptime_valid(self) -> None:
        """Test con packet válido."""
        data = bytes([90])  # PacketID
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_uptime_packet()

        assert result.success is True
        assert result.data == {}


class TestValidateOnlinePacket:
    """Tests para validate_online_packet."""

    def test_online_valid(self) -> None:
        """Test con packet válido."""
        data = bytes([70])  # PacketID
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_online_packet()

        assert result.success is True
        assert result.data == {}


class TestValidateQuitPacket:
    """Tests para validate_quit_packet."""

    def test_quit_valid(self) -> None:
        """Test con packet válido."""
        data = bytes([71])  # PacketID
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_quit_packet()

        assert result.success is True
        assert result.data == {}


class TestValidatePingPacket:
    """Tests para validate_ping_packet."""

    def test_ping_valid(self) -> None:
        """Test con packet válido."""
        data = bytes([119])  # PacketID
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_ping_packet()

        assert result.success is True
        assert result.data == {}


class TestValidateAyudaPacket:
    """Tests para validate_ayuda_packet."""

    def test_ayuda_valid(self) -> None:
        """Test con packet válido."""
        data = bytes([82])  # PacketID
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_ayuda_packet()

        assert result.success is True
        assert result.data == {}


class TestValidatePacketById:
    """Tests para validate_packet_by_id."""

    def test_validate_packet_by_id_walk(self) -> None:
        """Test validando WALK por ID."""
        data = bytes([6, 1])  # WALK con heading=1
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_packet_by_id(6)

        assert result is not None
        assert result.success is True
        assert result.data == {"heading": 1}

    def test_validate_packet_by_id_unknown(self) -> None:
        """Test con packet ID desconocido."""
        data = bytes([255])  # ID desconocido
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_packet_by_id(255)

        assert result is None


class TestValidationResultLogValidation:
    """Tests para ValidationResult.log_validation."""

    def test_log_validation_success(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging de validación exitosa."""
        data = bytes([6, 1])
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_walk_packet()

        with caplog.at_level("DEBUG"):
            result.log_validation("WALK", 6, "127.0.0.1:12345")

        # Verificar que se registró el log
        assert any("127.0.0.1:12345" in record.message for record in caplog.records)
        assert any("WALK" in record.message for record in caplog.records)

    def test_log_validation_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test logging de validación fallida."""
        data = bytes([6, 5])  # heading inválido
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_walk_packet()

        with caplog.at_level("WARNING"):
            result.log_validation("WALK", 6, "127.0.0.1:12345")

        # Verificar que se registró el warning
        assert any("127.0.0.1:12345" in record.message for record in caplog.records)
        assert any("inválido" in record.message.lower() for record in caplog.records)


class TestValidateCommerceBuyPacket:
    """Tests para validate_commerce_buy_packet."""

    def test_commerce_buy_valid(self) -> None:
        """Test con datos válidos."""
        data = bytes([40, 10]) + struct.pack("<H", 5)  # slot=10, quantity=5
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_commerce_buy_packet()

        assert result.success is True
        assert result.data == {"slot": 10, "quantity": 5}

    def test_commerce_buy_invalid_quantity(self) -> None:
        """Test con cantidad inválida."""
        data = bytes([40, 10]) + struct.pack("<H", 20000)  # quantity > 10000
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_commerce_buy_packet()

        assert result.success is False


class TestValidateCommerceSellPacket:
    """Tests para validate_commerce_sell_packet."""

    def test_commerce_sell_valid(self) -> None:
        """Test con datos válidos."""
        data = bytes([42, 5]) + struct.pack("<H", 3)  # slot=5, quantity=3
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_commerce_sell_packet()

        assert result.success is True
        assert result.data == {"slot": 5, "quantity": 3}


class TestValidateBankDepositPacket:
    """Tests para validate_bank_deposit_packet."""

    def test_bank_deposit_valid(self) -> None:
        """Test con datos válidos."""
        data = bytes([43, 8]) + struct.pack("<H", 100)  # slot=8, quantity=100
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_bank_deposit_packet()

        assert result.success is True
        assert result.data == {"slot": 8, "quantity": 100}


class TestValidateBankExtractPacket:
    """Tests para validate_bank_extract_packet."""

    def test_bank_extract_valid(self) -> None:
        """Test con datos válidos."""
        data = bytes([41, 15]) + struct.pack("<H", 50)  # slot=15, quantity=50
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_bank_extract_packet()

        assert result.success is True
        assert result.data == {"slot": 15, "quantity": 50}

    def test_bank_extract_invalid_slot(self) -> None:
        """Test con slot inválido (>40)."""
        data = bytes([41, 50]) + struct.pack("<H", 50)  # slot=50 > 40
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_bank_extract_packet()

        assert result.success is False


class TestValidateChangeHeadingPacket:
    """Tests para validate_change_heading_packet."""

    def test_change_heading_valid(self) -> None:
        """Test con heading válido."""
        data = bytes([37, 2])  # heading=2
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_change_heading_packet()

        assert result.success is True
        assert result.data == {"heading": 2}

    def test_change_heading_invalid(self) -> None:
        """Test con heading inválido."""
        data = bytes([37, 5])  # heading=5 (inválido)
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_change_heading_packet()

        assert result.success is False


class TestValidateDoubleClickPacket:
    """Tests para validate_double_click_packet."""

    def test_double_click_valid(self) -> None:
        """Test con slot válido."""
        data = bytes([27, 10])  # slot=10
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_double_click_packet()

        assert result.success is True
        assert result.data == {"slot": 10}


class TestValidateLeftClickPacket:
    """Tests para validate_left_click_packet."""

    def test_left_click_valid(self) -> None:
        """Test con coordenadas válidas."""
        data = bytes([26, 50, 60])  # x=50, y=60
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_left_click_packet()

        assert result.success is True
        assert result.data == {"x": 50, "y": 60}

    def test_left_click_invalid_coordinates(self) -> None:
        """Test con coordenadas inválidas."""
        data = bytes([26, 150, 60])  # x=150 > 100
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_left_click_packet()

        assert result.success is False


class TestValidateEquipItemPacket:
    """Tests para validate_equip_item_packet."""

    def test_equip_item_valid(self) -> None:
        """Test con slot válido."""
        data = bytes([36, 5])  # slot=5
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_equip_item_packet()

        assert result.success is True
        assert result.data == {"slot": 5}


class TestValidateUseItemPacket:
    """Tests para validate_use_item_packet."""

    def test_use_item_valid(self) -> None:
        """Test con slot válido."""
        data = bytes([30, 12])  # slot=12
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_use_item_packet()

        assert result.success is True
        assert result.data == {"slot": 12}
