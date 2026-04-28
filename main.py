from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import shutil
import time
import os

# Configuração de caminhos absolutos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "db.sqlite")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Tempo de bloqueio: 300 segundos = 5 minutos
TEMPO_LIMITE_RESERVA = 300 

def conectar_banco():
    # check_same_thread=False e timeout=10 evitam o "Internal Server Error"
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    # PRAGMA WAL permite que várias pessoas acessem o site ao mesmo tempo sem travar
    conn.execute("PRAGMA journal_mode=WAL;")
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

# Inicia o banco de dados assim que o servidor liga
inicializar_banco()

def limpar_reservas_expiradas():
    """Libera assentos que foram clicados mas não finalizados em 5 minutos."""
    conn = conectar_banco()
    c = conn.cursor()
    agora = int(time.time())
    limite = agora - TEMPO_LIMITE_RESERVA
    # Se o status for 'reservado' e o tempo passou do limite, volta para 'livre'
    c.execute("UPDATE assentos SET status='livre', timestamp=0 WHERE status='reservado' AND timestamp < ?", (limite,))
    conn.commit()
    conn.close()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    limpar_reservas_expiradas() # Faxina nos desistentes
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
    
    # Só muda para reservado se o assento estiver LIVRE
    c.execute("UPDATE assentos SET status='reservado', timestamp=? WHERE numero=? AND status='livre'", (agora, num))
    conn.commit()
    
    c.execute("SELECT status FROM assentos WHERE numero=?", (num,))
    resultado = c.fetchone()
    conn.close()

    if resultado and resultado[0] == 'reservado':
        return templates.TemplateResponse("form.html", {"request": request, "num": num})
    else:
        # Se alguém já pegou, avisa o usuário
        return HTMLResponse("<script>alert('Assento ocupado ou reserva expirada!'); window.location.href='/';</script>")

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
    # 1. Salva o arquivo de comprovante no Render
    extensao = comprovante.filename.split(".")[-1]
    nome_foto = f"comprovante_{assento}_{int(time.time())}.{extensao}"
    caminho_foto = os.path.join(BASE_DIR, nome_foto)
    with open(caminho_foto, "wb") as buffer:
        shutil.copyfileobj(comprovante.file, buffer)

    # 2. Salva definitivamente no banco
    conn = conectar_banco()
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
                <h1>✅ Reserva Confirmada!</h1>
                <p>Obrigado! Sua vaga para o Campori está garantida.</p>
                <script>setTimeout(()=>window.location.href='/', 3000)</script>
            </body>
        </html>
    """)