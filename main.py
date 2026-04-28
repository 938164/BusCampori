from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import shutil
import time
import os

# 1. Configura o caminho absoluto das pastas (Evita erro de pasta não encontrada)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "db.sqlite")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# 2. Inicialização Segura do Banco
def inicializar_banco():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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

TEMPO_LIMITE_RESERVA = 600 

def limpar_reservas_expiradas():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    agora = int(time.time())
    limite = agora - TEMPO_LIMITE_RESERVA
    c.execute("UPDATE assentos SET status='livre', timestamp=0 WHERE status='reservado' AND timestamp < ?", (limite,))
    conn.commit()
    conn.close()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    limpar_reservas_expiradas()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT numero, status FROM assentos")
    dados = c.fetchall()
    conn.close()
    return templates.TemplateResponse("index.html", {"request": request, "assentos": dados})

@app.get("/reservar/{num}", response_class=HTMLResponse)
async def reservar(request: Request, num: int):
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    agora = int(time.time())
    # Tenta reservar apenas se estiver livre
    c.execute("UPDATE assentos SET status='reservado', timestamp=? WHERE numero=? AND status='livre'", (agora, num))
    conn.commit()
    
    c.execute("SELECT status FROM assentos WHERE numero=?", (num,))
    status_atual = c.fetchone()[0]
    conn.close()

    if status_atual == 'reservado':
        return templates.TemplateResponse("form.html", {"request": request, "num": num})
    else:
        return HTMLResponse("<script>alert('Assento já reservado por outro usuário!'); window.location.href='/';</script>")

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
    # Salva o arquivo na pasta raiz do projeto
    extensao = comprovante.filename.split(".")[-1]
    nome_foto = f"comprovante_assento_{assento}.{extensao}"
    caminho_foto = os.path.join(BASE_DIR, nome_foto)
    
    with open(caminho_foto, "wb") as buffer:
        shutil.copyfileobj(comprovante.file, buffer)

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
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
                <h1>✅ Sucesso! Assento confirmado.</h1>
                <p>Sua reserva foi processada. Você será redirecionado.</p>
                <script>setTimeout(()=>window.location.href='/', 3000)</script>
            </body>
        </html>
    """)