from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import shutil
import time
import os

# Configuração de caminhos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "db.sqlite")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Tempo de bloqueio: 300 segundos = 5 minutos
TEMPO_LIMITE_RESERVA = 300 

def conectar_banco():
    # O timeout=10 impede o "Internal Server Error" se o banco estiver ocupado
    return sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)

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
            c.execute("INSERT INTO assentos (numero, status, timestamp) VALUES (?, 'livre', 0)", (i,))
        conn.commit()
    conn.close()

inicializar_banco()

def limpar_reservas_expiradas():
    conn = conectar_banco()
    c = conn.cursor()
    agora = int(time.time())
    limite = agora - TEMPO_LIMITE_RESERVA
    # Libera quem está como 'reservado' e passou de 5 minutos
    c.execute("UPDATE assentos SET status='livre', timestamp=0 WHERE status='reservado' AND timestamp < ?", (limite,))
    conn.commit()
    conn.close()

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
    
    # Só reserva se o assento estiver realmente 'livre'
    c.execute("UPDATE assentos SET status='reservado', timestamp=? WHERE numero=? AND status='livre'", (agora, num))
    conn.commit()
    
    c.execute("SELECT status FROM assentos WHERE numero=?", (num,))
    status_atual = c.fetchone()[0]
    conn.close()

    if status_atual == 'reservado':
        return templates.TemplateResponse("form.html", {"request": request, "num": num})
    else:
        return HTMLResponse("<script>alert('Este assento já expirou ou foi pego por outro!'); window.location.href='/';</script>")

@app.post("/confirmar")
async def confirmar(
    assento: int = Form(...), 
    nome: str = Form(...), 
    nascimento: str = Form(...), 
    pai: str = Form(...), 
    mae: str = Form(...), 
    pagamento: str = Form(...),
    comprovante: UploadFile = File(...)
):
    # Salva o comprovante
    extensao = comprovante.filename.split(".")[-1]
    nome_foto = f"comprovante_assento_{assento}.{extensao}"
    caminho_foto = os.path.join(BASE_DIR, nome_foto)
    
    with open(caminho_foto, "wb") as buffer:
        shutil.copyfileobj(comprovante.file, buffer)

    conn = conectar_banco()
    c = conn.cursor()
    # Atualiza para 'pago' (isso trava o assento definitivamente)
    c.execute("""
        UPDATE assentos 
        SET status='pago', nome=?, nascimento=?, pai=?, mae=?, pagamento=?, timestamp=0 
        WHERE numero=?
    """, (nome, nascimento, pai, mae, pagamento, assento))
    conn.commit()
    conn.close()

    return HTMLResponse("""
        <html>
            <body style='background:#1a1a2e;color:white;text-align:center;padding-top:100px;font-family:sans-serif;'>
                <h1>✅ Reserva Confirmada!</h1>
                <p>Obrigado! Sua vaga está garantida.</p>
                <script>setTimeout(()=>window.location.href='/', 3000)</script>
            </body>
        </html>
    """)