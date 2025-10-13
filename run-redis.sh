#!/usr/bin/env bash
set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

CONTAINER_NAME="pyao-redis-dev"
IMAGE_NAME="pyao-redis"

# Función de limpieza
cleanup() {
    echo -e "\n${YELLOW}🧹 Limpiando...${NC}"
    
    # Detener y eliminar contenedor
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo -e "${YELLOW}⏹️  Deteniendo contenedor ${CONTAINER_NAME}...${NC}"
        docker stop "${CONTAINER_NAME}" > /dev/null 2>&1 || true
        
        echo -e "${YELLOW}🗑️  Eliminando contenedor ${CONTAINER_NAME}...${NC}"
        docker rm "${CONTAINER_NAME}" > /dev/null 2>&1 || true
    fi
    
    echo -e "${GREEN}✅ Limpieza completada${NC}"
    exit 0
}

# Capturar señales de interrupción
trap cleanup SIGINT SIGTERM EXIT

echo -e "${GREEN}🚀 Iniciando Redis para PyAO Server${NC}"
echo ""

# Verificar si la imagen existe, si no, construirla
if ! docker images --format '{{.Repository}}' | grep -q "^${IMAGE_NAME}$"; then
    echo -e "${YELLOW}📦 Construyendo imagen ${IMAGE_NAME}...${NC}"
    docker build -t "${IMAGE_NAME}" ./redis
    echo -e "${GREEN}✅ Imagen construida${NC}"
    echo ""
fi

# Verificar si ya existe un contenedor con el mismo nombre
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${YELLOW}⚠️  Contenedor ${CONTAINER_NAME} ya existe. Eliminando...${NC}"
    docker stop "${CONTAINER_NAME}" > /dev/null 2>&1 || true
    docker rm "${CONTAINER_NAME}" > /dev/null 2>&1 || true
fi

# Ejecutar Redis
echo -e "${GREEN}🐳 Iniciando contenedor Redis...${NC}"
docker run --rm --name "${CONTAINER_NAME}" -p 6379:6379 "${IMAGE_NAME}" &

# Esperar a que Redis esté listo
echo -e "${YELLOW}⏳ Esperando a que Redis esté listo...${NC}"
sleep 2

# Verificar que Redis responde
if docker exec "${CONTAINER_NAME}" redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Redis está listo y respondiendo en localhost:6379${NC}"
    echo ""
    echo -e "${GREEN}📊 Comandos útiles:${NC}"
    echo -e "  ${YELLOW}•${NC} Ver logs: docker logs -f ${CONTAINER_NAME}"
    echo -e "  ${YELLOW}•${NC} Redis CLI: docker exec -it ${CONTAINER_NAME} redis-cli"
    echo -e "  ${YELLOW}•${NC} Monitorear: docker exec -it ${CONTAINER_NAME} redis-cli monitor"
    echo ""
    echo -e "${RED}⚠️  Presiona Ctrl+C para detener Redis y limpiar todo${NC}"
    echo ""
else
    echo -e "${RED}❌ Error: Redis no responde${NC}"
    exit 1
fi

# Mantener el script corriendo y mostrar logs
docker logs -f "${CONTAINER_NAME}"
