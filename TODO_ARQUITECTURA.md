# TODOs de Arquitectura y Diseño

## 🔴 Alta Prioridad

### 1. Sistema de Carga de Recursos
**Problema:** Apenas se inicia Redis se cargan los recursos desde los archivos TOML y maps, luego solo se consulta la base Redis. Este comportamiento debe ser revisado.

**Ubicación:** `src/server.py`, `src/npc_service.py`, `src/spell_catalog.py`

**Comportamiento Actual:**
- NPCs se cargan desde `npcs.toml` → Redis al iniciar
- Hechizos se cargan desde `spells.toml` al iniciar
- Mapas se cargan desde archivos `.map` al iniciar
- Después solo se consulta Redis

**Problemas:**
- No hay sincronización entre archivos y Redis
- Cambios en archivos requieren reiniciar servidor
- No hay versionado de datos
- Puede haber inconsistencias

**Soluciones Propuestas:**
1. **Opción A - Source of Truth en Archivos:**
   - Archivos TOML/maps son la fuente de verdad
   - Redis solo como cache
   - Recargar desde archivos periódicamente o con comando

2. **Opción B - Source of Truth en Redis:**
   - Migración inicial desde archivos
   - Después todo se edita en Redis
   - Exportar a archivos para backup

3. **Opción C - Híbrido:**
   - Archivos para configuración estática (NPCs, hechizos)
   - Redis para estado dinámico (HP, posición, items)
   - Sincronización clara entre ambos

**Recomendación:** Opción C - Separar configuración estática de estado dinámico

**Tareas:**
- [ ] Documentar qué datos son estáticos vs dinámicos
- [ ] Implementar sistema de versionado para configs
- [ ] Agregar comando admin para recargar configs
- [ ] Separar repositorios de configuración vs estado

---

### 2. Separación de Capas y Responsabilidades
**Problema:** Revisar la separación de capas y responsabilidades en la arquitectura actual.

**Ubicación:** Todo el proyecto, especialmente `src/server.py`

**Problemas Identificados:**
- `Server` tiene demasiadas responsabilidades
- Mezcla de lógica de negocio y configuración
- Dependencias circulares potenciales
- Tasks acceden directamente a repositorios

**Arquitectura Actual:**
```
Server
  ├── Repositories (Redis)
  ├── Services (Lógica de negocio)
  ├── Tasks (Handlers de packets)
  └── Managers (Estado en memoria)
```

**Problemas:**
- Server inicializa todo manualmente
- Tasks tienen muchas dependencias
- No hay inyección de dependencias clara
- Difícil de testear

**Soluciones Propuestas:**
1. **Patrón Service Locator:**
   ```python
   class ServiceContainer:
       def __init__(self):
           self.repositories = {}
           self.services = {}
           self.managers = {}
   ```

2. **Dependency Injection:**
   - Usar biblioteca como `dependency-injector`
   - Configurar dependencias en un solo lugar
   - Tasks reciben solo lo que necesitan

3. **Arquitectura en Capas Clara:**
   ```
   Presentation (Tasks/Packets)
       ↓
   Application (Services)
       ↓
   Domain (Models/Entities)
       ↓
   Infrastructure (Repositories/Redis)
   ```

**Recomendación:** Implementar Service Container simple + Arquitectura en capas

**Tareas:**
- [ ] Crear ServiceContainer para gestionar dependencias
- [ ] Separar lógica de negocio de Tasks a Services
- [ ] Definir interfaces claras entre capas
- [ ] Refactorizar Server.start() para usar container
- [ ] Agregar tests unitarios por capa

---

### 3. Inicialización de Objetos con Valores None
**Problema:** Los objetos deberían crearse lo más completos posibles y funcionales. Analizar si se puede cambiar el orden y reducir la cantidad de None.

**Ubicación:** `src/server.py` - método `__init__` y `start()`

