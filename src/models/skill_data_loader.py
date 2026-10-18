"""Carga las reglas de habilidades en Redis antes de aceptar jugadores."""

import json
import tomllib

from src.runtime_paths import data_dir
from src.utils.base_data_loader import BaseDataLoader

MAX_SKILL = 100
MAX_EXTENSION_BONUS = 0.5

SKILL_RULES_KEY = "config:skills:rules"


class SkillDataLoader(BaseDataLoader):
    """Reglas versionadas en TOML; durante la partida se consulta sólo Redis."""

    def get_name(self) -> str:
        """Identifica el catálogo.

        Returns:
            Nombre del conjunto de reglas.
        """
        return "Skill Rules"

    async def load(self) -> None:
        """Valida el archivo inicial y publica su versión de reglas.

        Raises:
            ValueError: Si las reglas no respetan los límites del protocolo.
        """
        rules = tomllib.loads((data_dir() / "skills.toml").read_text(encoding="utf-8"))
        if (
            rules["version"] != 1
            or rules["xp_base"] < 1
            or not rules["natural_caps"]
            or any(not 0 <= value <= MAX_SKILL for value in rules["natural_caps"])
            or any(
                not 0 <= rules[key] <= MAX_EXTENSION_BONUS
                for key in ("robustness_max_mitigation", "agility_max_evasion")
            )
        ):
            message = "Reglas de habilidades inválidas"
            raise ValueError(message)
        await self.redis_client.set(SKILL_RULES_KEY, json.dumps(rules))
