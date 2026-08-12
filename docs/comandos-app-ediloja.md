# Comandos de App-EdiLoja

**Guía de referencia rápida**

---

## 1. Empezar a trabajar

Cada terminal nueva necesita esto. Es el error más común: ejecutar algo sin el entorno activo.

```bash
cd ~/Desktop/App_Creacion-guias
source .venv/bin/activate
docker compose up -d
```

**Comprobar que el entorno está activo:**

```bash
which python
```

Debe responder una ruta que termine en `App_Creacion-guias/.venv/bin/python`.
Si responde `/usr/local/bin/python3`, el entorno **no** está activo.

La señal rápida: el prompt empieza con `(.venv)`.

**Atajo opcional** — agregar a `~/.zshrc` para escribir solo `ediloja`:

```bash
ediloja() {
  cd ~/Desktop/App_Creacion-guias && source .venv/bin/activate
}
```

---

## 2. Levantar el servidor

```bash
uvicorn app.principal:app --reload --port 8000
```

`--reload` reinicia al guardar cualquier archivo. **Solo para desarrollo.**

Dejar esa terminal corriendo y abrir otra para el resto de comandos.

| Dirección | Qué muestra |
|---|---|
| http://localhost:8000/ingresar | Pantalla de acceso |
| http://localhost:8000/docs | Documentación automática de la API |
| http://localhost:8000/salud | Estado del proceso |
| http://localhost:8000/listo | Estado de base de datos y Redis |

---

## 3. Docker: base de datos y Redis

```bash
docker compose up -d          # levantar
docker compose ps             # ver estado (debe decir "healthy")
docker compose stop           # detener sin borrar
docker compose down           # detener y eliminar contenedores
docker compose logs db        # ver errores de PostgreSQL
docker compose logs redis     # ver errores de Redis
```

**Borrar TODOS los datos y empezar de cero:**

```bash
docker compose down -v
docker compose up -d
alembic upgrade head
python -m app.cli.sembrar_roles
```

La `-v` elimina el volumen. **No hay vuelta atrás.**

**Contenedores huérfanos de otro proyecto:**

```bash
docker ps -a --filter "name=ediloja"
docker rm -f ediloja-db ediloja-redis
```

---

## 4. Migraciones de base de datos

El patrón completo, siempre en este orden:

```bash
# 1. Verificar que el modelo no tiene errores de sintaxis
python -c "from app.modelos import NombreDelModelo; print('OK')"

# 2. Generar la migración
alembic revision --autogenerate -m "descripcion corta"

# 3. LEERLA antes de aplicar
cat migraciones/versions/*descripcion*.py

# 4. Aplicar
alembic upgrade head
```

**El paso 3 no se salta.** Alembic acierta casi siempre; el "casi" es el que borra una columna con datos.

**Otros comandos útiles:**

```bash
alembic current               # en qué migración está la base
alembic history               # todas las migraciones
alembic downgrade -1          # retroceder una
```

**Si se genera una migración vacía** (contiene solo `pass`), es porque no había cambios que detectar:

```bash
alembic downgrade -1
rm migraciones/versions/ARCHIVO_VACIO.py
alembic current
```

---

## 5. Consultar la base de datos

```bash
docker compose exec db psql -U ediloja_app -d ediloja
```

Dentro de `psql`:

| Comando | Qué hace |
|---|---|
| `\dt` | Listar tablas |
| `\d usuario` | Estructura de una tabla |
| `\q` | Salir |

**Consultas de un solo golpe, sin entrar:**

```bash
# Ver usuarios
docker compose exec db psql -U ediloja_app -d ediloja \
  -c "SELECT correo, estado, intentos_fallidos, bloqueado_hasta FROM usuario;"

# Ver roles
docker compose exec db psql -U ediloja_app -d ediloja \
  -c "SELECT codigo, nombre FROM rol ORDER BY codigo;"

# Ver auditoría reciente
docker compose exec db psql -U ediloja_app -d ediloja \
  -c "SELECT accion, detalles, ip, ocurrido_en FROM registro_auditoria ORDER BY ocurrido_en DESC LIMIT 10;"

# Ver sesiones activas
docker compose exec db psql -U ediloja_app -d ediloja \
  -c "SELECT usuario_id, emitida_en, expira_en, revocada_en FROM sesion ORDER BY emitida_en DESC;"
```

---

## 6. Comandos de la aplicación

```bash
# Crear los seis roles (se puede repetir sin duplicar)
python -m app.cli.sembrar_roles

# Crear el primer administrador (falla si ya existe uno)
python -m app.cli.crear_admin "correo@utpl.edu.ec" "Nombres" "Apellidos"

# Fijar contraseña — SOLO desarrollo
python -m app.cli.activar_local "correo@utpl.edu.ec" "contrasena-de-12-o-mas"
```

**`activar_local` también sirve para desbloquear:** pone los intentos fallidos en cero y quita el bloqueo.

Si la contraseña lleva `$`, `!` o `#`, usar **comillas simples**:

```bash
python -m app.cli.activar_local "correo@utpl.edu.ec" 'Mi$Contra#Larga'
```

---

## 7. Docker: la aplicación

