import math
import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit, join_room
import eventlet
from werkzeug.utils import secure_filename
from config import Config
from translate_service import translation_service
from security import security_manager

# Configuration de l'application
app = Flask(__name__)
app.config.from_object(Config)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Initialisation de la base de données
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Configuration des fichiers
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {
    'images': {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'},
    'videos': {'mp4', 'mov', 'avi', 'mkv', 'webm'},
    'audio': {'mp3', 'wav', 'ogg', 'm4a'},
    'documents': {'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'},
    'spreadsheets': {'xls', 'xlsx', 'csv', 'ods'},
    'presentations': {'ppt', 'pptx', 'odp'},
    'archives': {'zip', 'rar', '7z', 'tar', 'gz'},
    'code': {'py', 'js', 'html', 'css', 'java', 'cpp', 'c'}
}

# Créer les dossiers de téléchargement
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'images'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'videos'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'audio'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'documents'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'others'), exist_ok=True)

def allowed_file(filename):
    """Vérifie si le fichier a une extension autorisée"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in \
           [ext for extensions in app.config['ALLOWED_EXTENSIONS'].values() for ext in extensions]

def get_file_type(filename):
    """Détermine le type de fichier"""
    extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    for file_type, extensions in app.config['ALLOWED_EXTENSIONS'].items():
        if extension in extensions:
            return file_type
    return 'others'

def get_file_icon(filename):
    """Retourne l'icône correspondant au type de fichier"""
    file_type = get_file_type(filename)
    
    icons = {
        'images': 'fa-image',
        'videos': 'fa-video',
        'audio': 'fa-music',
        'documents': 'fa-file-alt',
        'spreadsheets': 'fa-file-excel',
        'presentations': 'fa-file-powerpoint',
        'archives': 'fa-file-archive',
        'code': 'fa-file-code',
        'others': 'fa-file'
    }
    return icons.get(file_type, 'fa-file')

def format_file_size(size_bytes):
    """Formater la taille des fichiers"""
    if size_bytes == 0:
        return "0 Bytes"
    
    size_names = ("Bytes", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    
    return f"{s} {size_names[i]}"

# Modèles de données
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    language = db.Column(db.String(10), default='fr')
    theme = db.Column(db.String(20), default='light')
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(32))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_online = db.Column(db.Boolean, default=False)
    profile_picture = db.Column(db.String(200), default='default.png')
    status = db.Column(db.String(100), default='En ligne')
    
    # Relations
    contacts = db.relationship('Contact', foreign_keys='Contact.user_id', backref='user', lazy=True)
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    messages_received = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy=True)

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_blocked = db.Column(db.Boolean, default=False)
    nickname = db.Column(db.String(100))

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    translated_content = db.Column(db.Text)
    original_language = db.Column(db.String(10))
    translated_language = db.Column(db.String(10))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    is_delivered = db.Column(db.Boolean, default=False)
    message_type = db.Column(db.String(20), default='text')
    file_url = db.Column(db.String(500))
    file_name = db.Column(db.String(255))
    file_size = db.Column(db.Integer)
    file_type = db.Column(db.String(50))
    thumbnail_url = db.Column(db.String(500))
    duration = db.Column(db.Integer)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    contact_info = db.Column(db.Text)

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    group_picture = db.Column(db.String(200), default='group_default.png')

class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)

class GroupMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    translated_contents = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes de l'application
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        two_factor_code = request.form.get('two_factor_code')
        
        user = User.query.filter_by(username=username).first()
        
        if user and security_manager.check_password(password, user.password_hash):
            # Vérifier l'authentification à deux facteurs si activée
            if user.two_factor_enabled:
                if not two_factor_code or not security_manager.verify_2fa_code(user.two_factor_secret, two_factor_code):
                    flash('Code d\'authentification à deux facteurs incorrect', 'error')
                    return render_template('login.html')
            
            login_user(user)
            user.is_online = True
            user.last_seen = datetime.utcnow()
            db.session.commit()
            
            # Rediriger vers le chat
            next_page = request.args.get('next')
            return redirect(next_page or url_for('chat'))
        else:
            flash('Nom d\'utilisateur ou mot de passe incorrect', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        language = request.form.get('language', 'fr')
        
        # Validation
        if password != confirm_password:
            flash('Les mots de passe ne correspondent pas', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Ce nom d\'utilisateur est déjà pris', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Cet email est déjà utilisé', 'error')
            return render_template('register.html')
        
        # Créer l'utilisateur
        hashed_password = security_manager.hash_password(password)
        user = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            language=language
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('Compte créé avec succès! Vous pouvez maintenant vous connecter.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    if current_user.is_authenticated:
        current_user.is_online = False
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
    
    logout_user()
    return redirect(url_for('index'))

@app.route('/chat')
@login_required
def chat():
    # Récupérer les contacts
    contacts = Contact.query.filter_by(user_id=current_user.id).all()
    contact_list = []
    
    for contact in contacts:
        contact_user = User.query.get(contact.contact_id)
        if contact_user:
            contact_list.append({
                'id': contact_user.id,
                'username': contact_user.username,
                'status': contact_user.status,
                'is_online': contact_user.is_online,
                'language': contact_user.language,
                'profile_picture': contact_user.profile_picture,
                'last_seen': contact_user.last_seen.strftime('%H:%M') if contact_user.last_seen else ''
            })
    
    # Récupérer les groupes
    groups = GroupMember.query.filter_by(user_id=current_user.id).all()
    group_list = []
    
    for member in groups:
        group = Group.query.get(member.group_id)
        if group:
            group_list.append({
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'member_count': GroupMember.query.filter_by(group_id=group.id).count()
            })
    
    return render_template('chat.html', 
                          contacts=contact_list,
                          groups=group_list,
                          user_language=current_user.language)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        # Mettre à jour les paramètres
        current_user.language = request.form.get('language', current_user.language)
        current_user.theme = request.form.get('theme', current_user.theme)
        current_user.status = request.form.get('status', current_user.status)
        
        # Gérer l'authentification à deux facteurs
        enable_2fa = request.form.get('enable_2fa') == 'on'
        
        if enable_2fa and not current_user.two_factor_enabled:
            current_user.two_factor_secret = security_manager.generate_2fa_secret()
            current_user.two_factor_enabled = True
        elif not enable_2fa:
            current_user.two_factor_enabled = False
        
        db.session.commit()
        flash('Paramètres mis à jour avec succès', 'success')
        
        if enable_2fa and current_user.two_factor_enabled:
            # Générer le QR code
            qr_code = security_manager.generate_2fa_qr_code(
                current_user.two_factor_secret,
                current_user.username
            )
            return render_template('settings.html', qr_code=qr_code)
    
    return render_template('settings.html')

@app.route('/contacts')
@login_required
def contacts():
    # Récupérer tous les utilisateurs (sauf soi-même)
    all_users = User.query.filter(User.id != current_user.id).all()
    
    # Récupérer les contacts existants
    existing_contacts = Contact.query.filter_by(user_id=current_user.id).all()
    contact_ids = [c.contact_id for c in existing_contacts]
    
    users = []
    for user in all_users:
        users.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'language': user.language,
            'is_online': user.is_online,
            'is_contact': user.id in contact_ids
        })
    
    return render_template('contacts.html', users=users)

@app.route('/add_contact/<int:contact_id>', methods=['POST'])
@login_required
def add_contact(contact_id):
    # Vérifier si le contact existe déjà
    existing = Contact.query.filter_by(user_id=current_user.id, contact_id=contact_id).first()
    
    if not existing:
        contact = Contact(
            user_id=current_user.id,
            contact_id=contact_id
        )
        db.session.add(contact)
        db.session.commit()
        flash('Contact ajouté avec succès', 'success')
    else:
        flash('Ce contact existe déjà', 'info')
    
    return redirect(url_for('contacts'))

@app.route('/get_messages/<int:contact_id>')
@login_required
def get_messages(contact_id):
    # Récupérer les messages entre l'utilisateur courant et le contact
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == contact_id)) |
        ((Message.sender_id == contact_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()
    
    messages_list = []
    for msg in messages:
        messages_list.append({
            'id': msg.id,
            'sender_id': msg.sender_id,
            'content': msg.content,
            'translated_content': msg.translated_content,
            'timestamp': msg.timestamp.strftime('%H:%M'),
            'is_read': msg.is_read,
            'message_type': msg.message_type,
            'file_url': msg.file_url,
            'file_name': msg.file_name,
            'file_size': msg.file_size
        })
    
    return jsonify({'messages': messages_list})

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    content = data.get('content')
    message_type = data.get('message_type', 'text')
    
    if not receiver_id or not content:
        return jsonify({'error': 'Données manquantes'}), 400
    
    # Récupérer les langues des utilisateurs
    sender_lang = current_user.language
    receiver = User.query.get(receiver_id)
    
    if not receiver:
        return jsonify({'error': 'Destinataire non trouvé'}), 404
    
    receiver_lang = receiver.language
    
    # Traduire le message si nécessaire
    translated_content = content
    if sender_lang != receiver_lang:
        translated_content = translation_service.translate_message(
            content, sender_lang, receiver_lang
        )
    
    # Créer le message
    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content,
        translated_content=translated_content,
        original_language=sender_lang,
        translated_language=receiver_lang,
        message_type=message_type,
        is_delivered=True
    )
    
    db.session.add(message)
    db.session.commit()
    
    # Émettre l'événement SocketIO
    socketio.emit('new_message', {
        'message_id': message.id,
        'sender_id': current_user.id,
        'receiver_id': receiver_id,
        'content': content,
        'translated_content': translated_content,
        'timestamp': message.timestamp.strftime('%H:%M'),
        'sender_name': current_user.username,
        'sender_language': sender_lang,
        'receiver_language': receiver_lang
    }, room=f'user_{receiver_id}')
    
    return jsonify({
        'success': True,
        'message_id': message.id,
        'translated_content': translated_content
    })

@app.route('/upload_file', methods=['POST'])
@login_required
def upload_file():
    """Route pour télécharger des fichiers"""
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    file = request.files['file']
    receiver_id = request.form.get('receiver_id')
    
    if not receiver_id:
        return jsonify({'error': 'Destinataire non spécifié'}), 400
    
    if file.filename == '':
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    if file and allowed_file(file.filename):
        # Sécuriser le nom du fichier
        original_filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{current_user.id}_{original_filename}"
        
        # Déterminer le type de fichier et le dossier cible
        file_type = get_file_type(original_filename)
        subfolder = file_type if file_type in ['images', 'videos', 'audio', 'documents'] else 'others'
        
        # Chemin de sauvegarde
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], subfolder, unique_filename)
        file.save(save_path)
        
        # URL pour accéder au fichier
        file_url = f"/{save_path}"
        
        # Taille du fichier
        file_size = os.path.getsize(save_path)
        
        # Récupérer les informations de traduction
        sender_lang = current_user.language
        receiver = User.query.get(receiver_id)
        receiver_lang = receiver.language if receiver else sender_lang
        
        # Créer le message
        file_message = Message(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            content=f"📎 Fichier: {original_filename}",
            translated_content=f"📎 File: {original_filename}",
            original_language=sender_lang,
            translated_language=receiver_lang,
            message_type='file',
            file_url=file_url,
            file_name=original_filename,
            file_size=file_size,
            file_type=file_type
        )
        
        db.session.add(file_message)
        db.session.commit()
        
        # Émettre l'événement SocketIO
        socketio.emit('new_file_message', {
            'message_id': file_message.id,
            'sender_id': current_user.id,
            'receiver_id': receiver_id,
            'filename': original_filename,
            'file_url': file_url,
            'file_type': file_type,
            'file_size': file_size,
            'timestamp': file_message.timestamp.strftime('%H:%M'),
            'sender_name': current_user.username,
            'icon': get_file_icon(original_filename)
        }, room=f'user_{receiver_id}')
        
        return jsonify({
            'success': True,
            'message_id': file_message.id,
            'filename': original_filename,
            'file_url': file_url,
            'file_type': file_type,
            'file_size': file_size
        })
    
    return jsonify({'error': 'Type de fichier non autorisé'}), 400

