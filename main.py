from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import shutil
import time
import os

# CONFIGURAÇÃO DE CAMINHOS - O segredo para o Render não dar erro
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# No Render, a pasta /tmp tem permissão de escrita garantida
DB_PATH = "/tmp/db.sqlite" 
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)

TEMPO_LIMITE_RESERVA = 300 # 5 minutos

def conectar_banco():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=20)
    conn.execute("PRAGMA journal_mode=WAL;") # Modo de alta performance
    return conn

def inicializar_banco():
    conn = conectar_banco()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS assentos (
        numero INTEGER PRIMARY KEY,
        status TEXT,
        timestamp INTEGER,
        nome TEXT,
        nascimento TEXT,
        pai TEXT,
        mae TEXT,
        pagamento TEXT
    )
    """)
    c.execute("SELECT COUNT(*) FROM assentos")
    if c.fetchone()[0] == 0:
        for i in range(1, 61):
            c.execute("INSERT INTO assentos (numero, status, timestamp, nome, nascimento, pai, mae, pagamento) VALUES (?, 'livre', 0, '', '', '', '', '')", (i,))
        conn.commit()
    conn.close()

# Tenta inicializar o banco. Se falhar, o log do Render dirá o porquê.
try:
    inicializar_banco()
except Exception as e:
    print(f"Erro ao iniciar banco: {e}")

def limpar_reservas_expiradas():
    try:
        conn = conectar_banco()
        c = conn.cursor()
        agora = int(time.time())
        limite = agora - TEMPO_LIMITE_RESERVA
        c.execute("UPDATE assentos SET status='livre', timestamp=0 WHERE status='reservado' AND timestamp < ?", (limite,))
        conn.commit()
        conn.close()
    except:
        pass

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    limpar_reservas_expiradas()
    conn = conectar_banco()
    c = conn.cursor()
    c.execute("SELECT numero, status FROM assentos")
    dados = c.fetchall()
    conn.close()
    return templates.TemplateResponse("index.html", {"request": request, "assentos": dados})

@app.get("/reservar/{num}", response_class=HTMLResponse)
async def reservar(request: Request, num: int):
    limpar_reservas_expiradas()
    conn = conectar_banco()
    c = conn.cursor()
    agora = int(time.time())
    c.execute("UPDATE assentos SET status='reservado', timestamp=? WHERE numero=? AND status='livre'", (agora, num))
    conn.commit()
    c.execute("SELECT status FROM assentos WHERE numero=?", (num,))
    res = c.fetchone()
    conn.close()
    if res and res[0] == 'reservado':
        return templates.TemplateResponse("form.html", {"request": request, "num": num})
    return HTMLResponse("<script>alert('Assento ocupado!'); window.location.href='/';</script>")

@app.post("/confirmar")
async def confirmar(
    assento: int = Form(...), nome: str = Form(...), nascimento: str = Form(...), 
    pai: str = Form(...), mae: str = Form(...), pagamento: str = Form(...),
    comprovante: UploadFile = File(...)
):
    # Salva foto na pasta temporária para evitar erro de permissão
    nome_foto = f"comprovante_{assento}.jpg"
    caminho_foto = os.path.join("/tmp", nome_foto)
    with open(caminho_foto, "wb") as buffer:
        shutil.copyfileobj(comprovante.file, buffer)

    conn = conectar_banco()
    c = conn.cursor()
    c.execute("UPDATE assentos SET status='pago', nome=?, nascimento=?, pai=?, mae=?, pagamento=?, timestamp=0 WHERE numero=?", 
              (nome, nascimento, pai, mae, pagamento, assento))
    conn.commit()
    conn.close()
    return HTMLResponse("<h1>Reserva Confirmada!</h1><script>setTimeout(()=>window.location.href='/', 3000)</script>")