```bash
# Construir la imagen
docker build -t ediloja:local .

# Ver tamaño
docker images ediloja:local

# Verificar que NO corre como root (debe decir uid=10001)
docker run --rm ediloja:local id
```

**Ejecutar el contenedor contra la base local:**

```bash
docker run --rm -p 8001:8000 \
  -e ENTORNO=desarrollo \
  -e URL_BASE_DATOS="postgresql+psycopg://ediloja_app:clave_local_desarrollo@host.docker.internal:5436/ediloja" \
  -e URL_REDIS="redis://host.docker.internal:6382/0" \
  -e CLAVE_SECRETA="una-clave-de-al-menos-32-caracteres-aqui" \
  ediloja:local
```

Puerto **8001** para no chocar con uvicorn. Dentro del contenedor, `localhost` es el contenedor mismo: por eso se usa `host.docker.internal`.

```bash
curl -s localhost:8001/salud
curl -s localhost:8001/listo
```

---

## 8. Git

**El ciclo de cada hito:**

```bash
git status                    # qué cambió
git diff                      # qué dice exactamente
git add archivo1 archivo2     # agregar
git status                    # CONFIRMAR que están en verde
git commit -m "Hito N: descripcion"
git push
```

**Reglas que conviene sostener:**

- Se hace commit cuando algo **funciona**, no cuando está escrito
- `git status` después de `git add`, siempre
- Nunca usar `2>/dev/null` en comandos de Git: esconde errores
- Si `git status` muestra `.env`, **detenerse**

**Verificar que un archivo está protegido:**

```bash
git check-ignore -v .env
```

**Si el push es rechazado:**

```bash
git fetch origin
git log --oneline origin/main       # ver qué hay del otro lado
git pull --rebase origin main
git push
```

---

## 9. Pruebas rápidas

**Configuración válida:**

```bash
python -c "from app.configuracion import configuracion; print(configuracion.entorno)"
```

**Que la validación rechaza lo inválido** (debe FALLAR):

```bash
ENTORNO=produccion_falso python -c "from app.configuracion import configuracion"
VARIABLE_INVENTADA=hola python -c "from app.configuracion import configuracion"
```

**Ciclo de login por terminal:**

```bash
rm -f /tmp/galletas

curl -s -c /tmp/galletas -X POST localhost:8000/ingresar \
  -d "correo=CORREO" -d "password=CONTRASENA" > /dev/null

cat /tmp/galletas

curl -s -b /tmp/galletas -o /dev/null -w "GET /inicio -> %{http_code}\n" \
  localhost:8000/inicio
```

Debe terminar en `200`.

**Que CSRF protege** (debe dar 403):

```bash
curl -s -o /dev/null -w "sin token -> %{http_code}\n" \
  -X POST localhost:8000/ingresar \
  -d "correo=CORREO" -d "password=CONTRASENA"
```

**Que las contraseñas no filtran por tiempo:**

```bash
python -c "
import time
from app.seguridad.passwords import generar_hash, verificar
h = generar_hash('contrasena-de-prueba-larga')
verificar('x', h); verificar('x', None)
def medir(arg, n=10):
    t = time.perf_counter()
    for _ in range(n): verificar('mala', arg)
    return (time.perf_counter() - t) / n * 1000
print(f'usuario existe:    {medir(h):.1f} ms')
print(f'usuario no existe: {medir(None):.1f} ms')
"
```

Los dos tiempos deben ser parecidos.

---

## 10. Cuando algo falla

| Síntoma | Primera cosa que revisar |
|---|---|
| `command not found: python` | El entorno virtual no está activo → `source .venv/bin/activate` |
| Un comando se comporta raro | `which alembic` — puede estar corriendo el del sistema |
| `connection refused` | Puertos de `.env` y `docker-compose.yml` no coinciden |
| `service "db" is not running` | `docker ps -a` — puede haber un contenedor huérfano |
| `Extra inputs are not permitted` | Variable en `.env` no declarada en `Configuracion` |
| `IndentationError` | Se perdieron espacios al pegar. Cuatro espacios, no tabulaciones |
| El login rechaza credenciales correctas | Revisar `bloqueado_hasta` en la tabla `usuario` |
| Página 404 | Falta `include_router` en `app/principal.py` |
| Subrayado rojo en el editor | Cosmético. El intérprete de Pyrefly, no el código |

**Regla general:** cuando un comando falle de forma incomprensible, mirar primero de dónde salió el ejecutable con `which`.

---

## 11. Puertos del proyecto

| Servicio | Puerto local | Puerto interno |
|---|--:|--:|
| PostgreSQL | 5436 | 5432 |
| Redis | 6382 | 6379 |
| uvicorn | 8000 | — |
| Contenedor de pruebas | 8001 | 8000 |

El puerto de la izquierda se elige; el de la derecha es fijo por el programa.
**Debe coincidir con lo que dice `.env`.**

---

## 12. Archivos que nunca se suben a Git

```
.env              contraseñas y claves
.venv/            entorno virtual, se reconstruye
__pycache__/      archivos temporales de Python
.DS_Store         basura de macOS
```

Todos están en `.gitignore`. Si alguno aparece en `git status`, algo se rompió.
