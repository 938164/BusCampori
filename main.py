from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import shutil
import time
import os

# CONFIGURAÇÃO DE CAMINHOS
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = "/tmp/campori_v3.db" 
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# 1. INICIALIZAÇÃO DO BANCO
def inicializar_banco():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=20)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS assentos (
        numero INTEGER PRIMARY KEY,
        status TEXT,
        timestamp INTEGER
    )
    """)
    c.execute("SELECT COUNT(*) FROM assentos")
    if c.fetchone()[0] == 0:
        for i in range(1, 61):
            c.execute("INSERT INTO assentos (numero, status, timestamp) VALUES (?, 'livre', 0)", (i,))
        conn.commit()
    conn.close()

inicializar_banco()

# 2. FUNÇÃO DE LIMPEZA (5 MINUTOS)
def limpar_reservas():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=20)
    agora = int(time.time())
    limite = agora - 300 # 5 minutos
    conn.execute("UPDATE assentos SET status='livre', timestamp=0 WHERE status='reservado' AND timestamp < ?", (limite,))
    conn.commit()
    conn.close()

# 3. ROTA DA PÁGINA INICIAL (CORRIGIDA)
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    limpar_reservas()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT numero, status FROM assentos")
    dados = c.fetchall()
    conn.close()
    
    # FORMATO CORRETO PARA AS VERSÕES NOVAS DO FASTAPI:
    return templates.TemplateResponse(
        name="index.html", 
        context={"request": request, "assentos": dados}
    )

# 4. ROTA DE RESERVA
@app.get("/reservar/{num}", response_class=HTMLResponse)
async def reservar(request: Request, num: int):
    limpar_reservas()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    agora = int(time.time())
    conn.execute("UPDATE assentos SET status='reservado', timestamp=? WHERE numero=? AND status='livre'", (agora, num))
    conn.commit()
    
    c = conn.cursor()
    c.execute("SELECT status FROM assentos WHERE numero=?", (num,))
    res = c.fetchone()
    conn.close()

    if res and res[0] == 'reservado':
        return templates.TemplateResponse(
            name="form.html", 
            context={"request": request, "num": num}
        )
    return HTMLResponse("<script>alert('Assento ocupado!'); window.location.href='/';</script>")

# 5. ROTA DE CONFIRMAÇÃO
@app.post("/confirmar")
async def confirmar(assento: int = Form(...), comprovante: UploadFile = File(...)):
    # Salva foto em local temporário
    foto_path = f"/tmp/comprovante_{assento}.jpg"
    with open(foto_path, "wb") as buffer:
        shutil.copyfileobj(comprovante.file, buffer)

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("UPDATE assentos SET status='pago', timestamp=0 WHERE numero=?", (assento,))
    conn.commit()
    conn.close()
    
    return HTMLResponse("<h1>✅ Sucesso!</h1><script>setTimeout(()=>window.location.href='/', 2000)</script>")