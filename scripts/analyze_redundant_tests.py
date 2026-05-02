#!/usr/bin/env python3
"""Script para analizar tests redundantes basándose en cobertura de código.

Este script identifica tests redundantes usando un enfoque por archivo:
1. Ejecuta cada archivo de test individualmente
2. Compara qué archivos de código fuente cubre cada archivo de test
3. Identifica archivos de test que cubren los mismos archivos de código

Uso:
    uv run python scripts/analyze_redundant_tests.py [--sample N]

Opciones:
    --sample N: Analizar solo los primeros N archivos de test (para pruebas rápidas)

El script:
1. Obtiene la lista de archivos de test
2. Ejecuta cada archivo de test individualmente con coverage
3. Compara qué archivos de código cubre cada test
4. Identifica tests redundantes (mismo conjunto de archivos cubiertos)
5. Genera un reporte en docs/REDUNDANT_TESTS_AUTOGEN.md (fusionar o contrastar con la Parte A de docs/REDUNDANT_TESTS.md)
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_test_files() -> list[str]:
    """Obtiene la lista de archivos de test del proyecto.

    Returns:
        Lista de paths a archivos de test (ej: 'tests/test_x.py').
    """
    print("📋 Recopilando archivos de test...")
    base_dir = Path(__file__).parent.parent
    tests_dir = base_dir / "tests"

    test_files = []
    for test_file in tests_dir.rglob("test_*.py"):
        rel_path = str(test_file.relative_to(base_dir))
        test_files.append(rel_path)

    # También buscar archivos que empiecen con test_ pero en otros lugares
    for test_file in tests_dir.rglob("*.py"):
        if test_file.name.startswith("test_") and test_file not in [
            Path(base_dir / f) for f in test_files
        ]:
            rel_path = str(test_file.relative_to(base_dir))
            test_files.append(rel_path)

    test_files.sort()
    print(f"✅ Encontrados {len(test_files)} archivos de test")
    return test_files


def get_coverage_for_test_file(test_file: str, base_dir: Path) -> set[tuple[str, int]]:
    """Ejecuta un archivo de test y retorna las líneas de código que cubre.

    Args:
        test_file: Path al archivo de test (ej: 'tests/test_x.py').
        base_dir: Directorio base del proyecto.

    Returns:
        Set de tuplas (archivo, línea) cubiertas (ej: ('src/file.py', 42)).
    """
    # Limpiar coverage anterior
    subprocess.run(
        ["rm", "-f", ".coverage", "coverage.json"],
        cwd=base_dir,
        capture_output=True,
    )

    # Ejecutar test con coverage
    result = subprocess.run(
        [
            "uv",
            "run",
            "pytest",
            test_file,
            "--cov=src",
            "--cov-report=json",
            "-q",
        ],
        cwd=base_dir,
        capture_output=True,
        text=True,
        timeout=120,  # Timeout de 2 minutos por test
    )

    if result.returncode != 0:
        # Test falló, retornar set vacío
        return set()

    # Leer coverage.json
    coverage_file = base_dir / "coverage.json"
    if not coverage_file.exists():
        return set()

    try:
        with open(coverage_file) as f:
            coverage_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return set()

    # Extraer líneas cubiertas (solo archivos en src/)
    covered_lines: set[tuple[str, int]] = set()

    for file_path, file_data in coverage_data.get("files", {}).items():
        if file_path.startswith("src/"):
            for line_num in file_data.get("executed_lines", []):
                covered_lines.add((file_path, line_num))

    return covered_lines


def analyze_redundant_tests(
    test_files: list[str], base_dir: Path, sample_size: int | None = None
) -> dict[str, dict]:
    """Analiza archivos de test para identificar redundancias.

    Args:
        test_files: Lista de paths a archivos de test.
        base_dir: Directorio base del proyecto.
        sample_size: Si se proporciona, solo analizar los primeros N archivos.

    Returns:
        Diccionario con análisis de cada archivo de test:
        {
            'test_file': {
                'covered_lines': set(...),
                'unique_lines': set(...),
                'unique_count': int,
                'total_covered': int,
            }
        }
    """
    if sample_size:
        test_files = test_files[:sample_size]
        print(f"⚠️  Modo muestra: analizando solo {sample_size} archivos de test")

    print(f"\n🔍 Analizando cobertura de {len(test_files)} archivos de test...")
    print("(Esto puede tardar varios minutos)\n")

    test_coverage: dict[str, set[tuple[str, int]]] = {}

    # Paso 1: Ejecutar cada archivo de test y recopilar líneas cubiertas
    for i, test_file in enumerate(test_files, 1):
        print(f"[{i}/{len(test_files)}] Ejecutando {test_file}...", end=" ", flush=True)
        covered_lines = get_coverage_for_test_file(test_file, base_dir)
        test_coverage[test_file] = covered_lines
        print(f"✅ {len(covered_lines)} líneas cubiertas")

    # Paso 2: Calcular líneas únicas por test
    print("\n🔎 Calculando líneas únicas por archivo de test...")
    test_analysis: dict[str, dict] = {}

    # Obtener todas las líneas cubiertas por todos los tests
    all_covered_lines: set[tuple[str, int]] = set()
    for covered_lines in test_coverage.values():
        all_covered_lines.update(covered_lines)

    print(f"📊 Total de líneas cubiertas por todos los tests: {len(all_covered_lines)}")

    # Para cada test, calcular líneas únicas
    for test_file, covered_lines in test_coverage.items():
        # Líneas que solo este test cubre
        other_tests_lines = set()
        for other_test_file, other_lines in test_coverage.items():
            if other_test_file != test_file:
                other_tests_lines.update(other_lines)

        unique_lines = covered_lines - other_tests_lines

        test_analysis[test_file] = {
            "covered_lines": covered_lines,
            "unique_lines": unique_lines,
            "unique_count": len(unique_lines),
            "total_covered": len(covered_lines),
        }

    return test_analysis


def generate_report(test_analysis: dict[str, dict], output_file: Path) -> None:
    """Genera un reporte markdown con el análisis de tests redundantes.

    Args:
        test_analysis: Diccionario con análisis de cada archivo de test.
        output_file: Archivo donde escribir el reporte.
    """
    # Clasificar tests por líneas únicas
    completely_redundant = []
    nearly_redundant = []
    low_contribution = []
    significant_contribution = []

    for test_file, analysis in test_analysis.items():
        unique_count = analysis["unique_count"]
        if unique_count == 0:
            completely_redundant.append((test_file, analysis))
        elif unique_count < 10:
            nearly_redundant.append((test_file, analysis))
        elif unique_count < 50:
            low_contribution.append((test_file, analysis))
        else:
            significant_contribution.append((test_file, analysis))

    # Ordenar
    completely_redundant.sort(key=lambda x: x[1]["total_covered"])
    nearly_redundant.sort(key=lambda x: x[1]["unique_count"])
    low_contribution.sort(key=lambda x: x[1]["unique_count"])

    # Generar reporte
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_covered = sum(a["total_covered"] for a in test_analysis.values())

    report_lines = [
        "# Análisis de Tests Redundantes",
        "",
        f"**Fecha de análisis:** {now}",
        f"**Total de líneas cubiertas:** {total_covered:,}",
        "",
        "> **Nota:** Este análisis compara qué líneas de código cubre cada",
        "> archivo de test. Un archivo de test que no aporta líneas únicas",
        "> puede ser redundante, aunque valide comportamientos diferentes.",
        "",
        "## Resumen Ejecutivo",
        "",
        f"- **Total de archivos de test analizados:** {len(test_analysis)}",
        f"- **Archivos de test completamente redundantes (0 líneas únicas):** {len(completely_redundant)}",
        f"- **Archivos de test casi redundantes (<10 líneas únicas):** {len(nearly_redundant)}",
        f"- **Archivos de test con baja contribución (<50 líneas únicas):** {len(low_contribution)}",
        f"- **Archivos de test con contribución significativa (≥50 líneas únicas):** {len(significant_contribution)}",
        "",
        "---",
        "",
        "## Archivos de Test Completamente Redundantes",
        "",
        "Estos archivos de test pueden eliminarse sin reducir la cobertura total:",
        "",
    ]

    if completely_redundant:
        report_lines.append("| Archivo de Test | Líneas Cubiertas | Líneas Únicas | Recomendación |")
        report_lines.append("|-----------------|-------------------|---------------|---------------|")
        for test_file, analysis in completely_redundant:
            report_lines.append(
                f"| `{test_file}` | {analysis['total_covered']} | {analysis['unique_count']} | ⚠️ **ELIMINAR** |"
            )
    else:
        report_lines.append("✅ No se encontraron archivos de test completamente redundantes.")
        report_lines.append("")

    report_lines.extend([
        "",
        "---",
        "",
        "## Archivos de Test Casi Redundantes (<10 líneas únicas)",
        "",
        "Estos archivos de test aportan muy poca cobertura única:",
        "",
    ])

    if nearly_redundant:
        report_lines.append("| Archivo de Test | Líneas Cubiertas | Líneas Únicas | Recomendación |")
        report_lines.append("|-----------------|-------------------|---------------|---------------|")
        for test_file, analysis in nearly_redundant[:30]:  # Limitar a 30 para no hacer muy largo
            # Mostrar algunas líneas únicas de ejemplo
            unique_lines_list = list(analysis["unique_lines"])[:3]
            unique_lines_str = ", ".join([f"{f}:{l}" for f, l in unique_lines_list])
            if len(analysis["unique_lines"]) > 3:
                unique_lines_str += "..."
            report_lines.append(
                f"| `{test_file}` | {analysis['total_covered']} | {analysis['unique_count']} | 🔍 Revisar |"
            )
            if unique_lines_str:
                report_lines.append(f"| | | Ejemplo: {unique_lines_str} | |")
        if len(nearly_redundant) > 30:
            report_lines.append(f"\n... y {len(nearly_redundant) - 30} archivos más.")
    else:
        report_lines.append("✅ No se encontraron archivos de test casi redundantes.")
        report_lines.append("")

    report_lines.extend([
        "",
        "---",
        "",
        "## Archivos de Test con Baja Contribución (<50 líneas únicas)",
        "",
        f"Lista de archivos de test que aportan menos de 50 líneas únicas (mostrando primeros 50):",
        "",
    ])

    if low_contribution:
        report_lines.append("| Archivo de Test | Líneas Cubiertas | Líneas Únicas |")
        report_lines.append("|-----------------|-------------------|---------------|")
        for test_file, analysis in low_contribution[:50]:
            report_lines.append(
                f"| `{test_file}` | {analysis['total_covered']} | {analysis['unique_count']} |"
            )
        if len(low_contribution) > 50:
            report_lines.append(f"\n... y {len(low_contribution) - 50} archivos más.")
    else:
        report_lines.append("✅ No se encontraron archivos de test con baja contribución.")

    report_lines.extend([
        "",
        "---",
        "",
        "## Recomendaciones",
        "",
        "1. **Archivos completamente redundantes**: Pueden eliminarse inmediatamente si",
        "   no aportan cobertura única.",
        "2. **Archivos casi redundantes**: Revisar si las líneas únicas son críticas",
        "   antes de eliminar.",
        "3. **Este análisis es aproximado**: Dos archivos de test pueden cubrir las",
        "   mismas líneas pero validar comportamientos diferentes (diferentes datos,",
        "   casos edge, validaciones).",
        "4. **Se recomienda revisión manual**: Antes de eliminar archivos de test,",
        "   verificar que realmente validan lo mismo.",
        "",
        "## Metodología",
        "",
        "Este análisis compara qué líneas de código cubre cada archivo de test.",
        "Un archivo de test que no aporta líneas únicas (todas sus líneas están",
        "cubiertas por otros tests) es completamente redundante desde el punto de",
        "vista de cobertura.",
        "",
        "**Limitaciones:**",
        "- Este análisis no considera diferencias en datos de entrada o casos edge.",
        "- Tests que cubren las mismas líneas pero validan comportamientos diferentes",
        "  pueden aparecer como redundantes.",
        "- El análisis es por archivo de test, no por test individual.",
        "- Se recomienda revisión manual antes de eliminar archivos de test.",
        "",
    ])

    # Escribir reporte
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"\n✅ Reporte generado en: {output_file}")


def main() -> None:
    """Función principal."""
    parser = argparse.ArgumentParser(description="Analizar tests redundantes")
    parser.add_argument(
        "--sample",
        type=int,
        help="Analizar solo los primeros N archivos de test (para pruebas rápidas)",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).parent.parent

    print("=" * 70)
    print("🔍 Análisis de Tests Redundantes")
    print("=" * 70)
    print()

    # Paso 1: Obtener archivos de test
    test_files = get_test_files()
    if not test_files:
        print("❌ No se encontraron archivos de test.")
        sys.exit(1)

    if args.sample:
        test_files = test_files[:args.sample]
        print(f"⚠️  Modo muestra: analizando solo {len(test_files)} archivos de test")

    # Paso 2: Analizar redundancias
    test_analysis = analyze_redundant_tests(test_files, base_dir, args.sample)

    # Paso 3: Generar reporte
    output_file = base_dir / "docs" / "REDUNDANT_TESTS_AUTOGEN.md"
    generate_report(test_analysis, output_file)

    print("\n" + "=" * 70)
    print("✅ Análisis completado")
    print("=" * 70)


if __name__ == "__main__":
    main()