**Código Actual:**
```python
def __init__(self):
    self.redis_client: RedisClient | None = None
    self.player_repo: PlayerRepository | None = None
    self.account_repo: AccountRepository | None = None
    self.map_manager: MapManager | None = None
    # ... 15+ atributos más como None
```

**Problemas:**
- Objetos en estado inválido hasta que se llama `start()`
- Type checking requiere verificar None constantemente
- Fácil olvidar inicializar algo
- No hay garantía de orden de inicialización
- Difícil de testear

**Soluciones Propuestas:**

1. **Builder Pattern:**
   ```python
   class ServerBuilder:
       async def build(self) -> Server:
           redis = await self._init_redis()
           repos = await self._init_repositories(redis)
           services = await self._init_services(repos)
           return Server(redis, repos, services)
   ```

2. **Factory con Async:**
   ```python
   class ServerFactory:
       @staticmethod
       async def create() -> Server:
           # Inicializar todo en orden correcto
           # Retornar Server completamente funcional
   ```

3. **Lazy Initialization con Properties:**
   ```python
   @property
   def player_repo(self) -> PlayerRepository:
       if self._player_repo is None:
           raise RuntimeError("Server not started")
       return self._player_repo
   ```

4. **Separar Configuración de Runtime:**
   ```python
   class ServerConfig:
       # Solo configuración inmutable
       
   class ServerRuntime:
       # Estado mutable, siempre válido
   ```

**Recomendación:** Builder Pattern + Separar Config de Runtime

**Ejemplo de Implementación:**
```python
class ServerBuilder:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
    
    async def build(self) -> Server:
        # 1. Redis (base de todo)
        redis = RedisClient()
        await redis.connect()
        
        # 2. Repositorios (dependen de Redis)
        repos = await self._build_repositories(redis)
        
        # 3. Managers (estado en memoria)
        managers = await self._build_managers(repos)
        
        # 4. Services (lógica de negocio)
        services = await self._build_services(repos, managers)
        
        # 5. Server (completamente inicializado)
        return Server(
            redis=redis,
            repositories=repos,
            managers=managers,
            services=services,
            host=self.host,
            port=self.port
        )
```

**Tareas:**
- [ ] Crear ServerBuilder class
- [ ] Separar ServerConfig (inmutable) de ServerRuntime (mutable)
- [ ] Eliminar todos los `| None` innecesarios
- [ ] Garantizar orden de inicialización correcto
- [ ] Agregar validación de dependencias
- [ ] Actualizar tests para usar builder

---

## 🟡 Media Prioridad

### 4. Gestión de Configuración
- [ ] Centralizar configuración en un solo lugar
- [ ] Validar configuración al inicio
- [ ] Soporte para múltiples entornos (dev, prod)
- [ ] Hot-reload de configuración no crítica

### 5. Logging y Observabilidad
- [ ] Estructurar logs (JSON)
- [ ] Agregar métricas (Prometheus)
- [ ] Tracing distribuido
- [ ] Health checks

### 6. Testing
- [ ] Tests de integración por capa
- [ ] Mocks para Redis
- [ ] Tests de carga
- [ ] Coverage > 80%

---

## 🟢 Baja Prioridad

### 7. Documentación
- [ ] Diagramas de arquitectura
- [ ] Guía de contribución
- [ ] ADRs (Architecture Decision Records)

### 8. Performance
- [ ] Profiling del servidor
- [ ] Optimización de queries a Redis
- [ ] Connection pooling
- [ ] Caching estratégico

---

## 📝 Notas

**Fecha de Creación:** 2025-10-17
**Última Actualización:** 2025-10-17

**Priorización:**
1. Sistema de carga de recursos (afecta mantenibilidad)
2. Separación de capas (afecta escalabilidad)
3. Inicialización de objetos (afecta robustez)

**Impacto Estimado:**
- Refactorización grande: 2-3 semanas
- Mejora significativa en mantenibilidad
- Reducción de bugs por estado inválido
- Mejor testabilidad
