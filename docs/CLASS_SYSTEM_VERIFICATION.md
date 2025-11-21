# Verificación del Sistema de Clases

Guía para verificar que el sistema de clases funciona correctamente.

## 📋 Skills por Clase

### 🔮 Mago (ID: 1)
- **magia**: 10
- **robustez**: 5
- **agilidad**: 3

### ⚔️ Clérigo (ID: 2)
- **magia**: 8
- **robustez**: 7
- **agilidad**: 5

### 🛡️ Guerrero (ID: 3)
- **robustez**: 10
- **agilidad**: 7
- **magia**: 2

### 🏹 Cazador (ID: 10)
- **agilidad**: 10
- **robustez**: 7
- **supervivencia**: 5
- **magia**: 2

## 🔍 Cómo Verificar

### 1. En el Juego (Cliente)

**Crear un personaje:**
1. Crea una cuenta nueva
2. Selecciona una clase (Mago, Clérigo, Guerrero, Cazador)
3. Completa la creación del personaje

**Verificar skills:**
- En el cliente, usa el comando para ver skills (si existe)
- O verifica en los logs del servidor

### 2. En Redis (Directo)

**Conectar a Redis:**
```bash
redis-cli
```

**Ver skills de un usuario:**
```redis
HGETALL player:1:skills
```

**Ver clase del usuario:**
```redis
HGET account:username:data char_job
```

**Ejemplo de salida:**
```
1) "magia"
2) "10"
3) "robustez"
4) "5"
5) "agilidad"
6) "3"
```

### 3. Usando el Script de Verificación

**Ver skills por clase:**
```bash
uv run python scripts/check_class_skills.py
```

**Ver skills de un usuario específico:**
```bash
uv run python scripts/check_class_skills.py 1
```

### 4. En los Logs del Servidor

Al crear un personaje, deberías ver en los logs:

```
INFO - Skills iniciales asignadas para user_id 1 (clase Mago): {'magia': 10, 'robustez': 5, 'agilidad': 3}
INFO - Atributos guardados en Redis para user_id 1 (base={'strength': 18, ...}, final={'strength': 19, ...})
```

## 📊 Estructura en Redis

### Skills del Jugador
**Key:** `player:{user_id}:skills`  
**Tipo:** Hash  
**Campos:**
- `magia` (int)
- `robustez` (int)
- `agilidad` (int)
- `talar` (int)
- `pesca` (int)
- `mineria` (int)
- `herreria` (int)
- `carpinteria` (int)
- `supervivencia` (int)

### Clase del Personaje
**Key:** `account:{username}:data`  
**Campo:** `char_job` (int) - ID de la clase (1=Mago, 2=Clérigo, 3=Guerrero, 10=Cazador)

## ✅ Checklist de Verificación

- [ ] Crear personaje Mago → Verificar que tiene `magia=10`
- [ ] Crear personaje Guerrero → Verificar que tiene `robustez=10`
- [ ] Crear personaje Clérigo → Verificar que tiene `magia=8, robustez=7`
- [ ] Crear personaje Cazador → Verificar que tiene `agilidad=10, supervivencia=5`
- [ ] Verificar en Redis que las skills se guardaron correctamente
- [ ] Verificar que los atributos base se aplicaron (STR, AGI, INT, CHA, CON)
- [ ] Verificar que el HP inicial es correcto según la clase (usando modificadores)

## 🐛 Troubleshooting

### No se guardan skills
- Verificar que `ClassService` se inicializa correctamente
- Verificar que `classes.toml` existe y tiene datos válidos
- Revisar logs del servidor para errores

### Skills incorrectas
- Verificar que el `class_id` coincide con el `char_job` en Redis
- Verificar que `classes.toml` tiene las skills correctas para cada clase

### Atributos incorrectos
- Verificar que se aplican atributos base de clase
- Verificar que se aplican modificadores raciales después
- Revisar logs para ver el flujo completo

---

**Última actualización:** 2025-01-30