@app.route('/upload_multiple_files', methods=['POST'])
@login_required
def upload_multiple_files():
    """Route pour télécharger plusieurs fichiers"""
    if 'files[]' not in request.files:
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    files = request.files.getlist('files[]')
    receiver_id = request.form.get('receiver_id')
    
    if not receiver_id:
        return jsonify({'error': 'Destinataire non spécifié'}), 400
    
    uploaded_files = []
    
    for file in files:
        if file and file.filename != '' and allowed_file(file.filename):
            # Sécuriser le nom du fichier
            original_filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_filename = f"{timestamp}_{current_user.id}_{original_filename}"
            
            # Déterminer le type de fichier
            file_type = get_file_type(original_filename)
            subfolder = file_type if file_type in ['images', 'videos', 'audio', 'documents'] else 'others'
            
            # Chemin de sauvegarde
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], subfolder, unique_filename)
            file.save(save_path)
            
            # URL pour accéder au fichier
            file_url = f"/{save_path}"
            file_size = os.path.getsize(save_path)
            
            uploaded_files.append({
                'filename': original_filename,
                'file_url': file_url,
                'file_type': file_type,
                'file_size': file_size,
                'icon': get_file_icon(original_filename)
            })
    
    if uploaded_files:
        # Créer un message groupé pour les fichiers
        sender_lang = current_user.language
        receiver = User.query.get(receiver_id)
        receiver_lang = receiver.language if receiver else sender_lang
        
        file_names = ', '.join([f['filename'] for f in uploaded_files])
        
        file_message = Message(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            content=f"📦 {len(uploaded_files)} fichiers: {file_names}",
            translated_content=f"📦 {len(uploaded_files)} files: {file_names}",
            original_language=sender_lang,
            translated_language=receiver_lang,
            message_type='multiple_files',
            file_url=json.dumps(uploaded_files)
        )
        
        db.session.add(file_message)
        db.session.commit()
        
        # Émettre l'événement SocketIO
        socketio.emit('new_multiple_files', {
            'message_id': file_message.id,
            'sender_id': current_user.id,
            'receiver_id': receiver_id,
            'files': uploaded_files,
            'count': len(uploaded_files),
            'timestamp': file_message.timestamp.strftime('%H:%M'),
            'sender_name': current_user.username
        }, room=f'user_{receiver_id}')
        
        return jsonify({
            'success': True,
            'message_id': file_message.id,
            'files': uploaded_files,
            'count': len(uploaded_files)
        })
    
    return jsonify({'error': 'Aucun fichier valide téléchargé'}), 400

@app.route('/send_voice_message', methods=['POST'])
@login_required
def send_voice_message():
    """Route pour envoyer des messages vocaux"""
    if 'audio' not in request.files:
        return jsonify({'error': 'Aucun audio enregistré'}), 400
    
    audio_file = request.files['audio']
    receiver_id = request.form.get('receiver_id')
    duration = request.form.get('duration', 0)
    
    if not receiver_id:
        return jsonify({'error': 'Destinataire non spécifié'}), 400
    
    if audio_file and audio_file.filename != '':
        # Générer un nom de fichier unique
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"voice_{timestamp}_{current_user.id}.webm"
        
        # Chemin de sauvegarde
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'audio', filename)
        audio_file.save(save_path)
        
        # URL pour accéder au fichier
        file_url = f"/{save_path}"
        file_size = os.path.getsize(save_path)
        
        # Récupérer les informations de traduction
        sender_lang = current_user.language
        receiver = User.query.get(receiver_id)
        receiver_lang = receiver.language if receiver else sender_lang
        
        # Créer le message vocal
        voice_message = Message(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            content="🎤 Message vocal",
            translated_content="🎤 Voice message",
            original_language=sender_lang,
            translated_language=receiver_lang,
            message_type='voice',
            file_url=file_url,
            file_name=filename,
            file_size=file_size,
            duration=int(duration) if duration else 0
        )
        
        db.session.add(voice_message)
        db.session.commit()
        
        # Émettre l'événement SocketIO
        socketio.emit('new_voice_message', {
            'message_id': voice_message.id,
            'sender_id': current_user.id,
            'receiver_id': receiver_id,
            'file_url': file_url,
            'duration': duration,
            'file_size': file_size,
            'timestamp': voice_message.timestamp.strftime('%H:%M'),
            'sender_name': current_user.username
        }, room=f'user_{receiver_id}')
        
        return jsonify({
            'success': True,
            'message_id': voice_message.id,
            'file_url': file_url,
            'duration': duration,
            'file_size': file_size
        })
    
    return jsonify({'error': 'Aucun audio valide'}), 400

