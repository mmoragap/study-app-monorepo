# GradeOS v2 — Plataforma de Estudio para Examen de Grado

## Instalación

```bash
# 1. Instalar dependencias (en Anaconda Prompt o CMD)
pip install -r requirements.txt

# 2. Configurar API key de Anthropic
set ANTHROPIC_API_KEY=sk-ant-...        # Windows CMD
export ANTHROPIC_API_KEY="sk-ant-..."   # Mac/Linux

# 3. Correr la app
python app.py

# 4. Abrir en el navegador
http://localhost:5000
```

## Módulos

| Módulo | Qué hace |
|---|---|
| **Landing** | Configuración inicial: nombre, fecha examen, horas disponibles |
| **Dashboard** | Radar de dominio, heatmap de actividad, stats globales, recomendación del día |
| **Plan de estudio** | Carta Gantt generada automáticamente por ponderación y dominio |
| **Vault** | Subida de PDF/DOCX/TXT, extracción de texto, indexación por fragmentos |
| **Tutor IA** | Chat con RAG: busca fragmentos relevantes de tus archivos antes de responder |
| **Simulador** | Preguntas generadas desde tu material, corrección automática con feedback |

## Estructura de archivos

```
gradeos/
├── app.py              ← Backend Flask completo
├── templates/
│   └── index.html      ← Frontend SPA completo
├── uploads/            ← Archivos subidos (auto-creado)
├── data.json           ← Base de datos local (auto-creado)
└── requirements.txt
```

## Cómo funciona el Tutor IA (RAG)

1. Subes un PDF → el sistema extrae el texto y lo divide en fragmentos de ~800 caracteres
2. Cuando preguntas algo, el sistema busca los fragmentos más relevantes por palabras clave
3. Claude recibe esos fragmentos como contexto y responde basándose en TU material
4. Las fuentes usadas se muestran bajo cada respuesta
