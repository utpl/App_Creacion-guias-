# Catálogo académico y asignaciones docentes

**Documento técnico** · Hitos 21–23 · 12 de agosto de 2026

---

## 1. Qué resuelve este módulo

Conectar tres cosas que hasta ahora vivían separadas:

```
Las personas          →  ya existían como usuarios del sistema
Las asignaturas       →  no existían
Quién dicta qué       →  no existía
```

Sin esa conexión, un docente entra al sistema y ve una pantalla vacía.

---

## 2. El modelo de datos

```
Facultad
   └── Carrera  (nivel, modalidad, departamento)
          └── Asignatura  (código, nombre, créditos, ciclo, URL de Canvas)

PeriodoAcademico  (nombre, activo)

AsignacionDocente
   ├── docente     → Usuario
   ├── asignatura  → Asignatura
   ├── periodo     → PeriodoAcademico
   └── rol_en_asignatura:  titular | colaborador
```

### 2.1 Decisiones y por qué

**El periodo no tiene fechas.** Solo nombre y si está activo. Sirve para saber a qué periodo pertenece una guía, no para calcular calendario académico. Las fechas reales las administra otro sistema.

**No existe el concepto de paralelo.** Una guía aprobada se publica duplicando el curso en Canvas, y el contenido es idéntico en todos los paralelos. Guardar el paralelo obligaría a mantener guías gemelas sin ninguna diferencia entre ellas.

**Varias personas pueden estar asignadas a una asignatura.** La restricción única es `docente + asignatura + periodo`, no `asignatura + periodo`. Esto permite que una asignatura tenga un autor original y uno o más reestructuradores.

**`nivel` y `modalidad` viven en `Carrera`, no en `Asignatura`.** Son las dimensiones que después filtran qué reglas de generación aplican. Ponerlas en la asignatura obligaría a repetir el mismo valor 63 veces.

**La guía cuelga de asignatura + periodo, no del docente.** Si tres personas trabajan en la misma asignatura, editan la misma guía; no se generan tres versiones paralelas.

---

## 3. De dónde salen los datos

Todo proviene de la hoja de oferta institucional (`oferta.xlsx`), que contiene 63 filas y 41 columnas.

### 3.1 Lo que sí trae

| Dato | Columna del archivo |
|---|---|
| Código de asignatura | `Código Banner` |
| Nombre | `Nombre de Asignatura` |
| Facultad | `Facultad` |
| Carrera | `Carrera responsable de la asignatura` |
| Departamento | `Departamento` |
| Créditos, ciclo | `Créditos`, `Ciclo único` |
| Campo de formación | `Tipo de componente...` |
| Aula virtual | `URL CANVAS` |
| Docentes | `Autor GD`, `Correo electronico GD` |

### 3.2 Lo que NO trae, y hay que resolver aparte

- **Periodo académico** — se pasa como parámetro al importar
- **Modalidad** — se fija como `EN_LINEA` para todo el catálogo actual
- **Número de semanas** — lo elige el docente entre 8 y 16
- **Matriz de planificación** — la sube el docente

---

## 4. Problemas del archivo real y cómo se tratan

El archivo no está normalizado. Estos son los casos detectados y la regla aplicada a cada uno.

### 4.1 Carreras escritas de dos formas

```
"Pedagogía de Los Idiomas Nacionales y Extranjeros"   ← L mayúscula
"Pedagogía de los Idiomas Nacionales y Extranjeros"   ← l minúscula
```

**Regla:** se comparan sin acentos, en minúsculas y sin espacios dobles. Por eso el archivo aparenta 18 carreras y el catálogo tiene 16.

### 4.2 Campo de formación con errores de escritura

```
"INTEGRACION"  →  falta la tilde
"METODOLGÍA"   →  error de digitación
"Fundamentos Teóricos" / "FUNDAMENTOS TEÓRICOS"
```

**Regla:** tabla de equivalencias que unifica las variantes a un valor canónico.

### 4.3 Dos carreras en la misma celda

La fila `EDUC_3135` trae dos carreras separadas por un salto de línea.

**Regla:** se toma la primera. La asignatura pertenece a una sola carrera responsable.

### 4.4 Varias personas en una sola celda

Este es el caso más frecuente: 23 de las 63 filas.

```
Autor GD:      Ligia Elizabeth Molina de la Cruz
               Reestructurada por:
               Mayra Fernanda Jaramillo Pontón
               Eva Ulehlova
```

**Reglas aplicadas:**

1. Se separa por saltos de línea
2. Se descarta la línea literal `"Reestructurada por:"`, que es una etiqueta, no una persona
3. Se deduplica: en tres filas la misma persona figura como autora original **y** como reestructuradora
4. **El primero de la cadena es titular**, el resto son colaboradores

### 4.5 Nombres sin separación de apellidos

El archivo trae el nombre completo en una sola cadena.

**Regla:** convención ecuatoriana — los dos últimos términos son apellidos, el resto son nombres.

```
"Ligia Elizabeth Molina de la Cruz"
   nombres:   Ligia Elizabeth Molina de
   apellidos: la Cruz
```

Esta regla falla con apellidos compuestos. Los casos afectados se corrigen manualmente desde el panel de usuarios.

---

## 5. Titular y colaborador

### 5.1 La regla