@app.route('/send_location', methods=['POST'])
@login_required
def send_location():
    """Envoyer une localisation"""
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    
    if not receiver_id or latitude is None or longitude is None:
        return jsonify({'error': 'Données manquantes'}), 400
    
    # Récupérer les informations de traduction
    sender_lang = current_user.language
    receiver = User.query.get(receiver_id)
    receiver_lang = receiver.language if receiver else sender_lang
    
    # Créer le message de localisation
    location_message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content="📍 Ma localisation",
        translated_content="📍 My location",
        original_language=sender_lang,
        translated_language=receiver_lang,
        message_type='location',
        latitude=latitude,
        longitude=longitude
    )
    
    db.session.add(location_message)
    db.session.commit()
    
    # Émettre l'événement SocketIO
    socketio.emit('new_location_message', {
        'message_id': location_message.id,
        'sender_id': current_user.id,
        'receiver_id': receiver_id,
        'latitude': latitude,
        'longitude': longitude,
        'timestamp': location_message.timestamp.strftime('%H:%M'),
        'sender_name': current_user.username
    }, room=f'user_{receiver_id}')
    
    return jsonify({'success': True, 'message_id': location_message.id})

@app.route('/share_contact', methods=['POST'])
@login_required
def share_contact():
    """Partager un contact"""
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    contact_info = data.get('contact_info')
    
    if not receiver_id or not contact_info:
        return jsonify({'error': 'Données manquantes'}), 400
    
    try:
        contact_data = json.loads(contact_info)
    except:
        return jsonify({'error': 'Format de contact invalide'}), 400
    
    # Récupérer les informations de traduction
    sender_lang = current_user.language
    receiver = User.query.get(receiver_id)
    receiver_lang = receiver.language if receiver else sender_lang
    
    # Créer le message de contact
    contact_message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=f"👤 Contact: {contact_data.get('name', 'Sans nom')}",
        translated_content=f"👤 Contact: {contact_data.get('name', 'Unnamed')}",
        original_language=sender_lang,
        translated_language=receiver_lang,
        message_type='contact',
        contact_info=contact_info
    )
    
    db.session.add(contact_message)
    db.session.commit()
    
    # Émettre l'événement SocketIO
    socketio.emit('new_contact_message', {
        'message_id': contact_message.id,
        'sender_id': current_user.id,
        'receiver_id': receiver_id,
        'contact_info': contact_data,
        'timestamp': contact_message.timestamp.strftime('%H:%M'),
        'sender_name': current_user.username
    }, room=f'user_{receiver_id}')
    
    return jsonify({'success': True, 'message_id': contact_message.id})

@app.route('/get_file_info/<path:file_url>')
@login_required
def get_file_info(file_url):
    """Récupérer les informations d'un fichier"""
    file_path = file_url.lstrip('/')
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'Fichier non trouvé'}), 404
    
    file_size = os.path.getsize(file_path)
    filename = os.path.basename(file_path).split('_', 2)[-1] if '_' in os.path.basename(file_path) else os.path.basename(file_path)
    
    return jsonify({
        'filename': filename,
        'file_size': file_size,
        'file_type': get_file_type(filename),
        'icon': get_file_icon(filename)
    })

@app.route('/download_file/<path:file_url>')
@login_required
def download_file(file_url):
    """Télécharger un fichier"""
    file_path = file_url.lstrip('/')
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'Fichier non trouvé'}), 404
    
    filename = os.path.basename(file_path).split('_', 2)[-1] if '_' in os.path.basename(file_path) else os.path.basename(file_path)
    
    return send_file(file_path, as_attachment=True, download_name=filename)

@app.route('/get_file_stats')
@login_required
def get_file_stats():
    """Obtenir les statistiques des fichiers échangés"""
    # Fichiers envoyés
    sent_files = Message.query.filter(
        Message.sender_id == current_user.id,
        Message.message_type.in_(['file', 'multiple_files', 'voice'])
    ).count()
    
    # Fichiers reçus
    received_files = Message.query.filter(
        Message.receiver_id == current_user.id,
        Message.message_type.in_(['file', 'multiple_files', 'voice'])
    ).count()
    
    # Taille totale des fichiers
    total_size = db.session.query(db.func.sum(Message.file_size)).filter(
        Message.sender_id == current_user.id,
        Message.file_size.isnot(None)
    ).scalar() or 0
    
    # Types de fichiers
    file_types = db.session.query(
        Message.message_type,
        db.func.count(Message.id)
    ).filter(
        Message.sender_id == current_user.id,
        Message.message_type.in_(['file', 'multiple_files', 'voice'])
    ).group_by(Message.message_type).all()
    
    return jsonify({
        'sent_files': sent_files,
        'received_files': received_files,
        'total_size': total_size,
        'formatted_size': format_file_size(total_size),
        'file_types': dict(file_types)
    })

# API pour la traduction
@app.route('/api/translate', methods=['POST'])
@login_required
def translate_text():
    data = request.get_json()
    text = data.get('text')
    from_lang = data.get('from_lang', current_user.language)
    to_lang = data.get('to_lang')
    
    if not text or not to_lang:
        return jsonify({'error': 'Texte ou langue de destination manquant'}), 400
    
    translated = translation_service.translate_message(text, from_lang, to_lang)
    
    return jsonify({
        'original': text,
        'translated': translated,
        'from_lang': from_lang,
        'to_lang': to_lang
    })

@app.route('/api/languages')
def get_languages():
    return jsonify(app.config['SUPPORTED_LANGUAGES'])

