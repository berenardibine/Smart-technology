from flask import Flask, render_template, request, jsonify, send_file
import anthropic
import base64
import sqlite3
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.enums import TA_CENTER
import tempfile

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs('uploads', exist_ok=True)

# ── Database ───────────────────────────────────────────────────────────────
def get_db():
    db = sqlite3.connect('stech.db')
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with get_db() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT)''')
        db.execute('''CREATE TABLE IF NOT EXISTS repairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_type TEXT, brand TEXT, model TEXT,
            symptoms TEXT, diagnosis TEXT, notes TEXT,
            created_at TEXT DEFAULT (datetime('now')))''')
        db.commit()

init_db()

# ── API key helpers ────────────────────────────────────────────────────────
def get_api_key():
    # DB first, then environment variable
    try:
        db = get_db()
        row = db.execute("SELECT value FROM settings WHERE key='api_key'").fetchone()
        if row and row['value']:
            return row['value'].strip()
    except Exception:
        pass
    return os.environ.get('ANTHROPIC_API_KEY', '').strip()

def call_claude(system, user_text, image_b64=None, image_type='image/jpeg'):
    api_key = get_api_key()
    if not api_key:
        raise ValueError("No API key configured. Please go to Settings and enter your Anthropic API key.")
    client = anthropic.Anthropic(api_key=api_key)
    content = []
    if image_b64:
        content.append({"type": "image",
                        "source": {"type": "base64", "media_type": image_type, "data": image_b64}})
    content.append({"type": "text", "text": user_text})
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1200,
        system=system,
        messages=[{"role": "user", "content": content}]
    )
    return msg.content[0].text

# ── Settings routes ────────────────────────────────────────────────────────
@app.route('/api/settings/apikey', methods=['GET'])
def get_key_status():
    key = get_api_key()
    if key:
        masked = key[:8] + '...' + key[-4:]
        return jsonify({'configured': True, 'masked': masked})
    return jsonify({'configured': False, 'masked': ''})

@app.route('/api/settings/apikey', methods=['POST'])
def save_api_key():
    data = request.json
    key = (data.get('api_key') or '').strip()
    if not key:
        return jsonify({'success': False, 'error': 'API key cannot be empty'}), 400
    # Quick validation
    if not key.startswith('sk-ant-'):
        return jsonify({'success': False, 'error': 'Invalid key format. Anthropic keys start with sk-ant-'}), 400
    # Test the key
    try:
        client = anthropic.Anthropic(api_key=key)
        client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "hi"}]
        )
    except anthropic.AuthenticationError:
        return jsonify({'success': False, 'error': 'Invalid API key. Please check and try again.'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'Could not verify key: {str(e)}'}), 400
    # Save to DB
    db = get_db()
    db.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('api_key',?)", (key,))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/settings/apikey', methods=['DELETE'])
def delete_api_key():
    db = get_db()
    db.execute("DELETE FROM settings WHERE key='api_key'")
    db.commit()
    return jsonify({'success': True})

# ── Main page ──────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

# ── AI Diagnostic ──────────────────────────────────────────────────────────
@app.route('/api/diagnose', methods=['POST'])
def diagnose():
    data = request.json
    system = """You are STECH AI, an expert electronics diagnostic system for professional repair technicians.
Format your response EXACTLY as:

## POSSIBLE CAUSES
1. [Cause] — [X]% probability
[Brief explanation]

2. [Cause] — [X]% probability
[Brief explanation]

3. [Cause] — [X]% probability
[Brief explanation]

## RECOMMENDED TESTS
• [Test name]: [How to perform]
• [Test name]: [How to perform]
• [Test name]: [How to perform]

## REPAIR STEPS
**Step 1:** [Action]
**Step 2:** [Action]
**Step 3:** [Action]

## DIFFICULTY LEVEL
[Beginner / Intermediate / Advanced] — [Reason]

## SAFETY WARNINGS
⚠️ [Warning]"""
    user_text = (f"Device: {data.get('device_type')}\nBrand: {data.get('brand')}\n"
                 f"Model: {data.get('model')}\nSymptoms: {data.get('symptoms')}\n\nProvide full diagnostic analysis.")
    try:
        result = call_claude(system, user_text)
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── PCB Analyzer ───────────────────────────────────────────────────────────
@app.route('/api/pcb', methods=['POST'])
def pcb_analyze():
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image uploaded'}), 400
    file = request.files['image']
    b64 = base64.b64encode(file.read()).decode()
    mime = file.content_type or 'image/jpeg'
    system = """You are STECH PCB Analysis AI. Format response EXACTLY as:

## DETECTED FAULTS
• [Fault and location]

## CONFIDENCE LEVEL
[XX]% — [Reasoning]

## AFFECTED COMPONENTS
• [Component/section]: [Issue]

## RECOMMENDED ACTION
[Repair recommendation]

## RISK ASSESSMENT
[Low / Medium / High] — [Explanation]"""
    try:
        result = call_claude(system, "Analyze this PCB for burned components, corrosion, shorts, or damage.", b64, mime)
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── Component Identifier ───────────────────────────────────────────────────
@app.route('/api/component', methods=['POST'])
def identify_component():
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image uploaded'}), 400
    file = request.files['image']
    b64 = base64.b64encode(file.read()).decode()
    mime = file.content_type or 'image/jpeg'
    system = """You are STECH Component Identification AI. Format EXACTLY as:

## COMPONENT IDENTIFIED
**Name:** [Full name]
**Type:** [Resistor/Capacitor/IC/Transistor/MOSFET/Diode/etc.]
**Value/Rating:** [Value if visible]

## FUNCTION
[What this component does]

## COMMON FAILURES
• [Failure 1]
• [Failure 2]

## REPLACEMENT SUGGESTIONS
• [Suggestion 1]
• [Suggestion 2]

## IDENTIFICATION TIPS
[How to read markings or pinout]"""
    try:
        result = call_claude(system, "Identify this electronic component with full specs.", b64, mime)
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── Repair Guide ───────────────────────────────────────────────────────────
@app.route('/api/repair-guide', methods=['POST'])
def repair_guide():
    data = request.json
    system = """You are STECH Repair Guide AI. Format EXACTLY as:

## REQUIRED TOOLS
• [Tool 1]
• [Tool 2]

## SAFETY WARNINGS
⚠️ [Warning]

## DIFFICULTY LEVEL
[Level] — Estimated Time: [X mins/hours]

## STEP-BY-STEP PROCEDURE
**Step 1 — [Title]**
[Instruction]

**Step 2 — [Title]**
[Instruction]

## TESTING AFTER REPAIR
[How to verify success]

## TIPS & TRICKS
• [Tip 1]
• [Tip 2]"""
    user_text = (f"Generate a complete repair guide for:\nDevice: {data.get('device')}\n"
                 f"Issue: {data.get('issue')}\nSkill Level: {data.get('level', 'Intermediate')}")
    try:
        result = call_claude(system, user_text)
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── Circuit Explain ────────────────────────────────────────────────────────
@app.route('/api/circuit', methods=['POST'])
def circuit_explain():
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'No image uploaded'}), 400
    file = request.files['image']
    b64 = base64.b64encode(file.read()).decode()
    mime = file.content_type or 'image/jpeg'
    system = """You are STECH Circuit Explanation AI. Format EXACTLY as:

## CIRCUIT PURPOSE
[What this circuit does]

## POWER FLOW
[How power moves through]

## SIGNAL FLOW
[How signals move]

## KEY COMPONENTS & FUNCTIONS
• [Component]: [Role]

## BEGINNER EXPLANATION
[Simple analogy-based explanation]

## TECHNICIAN EXPLANATION
[Technical explanation]

## COMMON ISSUES
• [Issue 1]
• [Issue 2]"""
    try:
        result = call_claude(system, "Explain this circuit diagram or PCB image in full detail.", b64, mime)
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── Learning ───────────────────────────────────────────────────────────────
@app.route('/api/learn', methods=['POST'])
def learn():
    data = request.json
    topic = data.get('topic', '')
    system = """You are STECH Learning AI. Format EXACTLY as:

## OVERVIEW
[Clear introduction]

## KEY CONCEPTS
• **[Concept 1]:** [Explanation]
• **[Concept 2]:** [Explanation]
• **[Concept 3]:** [Explanation]

## FORMULA / SPECIFICATIONS
[Relevant formulas or spec ranges]

## REAL-WORLD APPLICATION
[How this applies in repair work]

## COMMON MISTAKES
• [Mistake 1]
• [Mistake 2]

## QUICK REFERENCE
[Summary of key points]"""
    try:
        result = call_claude(system, f"Explain for a repair technician: {topic}")
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ── History CRUD ───────────────────────────────────────────────────────────
@app.route('/api/history', methods=['GET'])
def get_history():
    db = get_db()
    rows = db.execute('SELECT * FROM repairs ORDER BY id DESC').fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/history', methods=['POST'])
def save_repair():
    data = request.json
    db = get_db()
    cur = db.execute(
        'INSERT INTO repairs (device_type,brand,model,symptoms,diagnosis,notes) VALUES (?,?,?,?,?,?)',
        (data.get('device_type',''), data.get('brand',''), data.get('model',''),
         data.get('symptoms',''), data.get('diagnosis',''), data.get('notes',''))
    )
    db.commit()
    return jsonify({'success': True, 'id': cur.lastrowid})

@app.route('/api/history/<int:rid>', methods=['DELETE'])
def delete_repair(rid):
    db = get_db()
    db.execute('DELETE FROM repairs WHERE id=?', (rid,))
    db.commit()
    return jsonify({'success': True})

@app.route('/api/history/<int:rid>/notes', methods=['PUT'])
def update_notes(rid):
    data = request.json
    db = get_db()
    db.execute('UPDATE repairs SET notes=? WHERE id=?', (data.get('notes',''), rid))
    db.commit()
    return jsonify({'success': True})

# ── PDF Export ─────────────────────────────────────────────────────────────
@app.route('/api/pdf/<int:rid>')
def export_pdf(rid):
    db = get_db()
    rec = db.execute('SELECT * FROM repairs WHERE id=?', (rid,)).fetchone()
    if not rec:
        return 'Not found', 404
    rec = dict(rec)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    doc = SimpleDocTemplate(tmp.name, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    orange = colors.HexColor('#f97316')
    navy   = colors.HexColor('#1e3a5f')
    title_s = ParagraphStyle('T', fontSize=22, textColor=navy, fontName='Helvetica-Bold', spaceAfter=4)
    sub_s   = ParagraphStyle('S', fontSize=11, textColor=orange, fontName='Helvetica')
    lbl_s   = ParagraphStyle('L', fontSize=10, textColor=colors.grey, fontName='Helvetica-Bold', spaceAfter=2)
    body_s  = ParagraphStyle('B', fontSize=11, fontName='Helvetica', leading=16, spaceAfter=6)
    foot_s  = ParagraphStyle('F', fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
    story = [
        Paragraph("STECH ELECTRONICS", title_s),
        Paragraph("Professional Diagnostic Report", sub_s),
        HRFlowable(width="100%", thickness=2, color=orange, spaceAfter=16),
        Paragraph("DEVICE INFORMATION", lbl_s),
    ]
    t = Table([
        ['Device Type', rec['device_type'] or '—', 'Brand', rec['brand'] or '—'],
        ['Model',       rec['model'] or '—',        'Date',  (rec['created_at'] or '')[:10]],
    ], colWidths=[3*cm, 6*cm, 3*cm, 5*cm])
    t.setStyle(TableStyle([
        ('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),10),
        ('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.HexColor('#f1f5f9'),colors.white]),
        ('BOX',(0,0),(-1,-1),0.5,colors.HexColor('#e2e8f0')),
        ('INNERGRID',(0,0),(-1,-1),0.25,colors.HexColor('#e2e8f0')),
        ('PADDING',(0,0),(-1,-1),6),
        ('TEXTCOLOR',(0,0),(0,-1),colors.grey),('TEXTCOLOR',(2,0),(2,-1),colors.grey),
    ]))
    diag_clean = (rec['diagnosis'] or '').replace('\n','<br/>')
    story += [t, Spacer(1,16),
              Paragraph("SYMPTOMS", lbl_s), Paragraph(rec['symptoms'] or '—', body_s),
              Spacer(1,8), HRFlowable(width="100%",thickness=0.5,color=colors.HexColor('#e2e8f0'),spaceAfter=8),
              Paragraph("AI DIAGNOSIS", lbl_s), Paragraph(diag_clean, body_s)]
    if rec['notes']:
        story += [Spacer(1,8),
                  HRFlowable(width="100%",thickness=0.5,color=colors.HexColor('#e2e8f0'),spaceAfter=8),
                  Paragraph("TECHNICIAN NOTES", lbl_s), Paragraph(rec['notes'], body_s)]
    story += [Spacer(1,24),
              HRFlowable(width="100%",thickness=0.5,color=colors.HexColor('#e2e8f0'),spaceAfter=6),
              Paragraph(f"Generated by STECH Diagnostic AI · {datetime.now().strftime('%d %b %Y %H:%M')}", foot_s)]
    doc.build(story)
    return send_file(tmp.name, as_attachment=True,
                     download_name=f"STECH_Report_{rid}.pdf",
                     mimetype='application/pdf')

if __name__ == '__main__':
    print("\n" + "="*52)
    print("  ⚡ STECH Electronics Diagnostic AI")
    print("  Open: http://127.0.0.1:5000")
    print("  Go to Settings to enter your API key")
    print("="*52 + "\n")
    app.run(debug=True, port=5000)
