#!/usr/bin/env bash
# Script para ejecutar tests y verificaciones de código
set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Valores por defecto
SKIP_FORMAT=false
SKIP_MYPY=false
COVERAGE=false
PARALLEL=4
TEST_ARGS=""
RUFF_ONLY=false

show_help() {
    echo "Uso: $0 [opciones] [-- pytest_args]"
    echo ""
    echo "Opciones:"
    echo "  -h, --help       Muestra esta ayuda"
    echo "  -q, --quick      Modo rápido: solo tests (sin format/lint/mypy)"
    echo "  -f, --no-format  Omitir auto-formateo"
    echo "  -m, --no-mypy    Omitir verificación de tipos con mypy"
    echo "  -c, --coverage   Ejecutar con cobertura de código"
    echo "  -p, --parallel N Número de workers para pytest (default: 4)"
    echo "  --ruff-only      Solo ejecutar ruff check y salir"
    echo ""
    echo "Ejemplos:"
    echo "  $0                      # Ejecutar todo"
    echo "  $0 -q                   # Solo tests rápidos"
    echo "  $0 -c                   # Con cobertura"
    echo "  $0 -- tests/test_foo.py # Tests específicos"
    echo "  $0 -- -k 'test_login'   # Tests que coincidan con patrón"
}

# Parsear argumentos
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -q|--quick)
            SKIP_FORMAT=true
            SKIP_MYPY=true
            shift
            ;;
        -f|--no-format)
            SKIP_FORMAT=true
            shift
            ;;
        -m|--no-mypy)
            SKIP_MYPY=true
            shift
            ;;
        -c|--coverage)
            COVERAGE=true
            shift
            ;;
        -p|--parallel)
            PARALLEL="$2"
            shift 2
            ;;
        --ruff-only)
            RUFF_ONLY=true
            SKIP_FORMAT=true
            SKIP_MYPY=true
            shift
            ;;
        --)
            shift
            TEST_ARGS="$*"
            break
            ;;
        *)
            TEST_ARGS="$*"
            break
            ;;
    esac
done

# Timer (LC_NUMERIC=C para usar punto decimal)
start_time() { date +%s.%N; }
elapsed() {
    local end=$(date +%s.%N)
    LC_NUMERIC=C printf "%.1fs" "$(echo "$end - $1" | bc)"
}

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  PyAO Server - Test Suite${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Versiones (compacto)
echo -e "${YELLOW}📦 Versiones:${NC} Python $(uv run python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")') | uv $(uv --version | cut -d' ' -f2) | pytest $(uv run pytest --version | head -1 | cut -d' ' -f2)"
echo ""

# Solo ruff check
if [[ "$RUFF_ONLY" == true ]]; then
    t=$(start_time)
    echo -e "${YELLOW}🔍 Ruff check (solo lint)...${NC}"
    uv run ruff check src tests --quiet
    echo -e "${GREEN}   ✓ Sin errores de linting${NC} ($(elapsed $t))"
    exit 0
fi

# Auto-format
if [[ "$SKIP_FORMAT" == false ]]; then
    t=$(start_time)
    echo -e "${YELLOW}🎨 Formateando código...${NC}"
    uv run ruff format . --quiet
    uv run ruff check --fix --quiet . 2>/dev/null || true
    echo -e "${GREEN}   ✓ Formateo completado${NC} ($(elapsed $t))"
    echo ""
fi

# Tests
t=$(start_time)
echo -e "${YELLOW}🧪 Ejecutando tests...${NC}"

PYTEST_CMD="uv run pytest"
if [[ "$COVERAGE" == true ]]; then
    PYTEST_CMD="$PYTEST_CMD --cov=src --cov-report=term-missing --cov-report=html"
fi
PYTEST_CMD="$PYTEST_CMD -n $PARALLEL"

if [[ -n "$TEST_ARGS" ]]; then
    $PYTEST_CMD $TEST_ARGS
else
    $PYTEST_CMD tests/
fi
echo -e "${GREEN}   ✓ Tests pasados${NC} ($(elapsed $t))"
echo ""

# Ruff lint
t=$(start_time)
echo -e "${YELLOW}🔍 Verificando linting...${NC}"
uv run ruff check src tests --quiet
echo -e "${GREEN}   ✓ Sin errores de linting${NC} ($(elapsed $t))"
echo ""

# Mypy
if [[ "$SKIP_MYPY" == false ]]; then
    t=$(start_time)
    echo -e "${YELLOW}🔬 Verificando tipos (mypy)...${NC}"
    uv run mypy src tests --no-error-summary 2>/dev/null || uv run mypy src tests
    echo -e "${GREEN}   ✓ Sin errores de tipos${NC} ($(elapsed $t))"
    echo ""
fi

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ Todas las verificaciones pasaron${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
