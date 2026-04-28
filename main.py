from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
import shutil
import os
import time

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Conexão com Banco de Dados
def get_db():
    conn = sqlite3.connect("db.sqlite", check_same_thread=False)
    return conn

conn = get_db()
c = conn.cursor()

# Criar tabela com todas as colunas necessárias
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

# Iniciar assentos se o banco estiver vazio (1 a 60)
c.execute("SELECT COUNT(*) FROM assentos")
if c.fetchone()[0] == 0:
    for i in range(1, 61):
        c.execute("INSERT INTO assentos VALUES (?, 'livre', 0, '', '', '', '', '')", (i,))
    conn.commit()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    c.execute("SELECT numero, status FROM assentos")
    dados = c.fetchall()
    return templates.TemplateResponse(
        request=request, name="index.html", context={"assentos": dados}
    )

@app.get("/reservar/{num}", response_class=HTMLResponse)
async def reservar(request: Request, num: int):
    # --- O PULO DO GATO ESTÁ AQUI ---
    # Assim que ele clica, o status muda para 'reservado' no banco
    # O timestamp serve para você saber quando a reserva começou (opcional)
    c.execute("UPDATE assentos SET status='reservado', timestamp=? WHERE numero=? AND status='livre'", (int(time.time()), num))
    conn.commit()
    
    return templates.TemplateResponse(
        request=request, name="form.html", context={"num": num}
    )

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
    # 1. Salva a foto do comprovante
    extensao = comprovante.filename.split(".")[-1]
    nome_foto = f"comprovante_assento_{assento}.{extensao}"
    with open(nome_foto, "wb") as buffer:
        shutil.copyfileobj(comprovante.file, buffer)

    # 2. Atualiza o Banco de Dados para 'pago' e preenche os dados
    c.execute("""
        UPDATE assentos 
        SET status='pago', nome=?, nascimento=?, pai=?, mae=?, pagamento=? 
        WHERE numero=?
    """, (nome, nascimento, pai, mae, pagamento, assento))
    conn.commit()

    # 3. Gera o arquivo TXT com os dados da reserva
    with open(f"reserva_{assento}.txt", "w", encoding="utf-8") as f:
        f.write(f"Assento: {assento}\nNome: {nome}\nPagamento: {pagamento}\nFoto: {nome_foto}")

    # 4. Tela de Sucesso que fecha a aba após 3 segundos
    return HTMLResponse("""
        <html>
            <body style='background:#1a1a2e;color:white;text-align:center;padding-top:100px;font-family:sans-serif;'>
                <h1>✅ Comprovante Recebido!</h1>
                <p>Sua reserva foi finalizada com sucesso. Esta aba será fechada.</p>
                <script>setTimeout(()=>window.close(), 3000)</script>
            </body>
        </html>
    """)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)