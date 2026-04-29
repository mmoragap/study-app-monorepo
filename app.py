import os, json, uuid, math
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import anthropic

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

ALLOWED = {'pdf', 'docx', 'txt', 'png', 'jpg', 'jpeg'}
DB = 'data.json'
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

# ── DB ─────────────────────────────────────────────────────────────────────────
def load():
    if os.path.exists(DB):
        with open(DB) as f:
            return json.load(f)
    return {
        "config": {},          # fecha_examen, nombre_alumno
        "ramos": [],
        "archivos": [],
        "simulacros": [],
        "sesiones_estudio": [], # para heatmap
        "chat_sessions": []
    }

def save(data):
    with open(DB, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def allowed(fn):
    return '.' in fn and fn.rsplit('.',1)[1].lower() in ALLOWED

def extract_text(path, fn):
    ext = fn.rsplit('.',1)[1].lower()
    text = ""
    try:
        if ext == 'pdf':
            import PyPDF2
            with open(path,'rb') as f:
                r = PyPDF2.PdfReader(f)
                for p in r.pages:
                    text += (p.extract_text() or "")
        elif ext == 'docx':
            from docx import Document
            doc = Document(path)
            text = "\n".join(p.text for p in doc.paragraphs)
        elif ext == 'txt':
            with open(path, encoding='utf-8', errors='ignore') as f:
                text = f.read()
        elif ext in {'png','jpg','jpeg'}:
            text = "[Imagen — sube la versión PDF para mejor análisis]"
    except Exception as e:
        text = f"[Error: {e}]"
    # chunk into segments of 800 chars for better retrieval
    segments = []
    for i in range(0, len(text), 800):
        seg = text[i:i+800].strip()
        if seg:
            segments.append(seg)
    return text[:12000], segments

def simple_search(query, segments, top_k=5):
    """Keyword-based retrieval when no embeddings available"""
    if not segments:
        return []
    q_words = set(query.lower().split())
    scored = []
    for seg in segments:
        words = set(seg.lower().split())
        score = len(q_words & words) / (len(q_words) + 1)
        scored.append((score, seg))
    scored.sort(reverse=True)
    return [s for _, s in scored[:top_k] if _ > 0]

def dias_al_examen(data):
    cfg = data.get('config', {})
    fe = cfg.get('fecha_examen')
    if not fe:
        return None
    try:
        d = datetime.strptime(fe, '%Y-%m-%d').date()
        return (d - date.today()).days
    except:
        return None

# ── HOME ───────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.1.html')

# ── CONFIG ─────────────────────────────────────────────────────────────────────
@app.route('/api/config', methods=['GET'])
def get_config():
    d = load()
    dias = dias_al_examen(d)
    return jsonify({**d['config'], 'dias_al_examen': dias})

@app.route('/api/config', methods=['POST'])
def set_config():
    d = load()
    data = request.get_json()
    if not data:
        return jsonify({"error": "No se recibieron datos"}), 400
    
    d['config'].update(data)
    save(d)
    return jsonify(d['config'])

# ── RAMOS ──────────────────────────────────────────────────────────────────────
@app.route('/api/ramos', methods=['GET'])
def get_ramos():
    return jsonify(load()['ramos'])

@app.route('/api/ramos', methods=['POST'])
def add_ramo():
    d = load()
    b = request.json
    r = {
        "id": str(uuid.uuid4()),
        "nombre": b.get("nombre",""),
        "creditos": b.get("creditos", 8),
        "ponderacion": b.get("ponderacion", 25),
        "color": b.get("color","#5DCAA5"),
        "temas": b.get("temas", []),
        "dominio": 0,
        "horas_semana": b.get("horas_semana", 4),
        "prioridad": b.get("prioridad", "media")
    }
    d['ramos'].append(r)
    save(d)
    return jsonify(r)

@app.route('/api/ramos/<rid>', methods=['PATCH'])
def patch_ramo(rid):
    d = load()
    for r in d['ramos']:
        if r['id'] == rid:
            r.update(request.json)
            break
    save(d)
    return jsonify({"ok": True})

@app.route('/api/ramos/<rid>', methods=['DELETE'])
def del_ramo(rid):
    d = load()
    d['ramos'] = [r for r in d['ramos'] if r['id'] != rid]
    save(d)
    return jsonify({"ok": True})

# ── ARCHIVOS ───────────────────────────────────────────────────────────────────
@app.route('/api/archivos', methods=['GET'])
def get_archivos():
    d = load()
    return jsonify([{k:v for k,v in a.items() if k not in ('texto','segmentos')} for a in d['archivos']])

@app.route('/api/archivos', methods=['POST'])
def upload():
    d = load()
    if 'file' not in request.files:
        return jsonify({"error":"no file"}), 400
    file = request.files['file']
    if not file.filename or not allowed(file.filename):
        return jsonify({"error":"tipo no permitido"}), 400
    fn = secure_filename(file.filename)
    fid = str(uuid.uuid4())
    sn = f"{fid}_{fn}"
    path = os.path.join(app.config['UPLOAD_FOLDER'], sn)
    file.save(path)
    text, segments = extract_text(path, fn)
    a = {
        "id": fid,
        "nombre": fn,
        "ramo_id": request.form.get('ramo_id',''),
        "tipo": request.form.get('tipo','Apuntes'),
        "size": os.path.getsize(path),
        "path": path,
        "fecha": date.today().isoformat(),
        "texto": text,
        "segmentos": segments,
        "n_segmentos": len(segments)
    }
    d['archivos'].append(a)
    save(d)
    return jsonify({k:v for k,v in a.items() if k not in ('texto','segmentos')})

@app.route('/api/archivos/<aid>', methods=['DELETE'])
def del_archivo(aid):
    d = load()
    a = next((x for x in d['archivos'] if x['id']==aid), None)
    if a and os.path.exists(a.get('path','')):
        os.remove(a['path'])
    d['archivos'] = [x for x in d['archivos'] if x['id']!=aid]
    save(d)
    return jsonify({"ok":True})

# ── CHAT ───────────────────────────────────────────────────────────────────────
@app.route('/api/chat', methods=['POST'])
def chat():
    b = request.json
    question = b.get("message","")
    ramo_id  = b.get("ramo_id","")
    history  = b.get("history",[])
    d = load()

    archivos = d['archivos']
    if ramo_id:
        archivos = [a for a in archivos if a.get('ramo_id')==ramo_id]

    # RAG: retrieve relevant segments
    all_segments = []
    for a in archivos:
        for seg in a.get('segmentos',[]):
            all_segments.append((a['nombre'], a['tipo'], seg))

    relevant = []
    if all_segments:
        q_words = set(question.lower().split())
        scored = []
        for name, tipo, seg in all_segments:
            words = set(seg.lower().split())
            score = len(q_words & words) / (len(q_words)+1)
            scored.append((score, name, tipo, seg))
        scored.sort(reverse=True)
        relevant = scored[:6]

    context = ""
    if relevant:
        context = "FRAGMENTOS RELEVANTES DE TUS ARCHIVOS:\n\n"
        for score, name, tipo, seg in relevant:
            context += f"[{name} | {tipo}]\n{seg}\n\n---\n"
    else:
        context = "No se encontraron archivos relevantes para esta pregunta. Responde con tu conocimiento general."

    ramos = d['ramos']
    ramos_txt = ", ".join(r['nombre'] for r in ramos) or "no definidos"
    alumno = d['config'].get('nombre_alumno','Estudiante')
    dias = dias_al_examen(d)
    dias_txt = f"{dias} días" if dias is not None else "fecha no configurada"

    system = f"""Eres el tutor personal de {alumno} para su examen de grado de Ingeniería Civil Industrial.
Ramos del examen: {ramos_txt}.
Tiempo al examen: {dias_txt}.

{context}

INSTRUCCIONES:
- Responde SIEMPRE en español, tono directo y técnico como entre ingenieros.
- Si tienes fragmentos relevantes, basa tu respuesta en ellos y cítalos brevemente.
- Si la pregunta es conceptual, explica con claridad y da un ejemplo aplicado a ingeniería u operaciones.
- Si la pregunta es de cálculo, muestra el desarrollo paso a paso.
- Si el alumno no entiende algo, usa la técnica Feynman: pídele que lo explique con sus palabras.
- Al final de cada respuesta, sugiere UNA pregunta de seguimiento para profundizar.
- Máximo 400 palabras por respuesta."""

    msgs = []
    for h in history[-8:]:
        msgs.append({"role":h["role"],"content":h["content"]})
    msgs.append({"role":"user","content":question})

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system,
            messages=msgs
        )
        answer = resp.content[0].text
        fuentes = list(set(name for _,name,_,_ in relevant)) if relevant else []
    except Exception as e:
        answer = f"Error: {e}"
        fuentes = []

    return jsonify({"answer": answer, "fuentes": fuentes})

