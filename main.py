from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import shutil
import time
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Configuração do Banco de Dados e Inicialização
DB_PATH = "db.sqlite"

def inicializar_banco():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Cria a tabela se ela não existir
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
    # Verifica se precisa criar os 60 assentos iniciais
    c.execute("SELECT COUNT(*) FROM assentos")
    if c.fetchone()[0] == 0:
        for i in range(1, 61):
            c.execute("INSERT INTO assentos (numero, status, timestamp) VALUES (?, 'livre', 0)", (i,))
        conn.commit()
    conn.close()

# Chama a inicialização ao iniciar o app
inicializar_banco()

# Tempo de bloqueio (em segundos). 600 segundos = 10 minutos
TEMPO_LIMITE_RESERVA = 600 

def limpar_reservas_expiradas():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    agora = int(time.time())
    limite = agora - TEMPO_LIMITE_RESERVA
    c.execute("UPDATE assentos SET status='livre', timestamp=0 WHERE status='reservado' AND timestamp < ?", (limite,))
    conn.commit()
    conn.close()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    limpar_reservas_expiradas()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT numero, status FROM assentos")
    dados = c.fetchall()
    conn.close()
    return templates.TemplateResponse(request=request, name="index.html", context={"assentos": dados})

@app.get("/reservar/{num}", response_class=HTMLResponse)
async def reservar(request: Request, num: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    agora = int(time.time())
    # Tenta reservar
    c.execute("UPDATE assentos SET status='reservado', timestamp=? WHERE numero=? AND status='livre'", (agora, num))
    conn.commit()
    # Verifica sucesso
    c.execute("SELECT status FROM assentos WHERE numero=?", (num,))
    resultado = c.fetchone()
    conn.close()

    if resultado and resultado[0] == 'reservado':
        return templates.TemplateResponse(request=request, name="form.html", context={"num": num})
    else:
        return HTMLResponse("<script>alert('Este assento já está ocupado ou reservado!'); window.location.href='/';</script>")

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
    # Salva o arquivo de comprovante
    extensao = comprovante.filename.split(".")[-1]
    nome_foto = f"comprovante_assento_{assento}.{extensao}"
    with open(nome_foto, "wb") as buffer:
        shutil.copyfileobj(comprovante.file, buffer)

    # Finaliza no banco
    conn = sqlite3.connect(DB_PATH)
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