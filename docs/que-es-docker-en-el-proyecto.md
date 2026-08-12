# Docker en App-EdiLoja

**Documento explicativo** · 12 de agosto de 2026

---

## 1. La idea en una frase

Docker empaqueta la aplicación junto con **todo lo que necesita para funcionar** —el lenguaje, las librerías, la configuración— en un solo bloque cerrado que corre igual en cualquier computador.

---

## 2. El problema que resuelve

### Sin Docker

Para instalar la aplicación en un servidor nuevo hay que:

1. Instalar Python en la versión correcta
2. Instalar once librerías, cada una en su versión exacta
3. Configurar variables de entorno
4. Rezar para que el servidor no tenga otra versión de Python que estorbe

Y cuando algo falla, aparece la frase más cara del desarrollo de software:

> *"En mi máquina funciona."*

### Con Docker

Se entrega **una imagen**. El servidor la ejecuta. Punto.

No importa si el servidor es Linux, si tiene otra versión de Python, o si nunca tuvo Python. La imagen trae lo suyo.

---

## 3. Dos palabras que conviene distinguir

| Palabra | Qué es | Analogía |
|---|---|---|
| **Imagen** | El paquete cerrado. No corre, solo existe | Un molde |
| **Contenedor** | La imagen ejecutándose | La pieza salida del molde |

De una imagen se pueden crear muchos contenedores idénticos. Es exactamente lo que hará AWS cuando haya muchos docentes trabajando a la vez: levanta tres o cinco copias del mismo molde.

---

## 4. Qué hay dentro de nuestra imagen

```
ediloja:local  ·  291 MB

├── Python 3.13
├── Las 11 librerías del proyecto
│     FastAPI, SQLAlchemy, Alembic, Argon2, Redis...
├── El código de la aplicación
└── Un usuario sin privilegios llamado "app"
```

**Lo que NO hay dentro, a propósito:**

- Contraseñas
- La clave de OpenAI
- La dirección de la base de datos
- El archivo `.env`

Esos datos se inyectan **al momento de ejecutar**, nunca se hornean en la imagen.

---

## 5. Por qué la imagen no lleva secretos

Es la decisión de seguridad más importante de todo el archivo.

Una imagen se sube a un repositorio, se copia entre entornos y se comparte con el equipo. Si la contraseña de la base viviera adentro, **cualquiera que obtenga la imagen obtiene la contraseña**, y borrarla después no sirve: queda en el historial.

Separando las dos cosas:

```
La imagen dice:      "necesito una dirección de base de datos"
El servidor le dice: "aquí está, es esta"
```

La misma imagen sirve para desarrollo, pruebas y producción. Solo cambia lo que se le entrega al arrancar.

---

## 6. Por qué se construye en dos etapas

El archivo `Dockerfile` tiene dos partes, y esto sorprende al verlo por primera vez.

**Etapa 1 — El taller.** Instala herramientas de compilación y prepara las librerías. Es un espacio de trabajo desordenado y pesado.

**Etapa 2 — El producto.** Se lleva únicamente el resultado de la etapa anterior. Las herramientas se quedan atrás.

**El beneficio es doble:**

| | Sin dos etapas | Con dos etapas |
|---|--:|--:|
| Tamaño | ~600 MB | **291 MB** |
| Herramientas de compilación incluidas | Sí | **No** |

Menos tamaño significa despliegues más rápidos. Y no incluir compiladores significa que, si alguien lograra entrar al contenedor, no encontraría herramientas con qué trabajar.

---

## 7. Por qué no corre como administrador

Por defecto, un contenedor ejecuta todo como **root**, el usuario con permiso para hacer cualquier cosa.

Nosotros creamos un usuario limitado:

```
uid=10001(app) gid=10001(app)
```

Si alguien encontrara una vulnerabilidad y lograra ejecutar comandos dentro del contenedor, se toparía con un usuario que **no puede instalar nada, no puede modificar el sistema y no puede salir de su carpeta**.

Es la diferencia entre un intruso que entra a una oficina con llave maestra y uno que entra a un cubículo cerrado.