# Gestionnaires SocketIO
@socketio.on('connect')
@login_required
def handle_connect():
    if current_user.is_authenticated:
        join_room(f'user_{current_user.id}')
        current_user.is_online = True
        db.session.commit()
        
        # Notifier les contacts
        contacts = Contact.query.filter_by(user_id=current_user.id).all()
        for contact in contacts:
            emit('user_status', {
                'user_id': current_user.id,
                'is_online': True,
                'status': current_user.status
            }, room=f'user_{contact.contact_id}')

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        current_user.is_online = False
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        
        # Notifier les contacts
        contacts = Contact.query.filter_by(user_id=current_user.id).all()
        for contact in contacts:
            emit('user_status', {
                'user_id': current_user.id,
                'is_online': False,
                'last_seen': current_user.last_seen.strftime('%H:%M')
            }, room=f'user_{contact.contact_id}')

@socketio.on('typing')
def handle_typing(data):
    receiver_id = data.get('receiver_id')
    is_typing = data.get('is_typing')
    
    emit('typing_status', {
        'user_id': current_user.id,
        'is_typing': is_typing
    }, room=f'user_{receiver_id}')

@socketio.on('read_message')
def handle_read_message(data):
    message_id = data.get('message_id')
    message = Message.query.get(message_id)
    
    if message and message.receiver_id == current_user.id:
        message.is_read = True
        db.session.commit()
        
        emit('message_read', {
            'message_id': message_id
        }, room=f'user_{message.sender_id}')

@socketio.on('file_upload_progress')
def handle_file_upload_progress(data):
    """Gérer la progression du téléchargement de fichiers"""
    receiver_id = data.get('receiver_id')
    progress = data.get('progress')
    filename = data.get('filename')
    
    emit('upload_progress', {
        'sender_id': current_user.id,
        'filename': filename,
        'progress': progress
    }, room=f'user_{receiver_id}')

@socketio.on('new_location_message')
def handle_new_location(data):
    """Gérer les nouveaux messages de localisation"""
    emit('new_location', data, room=f'user_{data["receiver_id"]}')

@socketio.on('new_contact_message')
def handle_new_contact(data):
    """Gérer les nouveaux messages de contact"""
    emit('new_contact', data, room=f'user_{data["receiver_id"]}')


# API pour les informations de contact
@app.route('/api/contact_info/<int:contact_id>')
@login_required
def get_contact_info(contact_id):
    """Récupère les informations détaillées d'un contact"""
    contact_user = User.query.get(contact_id)
    
    if not contact_user:
        return jsonify({'error': 'Contact non trouvé'}), 404
    
    return jsonify({
        'id': contact_user.id,
        'username': contact_user.username,
        'email': contact_user.email,
        'language': contact_user.language,
        'language_name': app.config['SUPPORTED_LANGUAGES'].get(contact_user.language, contact_user.language),
        'status': contact_user.status,
        'is_online': contact_user.is_online,
        'last_seen': contact_user.last_seen.strftime('%H:%M') if contact_user.last_seen else '',
        'profile_picture': contact_user.profile_picture,
        'created_at': contact_user.created_at.strftime('%d/%m/%Y') if contact_user.created_at else ''
    })

# API pour les statistiques de chat
@app.route('/api/chat_stats')
@login_required
def get_chat_stats():
    """Récupère les statistiques du chat"""
    # Nombre total de messages
    total_messages = Message.query.filter(
        (Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id)
    ).count()
    
    # Nombre de contacts
    total_contacts = Contact.query.filter_by(user_id=current_user.id).count()
    
    # Nombre de groupes
    total_groups = GroupMember.query.filter_by(user_id=current_user.id).count()
    
    # Dernier message
    last_message = Message.query.filter(
        (Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id)
    ).order_by(Message.timestamp.desc()).first()
    
    last_message_time = last_message.timestamp.strftime('%d/%m/%Y %H:%M') if last_message else 'Jamais'
    
    return jsonify({
        'total_messages': total_messages,
        'total_contacts': total_contacts,
        'total_groups': total_groups,
        'last_message_time': last_message_time,
        'user_language': current_user.language,
        'user_language_name': app.config['SUPPORTED_LANGUAGES'].get(current_user.language, current_user.language)
    })

# API pour rechercher des utilisateurs
@app.route('/api/search_users')
@login_required
def search_users():
    """Recherche des utilisateurs"""
    query = request.args.get('q', '')
    
    if not query or len(query) < 2:
        return jsonify({'users': []})
    
    # Rechercher par username ou email
    users = User.query.filter(
        User.id != current_user.id,
        (User.username.ilike(f'%{query}%') | User.email.ilike(f'%{query}%'))
    ).limit(20).all()
    
    users_list = []
    for user in users:
        # Vérifier si déjà contact
        is_contact = Contact.query.filter_by(
            user_id=current_user.id, 
            contact_id=user.id
        ).first() is not None
        
        users_list.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'language': user.language,
            'language_name': app.config['SUPPORTED_LANGUAGES'].get(user.language, user.language),
            'is_online': user.is_online,
            'is_contact': is_contact,
            'profile_picture': user.profile_picture
        })
    
    return jsonify({'users': users_list})

