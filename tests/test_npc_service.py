"""Tests para el NPCService.

Verifica que el sistema de NPCs cargue correctamente y proporcione
todas las funcionalidades esperadas de gestión de NPCs.
"""

import sys
from pathlib import Path

# Agregar src al path para poder importar servicios
sys.path.append(str(Path(__file__).parent.parent / "src"))

from services.game.npc_service import NPCService


class TestNPCService:
    """Tests para NPCService con datos reales."""

    def setup_method(self) -> None:
        """Configurar método de prueba."""
        # Usar directorio data real
        self.data_dir = Path(__file__).parent.parent / "data"

        # Crear servicio con directorio real
        self.service = NPCService(self.data_dir)

    def test_load_npc_data(self):
        """Test carga de datos de NPCs."""
        npcs = self.service.get_all_npcs()
        assert len(npcs) >= 1  # Al menos nuestro test NPC

        # Verificar que nuestro test NPC está cargado
        test_npc = self.service.get_npc_by_id(1)
        if test_npc:
            assert test_npc["name"] == "Test NPC"
            assert "test" in test_npc["tags"]

    def test_get_npc_by_id(self):
        """Test búsqueda de NPC por ID."""
        # Test con nuestro NPC de prueba
        npc = self.service.get_npc_by_id(1)
        if npc:
            assert npc["name"] == "Test NPC"
            assert npc["category"] == "NPCS VARIOS"

        # NPC inexistente
        npc = self.service.get_npc_by_id(9999)
        assert npc is None

    def test_get_npc_by_name(self):
        """Test búsqueda de NPC por nombre."""
        # Test case insensitive
        npc = self.service.get_npc_by_name("npc test")
        if npc:
            assert npc["id"] == 1
            assert "Test" in npc["name"]

        # Nombre inexistente
        npc = self.service.get_npc_by_name("Nonexistent NPC")
        assert npc is None

    def test_npc_basic_functionality(self):
        """Test funcionalidad básica de NPCs."""
        # Verificar que el servicio no esté vacío
        npcs = self.service.get_all_npcs()
        assert len(npcs) >= 1

        # Probar algunos métodos básicos
        stats = self.service.get_npc_statistics()
        assert "total_npcs" in stats
        assert stats["total_npcs"] >= 1

        # Probar búsqueda
        results = self.service.search_npcs("test")
        assert isinstance(results, list)

    def test_npc_service_error_handling(self):
        """Test manejo de errores en NPCService."""
        # Buscar NPCs que no existen
        assert self.service.get_npc_by_id(99999) is None
        assert self.service.get_npc_by_name("definitely_not_exists") is None
        assert len(self.service.get_npcs_by_category("NONEXISTENT")) == 0
        assert len(self.service.get_npcs_by_type(99)) == 0

    def test_service_initialization(self):
        """Test inicialización del servicio."""
        # El servicio debe inicializarse sin errores
        assert self.service is not None
        assert hasattr(self.service, "get_all_npcs")
        assert hasattr(self.service, "get_npc_by_id")
        assert hasattr(self.service, "get_npc_statistics")


class TestNPCServiceWithTestData:
    """Tests adicionales que dependen de datos específicos."""

    def setup_method(self) -> None:
        """Configurar método de prueba."""
        self.service = NPCService()

    def test_npc_structure_validation(self):
        """Test validación de estructura de NPCs."""
        npcs = self.service.get_all_npcs()

        for npc in npcs[:5]:  # Revisar primeros 5 para no ser muy lento
            # Verificar campos obligatorios
            assert "id" in npc, f"NPC sin ID: {npc}"
            assert "name" in npc or "nombre" in npc, f"NPC sin nombre: {npc}"
            # category es opcional para NPCs amigables
            if "category" not in npc:
                assert "descripcion" in npc, f"NPC sin categoría y descripción: {npc}"

            # Verificar tipos de datos
            assert isinstance(npc["id"], int)
            name = npc.get("name", npc.get("nombre", ""))
            assert isinstance(name, str)
            # category es opcional
            if "category" in npc:
                assert isinstance(npc["category"], str)

            # Tags debe ser lista
            assert isinstance(npc.get("tags", []), list)

    def test_npc_filtering_methods(self):
        """Test métodos de filtrado de NPCs."""
        # Tests que no dependen de datos específicos

        # Test por tags vacíos
        empty_results = self.service.get_npcs_by_tags([])
        assert isinstance(empty_results, list)

        # Test por categoría inexistente
        empty_results = self.service.get_npcs_by_category("NONEXISTENT_CATEGORY")
        assert len(empty_results) == 0

        # Test por tipo inexistente
        empty_results = self.service.get_npcs_by_type(999)
        assert len(empty_results) == 0

    def test_npc_calculation_methods(self):
        """Test métodos de cálculo."""
        npcs = self.service.get_all_npcs()

        if npcs:
            # Test cálculo de dificultad con primer NPC
            first_npc = npcs[0]
            difficulty = self.service.calculate_npc_difficulty(first_npc)
            assert difficulty in {"Fácil", "Medio", "Difícil", "Extremo"}

    def test_npc_inventory_and_drops(self):
        """Test inventario y drops."""
        npcs = self.service.get_all_npcs()

        for npc in npcs[:3]:  # Revisar primeros 3
            # Los métodos no deben fallar aunque no haya datos
            inventory = self.service.get_npc_inventory(npc["id"])
            drops = self.service.get_npc_drops(npc["id"])

            assert isinstance(inventory, list)
            assert isinstance(drops, list)

    def test_npc_behavior_flags(self):
        """Test flags de comportamiento."""
        npcs = self.service.get_all_npcs()

        for npc in npcs[:3]:  # Revisar primeros 3
            npc_id = npc["id"]

            # Los métodos deben retornar booleanos válidos
            can_trade = self.service.can_npc_trade(npc_id)
            is_hostile = self.service.is_npc_hostile(npc_id)

            assert isinstance(can_trade, bool)
            assert isinstance(is_hostile, bool)

            # Dialog debe ser string (posiblemente vacío)
            dialog = self.service.get_npc_dialog(npc_id)
            assert isinstance(dialog, str)
