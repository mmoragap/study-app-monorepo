# GradeOS v2 — Plataforma de Estudio para Examen de Grado

Plataforma moderna diseñada para optimizar el aprendizaje, la planificación y el rendimiento académico mediante herramientas inteligentes y una arquitectura escalable.

---

## 🚀 Instalación y Configuración (Entorno Local)

Es **fundamental** seguir estos pasos para que el entorno de desarrollo sea idéntico para todos y evitar errores de librerías o conflictos de rutas.

### 1. Clonar el repositorio

```bash
git clone https://github.com/mmoragap/study-app-monorepo.git
cd study-app-monorepo
```

### 2. Crear y activar el entorno virtual (`.venv`)

El `.venv` es personal de cada PC, contiene las librerías y **NO se sube al repositorio** para evitar errores de compatibilidad entre Windows/Mac.

```bash
# Crear el entorno
python -m venv .venv

# Activar en Windows (CMD o PowerShell):
.venv\Scripts\activate

# Activar en Mac o Linux:
source .venv/bin/activate
```

### 3. Instalar dependencias

Con el entorno activado (deberías ver `(.venv)` en la terminal), instala las librerías oficiales:

```bash
pip install -r requirements.txt
```

### 4. Configurar API Key de Anthropic (Claude)

Crea un archivo nuevo en la carpeta raíz llamado exactamente `.env`. Pega la siguiente línea y pon tu clave personal (puedes guiarte por el archivo `.env.example`):

```
ANTHROPIC_API_KEY=tu_clave_aqui_sin_comillas
```

### 5. Correr la aplicación

```bash
python app.py
```

Una vez corriendo, abre en tu navegador: **http://127.0.0.1:5000**

---

## 🛠️ Reglas de Colaboración (Equipo)

Para que el proyecto no "explote" y todos trabajemos sincronizados, sigamos estas reglas de oro:

- **PROHIBIDO subir la carpeta `.venv`:** Ya está configurado en el `.gitignore`. Nunca fuerces su subida al repo.
- **Actualizar dependencias:** Si instalas una librería nueva con `pip`, debes actualizar el archivo de requisitos antes de subir tu código:
  ```bash
  pip freeze > requirements.txt
  ```
- **Sincronización Diaria:** Haz un `git pull` siempre antes de empezar a programar para bajarte los cambios que hicieron los demás.
- **Seguridad:** Nunca subas tus claves API directamente en el código de `app.py`. Usa siempre el archivo `.env`.

---

## 📦 Módulos del Sistema

| Módulo | Descripción |
|---|---|
| **Landing** | Configuración inicial: nombre, fecha de examen y horas disponibles por día. |
| **Dashboard** | Visualización de progreso: radar de dominio, heatmap y recomendación diaria. |
| **Plan de estudio** | Generación automática de Carta Gantt según ponderaciones y nivel de dominio. |
| **Vault** | Gestor de documentos (PDF/DOCX/TXT). Extracción de texto e indexación. |
| **Tutor IA** | Chat inteligente con arquitectura RAG: responde usando tus propios apuntes. |
| **Simulador** | Creación de ensayos y preguntas personalizadas con feedback automático. |

---

## 📂 Estructura del Proyecto

```
study-app-monorepo/
├── app.py              # Backend Flask (Rutas, lógica y Tutor IA)
├── .gitignore          # Archivos que Git debe ignorar (.venv, data.json, etc.)
├── .env.example        # Plantilla para que el equipo sepa qué variables configurar
├── templates/          # Frontend (Interfaz diseñada con Stitch/HTML)
├── uploads/            # Carpeta para los archivos que subes al Vault
├── data.json           # Base de datos local (se crea automáticamente al iniciar)
└── requirements.txt    # Lista oficial de librerías para el equipo
```

---

## 🤖 Funcionamiento del Tutor IA (RAG)

El sistema utiliza una arquitectura de **Generación Aumentada por Recuperación (RAG)** para asegurar que la IA no invente cosas:

1. **Ingesta:** Los archivos subidos al Vault se fragmentan en bloques con contexto.
2. **Búsqueda:** Cuando haces una pregunta, el sistema busca los fragmentos más relevantes en tus documentos.
3. **Contexto:** Se le envía a Claude (Anthropic) tu pregunta junto con los fragmentos encontrados.
4. **Respuesta:** El tutor genera una respuesta basada exclusivamente en tu material de estudio, citando las fuentes.

---

> Desarrollado para el proceso de Licenciatura ICI — UDD.