# API pour créer un groupe
@app.route('/api/create_group', methods=['POST'])
@login_required
def create_group_api():
    """Crée un nouveau groupe"""
    data = request.get_json()
    
    name = data.get('name')
    description = data.get('description', '')
    member_ids = data.get('member_ids', [])
    
    if not name:
        return jsonify({'error': 'Le nom du groupe est requis'}), 400
    
    if not isinstance(member_ids, list):
        return jsonify({'error': 'Format des membres invalide'}), 400
    
    # Créer le groupe
    group = Group(
        name=name,
        description=description,
        created_by=current_user.id
    )
    
    db.session.add(group)
    db.session.flush()  # Pour obtenir l'ID du groupe
    
    # Ajouter le créateur comme admin
    creator_member = GroupMember(
        group_id=group.id,
        user_id=current_user.id,
        is_admin=True
    )
    db.session.add(creator_member)
    
    # Ajouter les autres membres
    for member_id in member_ids:
        if member_id != current_user.id:
            member = GroupMember(
                group_id=group.id,
                user_id=member_id,
                is_admin=False
            )
            db.session.add(member)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'group_id': group.id,
        'name': group.name
    })

# API pour les messages non lus
@app.route('/api/unread_messages')
@login_required
def get_unread_messages():
    """Récupère le nombre de messages non lus par contact"""
    contacts = Contact.query.filter_by(user_id=current_user.id).all()
    
    unread_counts = {}
    for contact in contacts:
        unread_count = Message.query.filter(
            Message.sender_id == contact.contact_id,
            Message.receiver_id == current_user.id,
            Message.is_read == False
        ).count()
        
        if unread_count > 0:
            unread_counts[str(contact.contact_id)] = unread_count
    
    return jsonify(unread_counts)

# API pour marquer les messages comme lus
@app.route('/api/mark_as_read/<int:contact_id>', methods=['POST'])
@login_required
def mark_as_read(contact_id):
    """Marque tous les messages d'un contact comme lus"""
    messages = Message.query.filter(
        Message.sender_id == contact_id,
        Message.receiver_id == current_user.id,
        Message.is_read == False
    ).all()
    
    for message in messages:
        message.is_read = True
    
    db.session.commit()
    
    # Émettre l'événement
    socketio.emit('messages_read', {
        'contact_id': contact_id,
        'user_id': current_user.id
    }, room=f'user_{contact_id}')
    
    return jsonify({'success': True, 'count': len(messages)})


# Pages supplémentaires
@app.route('/features')
def features():
    return render_template('features.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/help')
def help_page():
    return render_template('help.html')  # À créer

@app.route('/contact')
def contact():
    return render_template('contact.html')  # À créer

@app.route('/download')
def download():
    return render_template('download.html')  # À créer

# API pour Omni7.0
@app.route('/api/omni', methods=['POST'])
@login_required
def omni_assistant():
    """Endpoint pour l'assistant IA Omni7.0"""
    data = request.get_json()
    message = data.get('message', '')
    user_id = current_user.id
    
    # Récupérer ou créer les données utilisateur pour Omni
    user_data = get_or_create_omni_data(user_id)
    
    # Traiter le message avec Omni7.0
    response = process_omni_message(message, user_data)
    
    # Mettre à jour les données utilisateur
    update_omni_data(user_id, user_data)
    
    return jsonify({
        'response': response,
        'user_name': user_data.get('first_name'),
        'knows_name': user_data.get('knows_name', False)
    })

def get_or_create_omni_data(user_id):
    """Récupère ou crée les données Omni pour un utilisateur"""
    # Dans une application réelle, on stockerait en base de données
    # Pour l'instant, simulation avec session
    if 'omni_data' not in session:
        session['omni_data'] = {
            'first_name': None,
            'last_name': None,
            'knows_name': False,
            'interaction_count': 0,
            'preferences': {}
        }
    
    return session['omni_data']

def update_omni_data(user_id, data):
    """Met à jour les données Omni"""
    session['omni_data'] = data
    session.modified = True

def process_omni_message(message, user_data):
    """Traite un message pour Omni7.0"""
    message_lower = message.lower()
    user_data['interaction_count'] = user_data.get('interaction_count', 0) + 1
    
    # Première interaction - demander le nom
    if not user_data['knows_name']:
        # Chercher le nom dans le message
        name_match = re.search(r'(je m\'appelle|mon nom est|je suis) (.+)', message, re.IGNORECASE)
        if name_match:
            full_name = name_match.group(2).strip()
            name_parts = full_name.split(' ')
            
            user_data['first_name'] = name_parts[0]
            user_data['last_name'] = ' '.join(name_parts[1:]) if len(name_parts) > 1 else None
            user_data['knows_name'] = True
            
            return f"Enchanté {user_data['first_name']} ! Je suis Omni7.0, votre assistant IA. Comment puis-je vous aider aujourd'hui ?"
        else:
            return "Je serais ravi de vous connaître ! Pourriez-vous me dire votre nom ? Par exemple, vous pouvez dire 'Je m'appelle [votre nom]'."
    
    # Interactions suivantes
    user_name = user_data['first_name']
    
    # Réponses basées sur le contenu du message
    if any(word in message_lower for word in ['bonjour', 'salut', 'hello', 'hi']):
        return f"Bonjour {user_name} ! Comment allez-vous aujourd'hui ?"
    
    elif any(word in message_lower for word in ['qui es-tu', 'qui êtes-vous', 'présente-toi']):
        return f"Je suis Omni7.0, votre assistant IA personnel sur MISPA. Je suis ici pour vous aider avec l'application et répondre à vos questions, {user_name}."
    
    elif any(word in message_lower for word in ['aide', 'help', 'comment', 'comment utiliser']):
        return f"""Bien sûr {user_name} ! Voici comment utiliser MISPA :

1. **Traduction** : Tous vos messages sont automatiquement traduits pour votre contact
2. **Fichiers** : Cliquez sur l'icône 📎 pour envoyer des photos, vidéos ou documents
3. **Messages vocaux** : Maintenez l'icône 🎤 pour enregistrer
4. **Paramètres** : Accédez aux paramètres pour activer la 2FA et choisir votre langue

Avez-vous une question spécifique ?"""

    elif any(word in message_lower for word in ['merci', 'thank you', 'thanks']):
        return f"Je vous en prie {user_name} ! N'hésitez pas si vous avez d'autres questions."
    
    elif any(word in message_lower for word in ['au revoir', 'bye', 'à plus']):
        return f"Au revoir {user_name} ! À bientôt sur MISPA !"
    
    else:
        # Réponses génériques personnalisées
        responses = [
            f"C'est une excellente question {user_name}. Laissez-moi réfléchir...",
            f"Je comprends votre demande {user_name}. Voici ce que je peux vous dire :",
            f"Très intéressant {user_name} ! En ce qui concerne MISPA, je vous recommande de...",
            f"{user_name}, pour cette question, je pense que la meilleure approche est..."
        ]
        return random.choice(responses) + "\n\nN'hésitez pas à me demander des conseils spécifiques sur l'utilisation de MISPA !"

