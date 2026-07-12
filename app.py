import os
import sqlite3
import hashlib
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'alexandre_dorper_chave_secreta_2026'

DATABASE = 'database.db'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_IMAGE_SIZE

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                bio TEXT DEFAULT '',
                data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS dicas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                categoria TEXT DEFAULT 'geral',
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            );

            CREATE TABLE IF NOT EXISTS fotos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                arquivo TEXT NOT NULL,
                legenda TEXT DEFAULT '',
                data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            );

            CREATE TABLE IF NOT EXISTS enciclopedia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                categoria TEXT DEFAULT 'geral',
                fonte TEXT DEFAULT '',
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        db.commit()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/enciclopedia')
def enciclopedia():
    db = get_db()
    artigos = db.execute('SELECT * FROM enciclopedia ORDER BY data_criacao DESC').fetchall()
    return render_template('enciclopedia.html', artigos=artigos)

@app.route('/galeria')
def galeria():
    db = get_db()
    fotos = db.execute('''
        SELECT fotos.*, usuarios.nome 
        FROM fotos 
        JOIN usuarios ON fotos.usuario_id = usuarios.id 
        ORDER BY fotos.data_upload DESC
    ''').fetchall()
    return render_template('galeria.html', fotos=fotos)

@app.route('/dicas')
def dicas():
    db = get_db()
    todas_dicas = db.execute('''
        SELECT dicas.*, usuarios.nome 
        FROM dicas 
        JOIN usuarios ON dicas.usuario_id = usuarios.id 
        ORDER BY dicas.data_criacao DESC
    ''').fetchall()
    return render_template('dicas.html', dicas=todas_dicas)

@app.route('/universidades')
def universidades():
    db = get_db()
    artigos = db.execute('''
        SELECT * FROM enciclopedia 
        WHERE categoria = 'universidade' OR fonte != '' 
        ORDER BY data_criacao DESC
    ''').fetchall()
    return render_template('universidades.html', artigos=artigos)

# ---- Autenticação ----

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = hashlib.sha256(request.form['senha'].encode()).hexdigest()
        
        try:
            db = get_db()
            db.execute(
                'INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)',
                (nome, email, senha)
            )
            db.commit()
            flash('Cadastro realizado com sucesso! Faça login.', 'success')
            return redirect(url_for('entrar'))
        except sqlite3.IntegrityError:
            flash('Este e-mail já está cadastrado!', 'error')
    
    return render_template('cadastro.html')

@app.route('/entrar', methods=['GET', 'POST'])
def entrar():
    if request.method == 'POST':
        email = request.form['email']
        senha = hashlib.sha256(request.form['senha'].encode()).hexdigest()
        
        db = get_db()
        user = db.execute(
            'SELECT * FROM usuarios WHERE email = ? AND senha = ?',
            (email, senha)
        ).fetchone()
        
        if user:
            session['user_id'] = user['id']
            session['user_nome'] = user['nome']
            flash(f'Bem-vindo, {user["nome"]}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('E-mail ou senha incorretos!', 'error')
    
    return render_template('entrar.html')

@app.route('/sair')
def sair():
    session.clear()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('index'))

# ---- Galeria (Upload de Fotos) ----

@app.route('/upload_foto', methods=['GET', 'POST'])
def upload_foto():
    if 'user_id' not in session:
        flash('Faça login para enviar fotos!', 'error')
        return redirect(url_for('entrar'))
    
    if request.method == 'POST':
        if 'foto' not in request.files:
            flash('Nenhum arquivo selecionado.', 'error')
            return redirect(request.url)
        
        file = request.files['foto']
        legenda = request.form.get('legenda', '')
        
        if file.filename == '':
            flash('Nenhum arquivo selecionado.', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{session['user_id']}_{int(__import__('time').time())}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            db = get_db()
            db.execute(
                'INSERT INTO fotos (usuario_id, arquivo, legenda) VALUES (?, ?, ?)',
                (session['user_id'], filename, legenda)
            )
            db.commit()
            
            flash('Foto enviada com sucesso!', 'success')
            return redirect(url_for('galeria'))
        else:
            flash('Formato de arquivo não permitido. Use PNG, JPG, JPEG ou GIF.', 'error')
    
    return render_template('upload_foto.html')

@app.route('/deletar_foto/<int:foto_id>', methods=['POST'])
def deletar_foto(foto_id):
    if 'user_id' not in session:
        return jsonify({'erro': 'Não autorizado'}), 401
    
    db = get_db()
    foto = db.execute('SELECT * FROM fotos WHERE id = ?', (foto_id,)).fetchone()
    
    if not foto:
        return jsonify({'erro': 'Foto não encontrada'}), 404
    
    if foto['usuario_id'] != session['user_id']:
        return jsonify({'erro': 'Você só pode deletar suas próprias fotos'}), 403
    
    # Deletar o arquivo
    caminho = os.path.join(app.config['UPLOAD_FOLDER'], foto['arquivo'])
    if os.path.exists(caminho):
        os.remove(caminho)
    
    db.execute('DELETE FROM fotos WHERE id = ?', (foto_id,))
    db.commit()
    
    flash('Foto deletada com sucesso!', 'success')
    return redirect(url_for('galeria'))

# ---- Dicas / Fórum ----

@app.route('/nova_dica', methods=['GET', 'POST'])
def nova_dica():
    if 'user_id' not in session:
        flash('Faça login para publicar dicas!', 'error')
        return redirect(url_for('entrar'))
    
    if request.method == 'POST':
        titulo = request.form['titulo']
        conteudo = request.form['conteudo']
        categoria = request.form.get('categoria', 'geral')
        
        db = get_db()
        db.execute(
            'INSERT INTO dicas (usuario_id, titulo, conteudo, categoria) VALUES (?, ?, ?, ?)',
            (session['user_id'], titulo, conteudo, categoria)
        )
        db.commit()
        
        flash('Dica publicada com sucesso!', 'success')
        return redirect(url_for('dicas'))
    
    return render_template('nova_dica.html')

@app.route('/deletar_dica/<int:dica_id>', methods=['POST'])
def deletar_dica(dica_id):
    if 'user_id' not in session:
        return jsonify({'erro': 'Não autorizado'}), 401
    
    db = get_db()
    dica = db.execute('SELECT * FROM dicas WHERE id = ?', (dica_id,)).fetchone()
    
    if not dica:
        return jsonify({'erro': 'Dica não encontrada'}), 404
    
    if dica['usuario_id'] != session['user_id']:
        return jsonify({'erro': 'Você só pode deletar suas próprias dicas'}), 403
    
    db.execute('DELETE FROM dicas WHERE id = ?', (dica_id,))
    db.commit()
    
    flash('Dica deletada!', 'success')
    return redirect(url_for('dicas'))

# ---- Admin (popula enciclopédia) ----

@app.route('/admin/enciclopedia/nova', methods=['GET', 'POST'])
def admin_nova_enciclopedia():
    if 'user_id' not in session:
        return redirect(url_for('entrar'))
    
    if request.method == 'POST':
        titulo = request.form['titulo']
        conteudo = request.form['conteudo']
        categoria = request.form.get('categoria', 'geral')
        fonte = request.form.get('fonte', '')
        
        db = get_db()
        db.execute(
            'INSERT INTO enciclopedia (titulo, conteudo, categoria, fonte) VALUES (?, ?, ?, ?)',
            (titulo, conteudo, categoria, fonte)
        )
        db.commit()
        
        flash('Artigo adicionado à enciclopédia!', 'success')
        return redirect(url_for('enciclopedia'))
    
    return render_template('admin_enciclopedia.html')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