# ── SIMULACRO ──────────────────────────────────────────────────────────────────
@app.route('/api/simulacro', methods=['POST'])
def gen_simulacro():
    b = request.json
    ramo_ids  = b.get("ramos",[])
    cantidad  = b.get("cantidad", 8)
    tipo      = b.get("tipo","mixto")
    dificultad= b.get("dificultad","media")
    d = load()

    archivos = [a for a in d['archivos'] if not ramo_ids or a.get('ramo_id') in ramo_ids]
    ramos    = [r for r in d['ramos'] if not ramo_ids or r['id'] in ramo_ids]
    ramos_txt= ", ".join(r['nombre'] for r in ramos) or "todos los ramos"

    # build context from segments
    context = ""
    seen = 0
    for a in archivos:
        for seg in a.get('segmentos',[])[:4]:
            context += f"[{a['nombre']}]\n{seg}\n\n"
            seen += 1
            if seen >= 20: break
        if seen >= 20: break

    tipo_instr = {
        "conceptual": "Solo preguntas conceptuales: definiciones, diferencias, explicaciones, aplicaciones.",
        "calculo": "Solo problemas numéricos con datos concretos que requieran desarrollo matemático.",
        "mixto": "60% conceptuales, 40% de cálculo o casos.",
        "casos": "Casos de análisis tipo examen oral: situaciones reales de una empresa u hospital que requieran aplicar conocimientos."
    }.get(tipo, "")

    dif_instr = {
        "baja": "Preguntas directas de memorización o aplicación simple.",
        "media": "Preguntas que requieren comprensión profunda y conexión entre conceptos.",
        "alta": "Preguntas desafiantes con múltiples conceptos integrados, trampas conceptuales, o problemas complejos."
    }.get(dificultad, "")

    prompt = f"""Genera exactamente {cantidad} preguntas de examen de grado de Ingeniería Civil Industrial para: {ramos_txt}.

Tipo: {tipo_instr}
Dificultad: {dif_instr}

Material del estudiante:
{context[:4000]}

Devuelve ÚNICAMENTE JSON válido, sin texto adicional, sin markdown:
{{
  "preguntas": [
    {{
      "numero": 1,
      "enunciado": "pregunta completa y clara",
      "tipo": "conceptual|calculo|caso",
      "dificultad": "baja|media|alta",
      "tema": "nombre del tema",
      "subtema": "concepto específico",
      "pauta": "respuesta completa o criterios de corrección detallados",
      "puntaje_max": 10
    }}
  ]
}}"""

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[{"role":"user","content":prompt}]
        )
        raw = resp.content[0].text.strip()
        if '```' in raw:
            raw = raw.split('```')[1]
            if raw.startswith('json'): raw = raw[4:]
        parsed = json.loads(raw)
        preguntas = parsed.get("preguntas",[])
    except Exception as e:
        preguntas = [{"numero":1,"enunciado":f"Error generando preguntas: {e}","tipo":"conceptual","dificultad":"media","tema":"Error","subtema":"","pauta":"","puntaje_max":10}]

    sim = {
        "id": str(uuid.uuid4()),
        "ramos": ramos_txt,
        "ramo_ids": ramo_ids,
        "tipo": tipo,
        "dificultad": dificultad,
        "preguntas": preguntas,
        "respuestas": {},
        "completado": False,
        "score": None,
        "fecha": date.today().isoformat(),
        "tiempo_inicio": datetime.now().isoformat()
    }
    d['simulacros'].append(sim)
    save(d)
    return jsonify(sim)