# Fonction pour créer les tables
def create_tables():
    with app.app_context():
        db.create_all()
        
        # Créer un utilisateur admin par défaut si inexistant
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@mispa.com',
                password_hash=security_manager.hash_password('admin123'),
                language='fr'
            )
            db.session.add(admin)
            db.session.commit()

if __name__ == '__main__':
    # Créer le répertoire de la base de données
    os.makedirs('database', exist_ok=True)
    
    # Créer les tables
    create_tables()
    
    # Démarrer l'application
    print("MBAJO 7.0 - MISPA Messenger")
    print("Application démarrée sur http://localhost:5000")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)

# Routes principales
@app.route('/')
def index():
    return render_template('index.html')  # Votre fichier index.html modifié

    # Routes supplémentaires pour les pages manquantes
@app.route('/features')
def features():
    return render_template('features.html')

@app.route('/help')
def help_page():
    return render_template('help.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/download')
def download():
    return render_template('download.html')

# Route pour la page about
@app.route('/about')
def about():
    return render_template('about.html')

# Route pour gérer les redirections depuis les pages HTML statiques
@app.route('/index.html')
def index_html():
    return redirect(url_for('index'))

@app.route('/register.html')
def register_html():
    return redirect(url_for('register'))

@app.route('/login.html')
def login_html():
    return redirect(url_for('login'))

@app.route('/about.html')
def about_html():
    return redirect(url_for('about'))

@app.route("/settings")
def settings():
    return render_template("settings.html")


# Route pour créer un exemple d'utilisateur pour les tests
@app.route('/create_test_user')
def create_test_user():
    """Crée un utilisateur de test pour le développement"""
    if User.query.filter_by(username='test').first():
        return jsonify({'message': 'Utilisateur test déjà existant'})
    
    test_user = User(
        username='test',
        email='test@mispa.com',
        password_hash=security_manager.hash_password('test123'),
        language='fr'
    )
    
    db.session.add(test_user)
    db.session.commit()
    
    return jsonify({'message': 'Utilisateur test créé', 'username': 'test', 'password': 'test123'})

# Route pour vérifier l'état de l'application
@app.route('/health')
def health_check():
    """Vérifie que l'application fonctionne correctement"""
    return jsonify({
        'status': 'OK',
        'timestamp': datetime.utcnow().isoformat(),
        'users_count': User.query.count(),
        'messages_count': Message.query.count()
    })

# =============== ROUTES POUR LES NOUVELLES FONCTIONNALITÉS ===============


from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/api/add_contact/<int:contact_id>", methods=["POST"])
def add_contact(contact_id):
    # Exemple de traitement
    data = request.get_json(silent=True)  # si tu envoies du JSON
    return jsonify({
        "message": f"Contact {contact_id} ajouté avec succès",
        "data": data
    })


@app.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    """Upload de photo de profil"""
    try:
        if 'avatar' not in request.files:
            return jsonify({'success': False, 'message': 'Aucun fichier'})
        
        file = request.files['avatar']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'})
        
        # Sécuriser le nom du fichier
        filename = secure_filename(f"user_{current_user.id}_{int(time.time())}.jpg")
        
        # Créer le dossier si nécessaire
        upload_folder = os.path.join('static', 'avatars')
        os.makedirs(upload_folder, exist_ok=True)
        
        # Sauvegarder le fichier
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        # Optimiser l'image
        from PIL import Image
        img = Image.open(file_path)
        img.thumbnail((300, 300))  # Redimensionner
        img.save(file_path, 'JPEG', quality=85)
        
        # Mettre à jour la base de données
        avatar_url = url_for('static', filename=f'avatars/{filename}')
        current_user.avatar_url = avatar_url
        db.session.commit()
        
        return jsonify({'success': True, 'avatar_url': avatar_url})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/send_invitation', methods=['POST'])
@login_required
def send_invitation():
    """Envoyer une invitation à un utilisateur"""
    data = request.get_json()
    username = data.get('username')
    
    # Vérifier si l'utilisateur existe
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'success': False, 'message': 'Utilisateur non trouvé'})
    
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'Vous ne pouvez pas vous ajouter vous-même'})
    
    # Vérifier si l'invitation existe déjà
    existing = ContactInvitation.query.filter_by(
        sender_id=current_user.id,
        receiver_id=user.id,
        status='pending'
    ).first()
    
    if existing:
        return jsonify({'success': False, 'message': 'Invitation déjà envoyée'})
    
    # Créer l'invitation
    invitation = ContactInvitation(
        sender_id=current_user.id,
        receiver_id=user.id,
        status='pending'
    )
    db.session.add(invitation)
    db.session.commit()
    
    # Notifier en temps réel
    emit_invitation_notification(user.id, {
        'id': invitation.id,
        'from_username': current_user.username,
        'from_avatar': current_user.avatar_url
    })
    
    return jsonify({'success': True})