---

## 8. Lo que se verificó

Tres pruebas, y las tres pasaron:

**El tamaño es razonable.**
```
291 MB
```

**No corre como administrador.**
```
uid=10001(app)
```

**Responde y conecta con la base de datos.**
```
/salud → {"estado":"vivo"}
/listo → {"estado":"listo"}
```

---

## 9. Las dos rutas de salud, y por qué son dos

Parecen redundantes. No lo son, y la distinción evita un problema serio en producción.

| Ruta | Pregunta que responde | Qué revisa |
|---|---|---|
| `/salud` | ¿El programa está vivo? | Nada externo |
| `/listo` | ¿Puede atender usuarios? | Base de datos y Redis |

**Por qué `/salud` no revisa la base de datos:**

AWS usa `/salud` para decidir si **reinicia** el contenedor. Si esa ruta consultara la base y la base tuviera una caída de treinta segundos, AWS reiniciaría todos los contenedores —que están sanos— y al volver todos a la vez el problema empeoraría.

AWS usa `/listo` para decidir si **le manda usuarios**. Un contenedor que aún no conecta a la base responde "todavía no", y AWS espera sin reiniciarlo.

Separar las dos preguntas evita apagar el sistema entero por un problema pasajero de otro componente.

---

## 10. Una imagen, dos trabajos

Esto será importante cuando llegue la generación de guías con inteligencia artificial.

La misma imagen se ejecuta de dos formas distintas:

```
Contenedor API      →  atiende a los docentes en el navegador
Contenedor worker   →  procesa las generaciones de IA en segundo plano
```

**Mismo molde, distinta instrucción de arranque.**

La ventaja: es imposible que el worker quede con una versión del código distinta de la API. Vienen del mismo paquete.

Y permite dimensionar por separado. Si un día hay muchas generaciones pendientes, se levantan más workers sin tocar la parte que atiende el navegador.

---

## 11. Cómo se traduce esto a AWS

| Pieza local | En AWS |
|---|---|
| La imagen | **ECR** — repositorio privado de imágenes |
| El contenedor corriendo | **ECS Fargate** — ejecuta contenedores sin servidores que mantener |
| PostgreSQL en Docker | **RDS** — base administrada con respaldo automático |
| Redis en Docker | **ElastiCache** |
| El archivo `.env` | **Secrets Manager** — inyecta las claves al arrancar |
| `/salud` y `/listo` | Lo que consulta el balanceador de carga |

Nada de esto exige reescribir código. Es la misma imagen que ya probamos, ejecutándose en otro lugar.

---

## 12. Para explicarlo en treinta segundos

> Docker convierte la aplicación en un paquete cerrado que trae todo lo necesario para funcionar. Ese paquete corre igual en cualquier computador, así que lo que probamos aquí es exactamente lo que va a correr en AWS.
>
> El paquete no lleva ninguna contraseña adentro: las recibe al arrancar. Y no se ejecuta con permisos de administrador, para que un ataque no pueda hacer daño más allá del propio contenedor.
>
> Pesa 291 megabytes, arranca en segundos, y para levantar más copias solo hay que pedirlas.

---

## 13. Preguntas que pueden hacer

**¿Esto no hace la aplicación más lenta?**
No. Un contenedor no es una máquina virtual: comparte el núcleo del sistema. El costo es prácticamente cero.

**¿Y si el contenedor se cae?**
AWS lo reemplaza automáticamente. Como no guarda nada adentro —los datos viven en la base—, un contenedor nuevo entra sin pérdida de información.

**¿Por qué no instalarlo directamente en un servidor?**
Se puede, y funciona hasta el día que hay que actualizar algo, o levantar un segundo servidor, o reproducir un error que solo aparece allá. Con contenedores, cada despliegue parte del mismo punto conocido.

**¿Cuánto cuesta?**
Se paga por el tiempo de ejecución, no por servidor reservado. Un módulo con setenta y seis usuarios que trabajan en horario de oficina cuesta considerablemente menos que un servidor encendido las veinticuatro horas.