@app.route('/api/simulacro/<sid>/evaluar', methods=['POST'])
def evaluar(sid):
    b = request.json
    respuestas = b.get("respuestas",{})
    tiempo_min = b.get("tiempo_min", 0)
    d = load()
    sim = next((s for s in d['simulacros'] if s['id']==sid), None)
    if not sim: return jsonify({"error":"no encontrado"}), 404

    preguntas_txt = ""
    for p in sim['preguntas']:
        resp_alumno = respuestas.get(str(p['numero']), "(sin respuesta)")
        preguntas_txt += f"""
P{p['numero']} [{p['tipo']} | {p['dificultad']} | {p['tema']}]:
Enunciado: {p['enunciado']}
Pauta: {p['pauta']}
Respuesta del alumno: {resp_alumno}
"""

    prompt = f"""Evalúa estas respuestas de un estudiante de Ingeniería Civil Industrial.

{preguntas_txt}

Devuelve ÚNICAMENTE JSON válido, sin texto adicional:
{{
  "evaluaciones": [
    {{
      "numero": 1,
      "puntaje": número de 0 a 10,
      "correcto": true o false,
      "feedback": "retroalimentación específica y constructiva de 1-2 oraciones",
      "concepto_clave": "el concepto que debe reforzar"
    }}
  ],
  "score_global": número de 0 a 100,
  "nivel": "Insuficiente|Suficiente|Bueno|Muy bueno|Excelente",
  "fortalezas": "1-2 oraciones sobre lo que domina",
  "areas_mejorar": "1-2 oraciones sobre qué reforzar urgente",
  "recomendacion": "acción concreta para la próxima sesión de estudio"
}}"""

    try:
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role":"user","content":prompt}]
        )
        raw = resp.content[0].text.strip()
        if '```' in raw:
            raw = raw.split('```')[1]
            if raw.startswith('json'): raw = raw[4:]
        result = json.loads(raw)
    except Exception as e:
        result = {"evaluaciones":[],"score_global":0,"nivel":"Error","fortalezas":"","areas_mejorar":str(e),"recomendacion":""}

    sim['respuestas']  = respuestas
    sim['completado']  = True
    sim['score']       = result.get('score_global',0)
    sim['nivel']       = result.get('nivel','')
    sim['evaluacion']  = result
    sim['tiempo_min']  = tiempo_min

    # update ramo dominio based on score
    score = result.get('score_global',0)
    for rid in sim.get('ramo_ids',[]):
        for r in d['ramos']:
            if r['id'] == rid:
                # weighted average: 70% old, 30% new score
                old = r.get('dominio',0)
                r['dominio'] = round(old*0.7 + score*0.3)
                break

    # log sesion estudio
    d['sesiones_estudio'].append({
        "fecha": date.today().isoformat(),
        "tipo": "simulacro",
        "duracion_min": tiempo_min,
        "score": score
    })
    save(d)
    return jsonify(result)