@app.route('/get_invitations', methods=['GET'])
@login_required
def get_invitations():
    """Récupérer les invitations reçues"""
    invitations = ContactInvitation.query.filter_by(
        receiver_id=current_user.id,
        status='pending'
    ).all()
    
    data = []
    for inv in invitations:
        user = User.query.get(inv.sender_id)
        data.append({
            'id': inv.id,
            'username': user.username,
            'avatar_url': user.avatar_url
        })
    
    return jsonify({'invitations': data})

@app.route('/accept_invitation', methods=['POST'])
@login_required
def accept_invitation():
    """Accepter une invitation"""
    data = request.get_json()
    invitation_id = data.get('invitation_id')
    
    invitation = ContactInvitation.query.get_or_404(invitation_id)
    
    if invitation.receiver_id != current_user.id:
        return jsonify({'success': False, 'message': 'Non autorisé'})
    
    invitation.status = 'accepted'
    
    # Créer la relation de contact
    contact1 = Contact(user_id=invitation.sender_id, contact_id=invitation.receiver_id)
    contact2 = Contact(user_id=invitation.receiver_id, contact_id=invitation.sender_id)
    
    db.session.add(contact1)
    db.session.add(contact2)
    db.session.commit()
    
    # Notifier l'expéditeur
    emit_invitation_accepted(invitation.sender_id, {
        'username': current_user.username,
        'avatar_url': current_user.avatar_url
    })
    
    return jsonify({'success': True})

@app.route('/reject_invitation', methods=['POST'])
@login_required
def reject_invitation():
    """Refuser une invitation"""
    data = request.get_json()
    invitation_id = data.get('invitation_id')
    
    invitation = ContactInvitation.query.get_or_404(invitation_id)
    
    if invitation.receiver_id != current_user.id:
        return jsonify({'success': False, 'message': 'Non autorisé'})
    
    invitation.status = 'rejected'
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/send_message_direct', methods=['POST'])
@login_required
def send_message_direct():
    """Envoyer un message direct (même sans être contact)"""
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    content = data.get('content')
    message_type = data.get('message_type', 'text')
    
    # Vérifier si l'utilisateur existe
    receiver = User.query.get(receiver_id)
    if not receiver:
        return jsonify({'success': False, 'message': 'Utilisateur non trouvé'})
    
    # Créer le message
    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content,
        message_type=message_type,
        is_read=False
    )
    db.session.add(message)
    db.session.commit()
    
    # Traduire le message
    translated_content = translate_text(content, receiver.language)
    
    # Notifier en temps réel
    emit_new_message(receiver_id, {
        'id': message.id,
        'sender_id': current_user.id,
        'sender_name': current_user.username,
        'sender_avatar': current_user.avatar_url,
        'content': content,
        'translated_content': translated_content,
        'timestamp': message.timestamp.strftime('%H:%M'),
        'message_type': message_type
    })
    
    return jsonify({'success': True, 'message_id': message.id})

@app.route('/send_voice_message', methods=['POST'])
@login_required
def send_voice_message():
    """Envoyer un message vocal"""
    try:
        if 'audio' not in request.files:
            return jsonify({'success': False, 'message': 'Aucun fichier audio'})
        
        audio = request.files['audio']
        receiver_id = request.form.get('receiver_id')
        
        # Sauvegarder le fichier audio
        filename = secure_filename(f"voice_{current_user.id}_{int(time.time())}.webm")
        upload_folder = os.path.join('static', 'voice_messages')
        os.makedirs(upload_folder, exist_ok=True)
        
        file_path = os.path.join(upload_folder, filename)
        audio.save(file_path)
        
        # Créer le message
        voice_url = url_for('static', filename=f'voice_messages/{filename}')
        message = Message(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            content=voice_url,
            message_type='voice',
            is_read=False
        )
        db.session.add(message)
        db.session.commit()
        
        # Notifier
        emit_new_message(receiver_id, {
            'id': message.id,
            'sender_id': current_user.id,
            'sender_name': current_user.username,
            'sender_avatar': current_user.avatar_url,
            'content': voice_url,
            'timestamp': message.timestamp.strftime('%H:%M'),
            'message_type': 'voice',
            'duration': request.form.get('duration', '0:03')
        })
        
        return jsonify({'success': True, 'voice_url': voice_url})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

def emit_invitation_notification(user_id, data):
    """Émettre une notification d'invitation"""
    from flask_socketio import emit
    socketio.emit('new_invitation', data, room=f'user_{user_id}')

def emit_invitation_accepted(user_id, data):
    """Émettre une notification d'invitation acceptée"""
    from flask_socketio import emit
    socketio.emit('invitation_accepted', data, room=f'user_{user_id}')

def emit_new_message(user_id, data):
    """Émettre un nouveau message"""
    from flask_socketio import emit
    socketio.emit('direct_message', data, room=f'user_{user_id}')

# Ajouter les modèles manquants
class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    contact_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ContactInvitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    content = db.Column(db.Text)
    message_type = db.Column(db.String(20), default='text')  # text, image, voice, file
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Ajouter le champ avatar_url au modèle User
class User(UserMixin, db.Model):
    # ... vos champs existants ...
    avatar_url = db.Column(db.String(500), default='/static/avatars/default.png')
    language = db.Column(db.String(10), default='fr')