**El primero de la cadena `Autor GD` es el titular.** Es el autor original de la guía.

### 5.2 Qué puede hacer cada uno

Ambos tienen exactamente las mismas capacidades:

- Ver la asignatura en su pantalla
- Editar cualquier semana de la guía
- **Aprobar una semana** — cualquiera de los vinculados puede hacerlo

La distinción `titular` / `colaborador` es informativa: indica quién escribió la guía originalmente. No otorga permisos distintos.

### 5.3 Por qué no solo el titular aprueba

En varias asignaturas el titular es el autor original y quien está trabajando activamente es el reestructurador:

```
DERE_4054   titular: Byron Maldonado    colaborador: Maryuri Celi (reestructuró)
ECON_4111   titular: Nathalie Aguirre   colaborador: Johanna Briceño (reestructuró)
```

Si solo aprobara el titular, el flujo se trabaría esperando a alguien que ya no toca la asignatura. El registro de auditoría guarda quién aprobó cada semana, así que la trazabilidad se conserva.

### 5.4 Restricción pendiente

El par académico revisor **no puede ser ninguno de los vinculados a esa guía**. Hay docentes que son titular de una asignatura y colaborador de otra, así que el caso va a aparecer y debe bloquearse explícitamente.

---

## 6. Correos externos

**El importador nunca crea cuentas con correo fuera de `@utpl.edu.ec`.**

Las reporta y espera alta manual por un administrador.

### 6.1 Por qué

- El correo institucional es el identificador único del sistema (no se almacena cédula)
- Una cuenta externa comprometida no la detecta nadie en la UTPL
- El alta manual queda auditada, con un responsable identificable

### 6.2 Cuentas de invitado

Los docentes de otras instituciones que dan cátedra reciben rol `PROFESOR` normal, pero su cuenta lleva dos marcas:

| Campo | Valor | Efecto |
|---|---|---|
| `origen` | `INVITADO` | Distingue del personal de nómina |
| `vigencia_hasta` | Fecha de fin | Pierde acceso automáticamente |

La vigencia es obligatoria. Sin ella, nadie va a acordarse de desactivar la cuenta cuando esa persona deje de colaborar.

---

## 7. Resultado de la importación

Ejecutada sobre el archivo real:

| | Cantidad |
|---|--:|
| Facultades | 4 |
| Carreras | 16 |
| Asignaturas | 63 |
| Docentes creados | 79 |
| Vínculos docente–asignatura | 89 |
| Asignaturas con un solo autor | 41 |
| Asignaturas con colaboradores | 22 |

### 7.1 Dos asignaturas sin titular

61 titulares de 63 esperados. Las dos faltantes:

**`ADMI_4121` — Jorge Fernando Calle Íñiguez**
Su único correo registrado es de Hotmail. No se creó cuenta.
**Resolución:** conseguir su correo institucional, o darlo de alta como invitado con vigencia.

**`ADMI_4098` — Melania Noemí Carrión**
La fila trae dos nombres y un solo correo. No se puede saber cuál corresponde a quién.
**Resolución:** consultar el correo faltante a quien mantiene el archivo de oferta.

**Consecuencia operativa:** esas dos asignaturas no tienen quien genere su guía. Aparecen como alerta en el panel de usuarios.

---

## 8. Los comandos

### 8.1 Catálogo

```bash
python -m app.cli.importar_oferta datos_ejemplo/oferta.xlsx
```

Crea facultades, carreras y asignaturas.

### 8.2 Periodo, docentes y asignaciones

```bash
python -m app.cli.importar_asignaciones datos_ejemplo/oferta.xlsx "Oct. 2026 - Feb. 2027"
```

Crea el periodo (y lo marca activo), las cuentas de docente y los vínculos.

### 8.3 Ambos son idempotentes

Se pueden ejecutar varias veces sin duplicar nada. Esto importa: en un despliegue automatizado, un reintento no debe corromper los datos.

### 8.4 Orden obligatorio

```
sembrar_roles  →  importar_oferta  →  importar_asignaciones
```

`importar_asignaciones` falla si no existe el rol `PROFESOR`, y omite las asignaturas que no estén en el catálogo.

---

## 9. Protección de datos

**El archivo `oferta.xlsx` no se sube al repositorio.** Contiene nombres y correos de 79 personas reales. Está excluido en `.gitignore`:

```
datos_ejemplo/*.xlsx
datos_ejemplo/*.csv
```

El sistema **no almacena cédulas**. Se evaluó y se descartó: el correo institucional cumple la función de identificador y la cédula acarrea obligaciones de protección de datos sin aportar nada al módulo. Además, en el archivo real venía con errores — once cédulas habían perdido el cero inicial al abrirse en Excel.

---

## 10. Lo que sigue

Con el catálogo cargado, el siguiente paso es la **pantalla de "Mis asignaturas"**: que un docente entre y vea las suyas.

Es demostrable ante usuarios reales sin haber generado una sola guía, y valida el enfoque completo antes de invertir en el módulo de generación con IA.

Después:

1. Carga de la matriz de planificación por parte del docente
2. Creación de la guía, con elección de 8 o 16 semanas
3. Generación con IA, encolada y con cuota de tres intentos
4. Circuito de revisión en tres etapas
5. Publicación en Canvas
