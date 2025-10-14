"""Tests para los enums de tipos de items."""

from src.item_types import ObjType, TipoPocion


class TestObjType:
    """Tests para el enum ObjType."""

    def test_obj_type_values(self):
        """Verifica que los valores de ObjType sean correctos."""
        assert ObjType.COMIDA == 1
        assert ObjType.ARMAS == 2
        assert ObjType.ARMADURAS == 3
        assert ObjType.POCIONES == 11
        assert ObjType.ESCUDOS == 16
        assert ObjType.CASCOS == 17
        assert ObjType.ANILLOS == 18

    def test_obj_type_all_values(self):
        """Verifica que todos los tipos estén definidos."""
        expected_types = [
            "COMIDA",
            "ARMAS",
            "ARMADURAS",
            "ARBOLES",
            "DINERO",
            "PUERTAS",
            "CONTENEDORES",
            "CARTELES",
            "LLAVES",
            "FOROS",
            "POCIONES",
            "LIBROS",
            "BEBIDA",
            "LENA",
            "FOGATA",
            "ESCUDOS",
            "CASCOS",
            "ANILLOS",
            "TELEPORT",
            "MUEBLES",
            "JOYAS",
            "YACIMIENTO",
            "METALES",
            "PERGAMINOS",
            "AURA",
            "INSTRUMENTOS_MUSICALES",
            "YUNQUE",
            "FRAGUA",
            "GEMAS",
            "FLORES",
            "BARCOS",
            "FLECHAS",
            "BOTELLAS_VACIAS",
            "BOTELLAS_LLENAS",
            "MANCHAS",
        ]

        obj_type_names = [member.name for member in ObjType]
        assert len(obj_type_names) == 35

        for expected in expected_types:
            assert expected in obj_type_names

    def test_obj_type_is_int_enum(self):
        """Verifica que ObjType sea un IntEnum."""
        assert isinstance(ObjType.COMIDA, int)
        assert ObjType.COMIDA + 1 == 2


class TestTipoPocion:
    """Tests para el enum TipoPocion."""

    def test_tipo_pocion_values(self):
        """Verifica que los valores de TipoPocion sean correctos."""
        assert TipoPocion.AGILIDAD == 1
        assert TipoPocion.FUERZA == 2
        assert TipoPocion.HP == 3
        assert TipoPocion.MANA == 4
        assert TipoPocion.CURA_VENENO == 5
        assert TipoPocion.INVISIBLE == 6

    def test_tipo_pocion_all_values(self):
        """Verifica que todos los tipos de poción estén definidos."""
        assert len(list(TipoPocion)) == 6

    def test_tipo_pocion_is_int_enum(self):
        """Verifica que TipoPocion sea un IntEnum."""
        assert isinstance(TipoPocion.HP, int)
        assert TipoPocion.HP + 1 == 4
