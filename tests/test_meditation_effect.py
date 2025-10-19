"""Tests básicos para MeditationEffect."""

from src.meditation_effect import MeditationEffect


class TestMeditationEffect:
    """Tests básicos para MeditationEffect."""

    def test_init_default(self) -> None:
        """Test de inicialización con valores por defecto."""
        effect = MeditationEffect()

        assert effect.interval_seconds == 3.0

    def test_init_custom_interval(self) -> None:
        """Test de inicialización con intervalo personalizado."""
        effect = MeditationEffect(interval_seconds=5.0)

        assert effect.interval_seconds == 5.0

    def test_get_interval_seconds(self) -> None:
        """Test de obtención del intervalo."""
        effect = MeditationEffect(interval_seconds=2.5)

        assert effect.get_interval_seconds() == 2.5

    def test_get_name(self) -> None:
        """Test de obtención del nombre del efecto."""
        effect = MeditationEffect()

        assert effect.get_name() == "Meditation"
