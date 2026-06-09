# ⚡ STECH Electronics Diagnostic AI
### Python Flask Web Application — v1.0

---

## 📋 Requirements
- Python 3.9 or higher
- An Anthropic API key (get one at https://console.anthropic.com)

---

## 🚀 Quick Start

### Step 1 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 2 — Set your API key

**Windows (Command Prompt):**
```cmd
set ANTHROPIC_API_KEY=your-api-key-here
```

**Windows (PowerShell):**
```powershell
$env:ANTHROPIC_API_KEY="your-api-key-here"
```

**Mac / Linux:**
```bash
export ANTHROPIC_API_KEY=your-api-key-here
```

### Step 3 — Run the app
```bash
python app.py
```

### Step 4 — Open in browser
```
http://127.0.0.1:5000
```

---

## 🗂️ Project Structure
```
stech/
├── app.py              ← Main Flask application
├── requirements.txt    ← Python dependencies
├── README.md           ← This file
├── stech.db            ← SQLite database (auto-created)
├── templates/
│   └── index.html      ← Full frontend UI
└── uploads/            ← Temporary image uploads
```

---

## ✨ Features
| Module | Description |
|---|---|
| 🔬 AI Diagnostic | Enter symptoms → AI ranks probable causes + repair steps |
| 🖥️ PCB Analyzer | Upload PCB photo → detect burned parts, corrosion, shorts |
| 🔩 Component ID | Upload component image → get full specs + replacements |
| 🔧 Repair Guide | Generate step-by-step repair procedures by skill level |
| ⚙️ Circuit AI | Upload circuit diagram → explain power/signal flow |
| 📚 Learning Center | 20+ AI-powered lessons on electronics & repair topics |
| 📋 Repair History | SQLite-stored records, searchable, with PDF export |
| 📄 PDF Reports | Professional reports with device info + diagnosis |

---

## 🔧 Troubleshooting

**"No module named flask"** → Run `pip install -r requirements.txt`

**"API key error"** → Make sure ANTHROPIC_API_KEY is set correctly

**Port already in use** → Change port in app.py: `app.run(port=5001)`

---

## 🔮 Future Ready
Architecture supports future upgrades:
- Authentication & multi-user
- Inventory management
- Spare parts catalog
- Advanced AI models