@app.route('/api/simulacros', methods=['GET'])
def get_simulacros():
    return jsonify(load()['simulacros'])

# ── PLANIFICACIÓN ──────────────────────────────────────────────────────────────
@app.route('/api/plan', methods=['GET'])
def get_plan():
    d = load()
    dias = dias_al_examen(d)
    if dias is None or dias <= 0:
        return jsonify({"semanas":[], "recomendacion":"Configura la fecha del examen primero."})

    ramos = d['ramos']
    if not ramos:
        return jsonify({"semanas":[], "recomendacion":"Agrega tus ramos primero."})

    # distribute by priority: weight = ponderacion * (1 - dominio/100)
    total_peso = sum(r.get('ponderacion',25) * (1 - r.get('dominio',0)/100) for r in ramos)
    horas_diarias = d['config'].get('horas_diarias', 3)
    semanas = math.ceil(dias / 7)

    plan = []
    for i in range(semanas):
        semana_num = i + 1
        fecha_ini = (date.today() + timedelta(days=i*7)).isoformat()
        fecha_fin = (date.today() + timedelta(days=min((i+1)*7-1, dias-1))).isoformat()
        dias_semana = min(7, dias - i*7)
        horas_semana = dias_semana * horas_diarias

        bloques = []
        for r in ramos:
            peso = r.get('ponderacion',25) * (1 - r.get('dominio',0)/100)
            fraccion = (peso / total_peso) if total_peso > 0 else (1/len(ramos))
            horas_ramo = round(horas_semana * fraccion, 1)
            if horas_ramo < 0.5: horas_ramo = 0.5
            # last week: focus on review
            fase = "Repaso general" if semana_num == semanas else ("Profundización" if semana_num > semanas//2 else "Base y comprensión")
            bloques.append({
                "ramo_id": r['id'],
                "ramo": r['nombre'],
                "color": r['color'],
                "horas": horas_ramo,
                "fase": fase,
                "dominio_actual": r.get('dominio',0)
            })

        plan.append({
            "semana": semana_num,
            "fecha_ini": fecha_ini,
            "fecha_fin": fecha_fin,
            "horas_total": round(horas_semana,1),
            "bloques": bloques
        })

    # recomendacion del dia
    ramo_urgente = min(ramos, key=lambda r: r.get('dominio',0)) if ramos else None
    rec = f"Hoy enfócate en {ramo_urgente['nombre']} (dominio {ramo_urgente['dominio']}%)" if ramo_urgente else ""

    return jsonify({"semanas": plan, "dias_al_examen": dias, "recomendacion": rec})

# ── SESIONES ESTUDIO (heatmap) ─────────────────────────────────────────────────
@app.route('/api/sesiones', methods=['GET'])
def get_sesiones():
    d = load()
    # aggregate by date
    agg = {}
    for s in d.get('sesiones_estudio',[]):
        fecha = s['fecha']
        if fecha not in agg:
            agg[fecha] = {"fecha": fecha, "minutos": 0, "sesiones": 0}
        agg[fecha]['minutos'] += s.get('duracion_min',0)
        agg[fecha]['sesiones'] += 1
    return jsonify(list(agg.values()))

@app.route('/api/sesiones', methods=['POST'])
def add_sesion():
    d = load()
    b = request.json
    d['sesiones_estudio'].append({
        "fecha": date.today().isoformat(),
        "tipo": b.get("tipo","manual"),
        "duracion_min": b.get("duracion_min", 0),
        "score": b.get("score", None)
    })
    save(d)
    return jsonify({"ok":True})

# ── STATS para dashboard ────────────────────────────────────────────────────────
@app.route('/api/stats', methods=['GET'])
def get_stats():
    d = load()
    ramos = d['ramos']
    archivos = d['archivos']
    sims = d['simulacros']
    sims_ok = [s for s in sims if s['completado']]
    avg_score = round(sum(s['score'] for s in sims_ok)/len(sims_ok)) if sims_ok else 0
    dominio_global = round(sum(r.get('dominio',0)*r.get('ponderacion',25) for r in ramos)/sum(r.get('ponderacion',25) for r in ramos)) if ramos else 0
    dias = dias_al_examen(d)
    return jsonify({
        "dominio_global": dominio_global,
        "n_ramos": len(ramos),
        "n_archivos": len(archivos),
        "n_simulacros": len(sims_ok),
        "avg_score": avg_score,
        "dias_al_examen": dias,
        "ramos": ramos
    })

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    app.run(debug=True, port=5000)
