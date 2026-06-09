#!/bin/bash
# ============================================================
#  STECH Electronics Diagnostic AI — Setup & Run Script
# ============================================================

echo ""
echo "  ⚡ STECH Electronics Diagnostic AI"
echo "  ======================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "  ❌ Python3 not found. Please install Python 3.9+"
    exit 1
fi

# Install dependencies
echo "  📦 Installing dependencies..."
pip3 install -r requirements.txt -q

# Check API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo ""
    echo "  ⚠️  ANTHROPIC_API_KEY not set!"
    echo "  Please set it:"
    echo "    export ANTHROPIC_API_KEY=your-key-here"
    echo "  Then run: python3 app.py"
    echo ""
else
    echo "  ✅ API key found"
    echo ""
    echo "  🚀 Starting server at http://127.0.0.1:5000"
    echo ""
    python3 app.py
fi
