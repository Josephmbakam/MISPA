import math
import os
import json
import re
import random
import time
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

# Langues supportées
app.config['SUPPORTED_LANGUAGES'] = {
    'fr': 'Français',
    'en': 'English',
    'es': 'Español',
    'de': 'Deutsch',
    'it': 'Italiano',
    'pt': 'Português',
    'ru': 'Русский',
    'zh': '中文',
    'ja': '日本語',
    'ar': 'العربية',
    'sw': 'Kiswahili',
    'yo': 'Yorùbá',
    'ig': 'Igbo',
    'ha': 'Hausa',
    'ln': 'Lingála',
    'kg': 'Kikongo',
    'rw': 'Kinyarwanda'
}

# Créer les dossiers de téléchargement
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'images'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'videos'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'audio'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'documents'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'others'), exist_ok=True)
os.makedirs(os.path.join('static', 'avatars'), exist_ok=True)
os.makedirs(os.path.join('static', 'voice_messages'), exist_ok=True)
os.makedirs('database', exist_ok=True)

# =============== MODÈLES DE DONNÉES ===============

class User(UserMixin, db.Model):
    __tablename__ = 'user'
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
    avatar_url = db.Column(db.String(500), default='/static/avatars/default.png')
    status = db.Column(db.String(100), default='En ligne')
    bio = db.Column(db.Text)
    location = db.Column(db.String(100))
    
    # Relations
    contacts = db.relationship('Contact', foreign_keys='Contact.user_id', backref='user', lazy=True)
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    messages_received = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy=True)
    sent_invitations = db.relationship('Invitation', foreign_keys='Invitation.sender_id', backref='sender', lazy=True)

class Contact(db.Model):
    __tablename__ = 'contact'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_blocked = db.Column(db.Boolean, default=False)
    nickname = db.Column(db.String(100))

class Invitation(db.Model):
    __tablename__ = 'invitation'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_email = db.Column(db.String(120), nullable=False)
    recipient_name = db.Column(db.String(80))
    language = db.Column(db.String(10), default='fr')
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, declined, cancelled
    sent_date = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ContactInvitation(db.Model):
    __tablename__ = 'contact_invitation'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

class Message(db.Model):
    __tablename__ = 'message'
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
    __tablename__ = 'group'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    group_picture = db.Column(db.String(200), default='group_default.png')

class GroupMember(db.Model):
    __tablename__ = 'group_member'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)

class GroupMessage(db.Model):
    __tablename__ = 'group_message'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    translated_contents = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# =============== FONCTIONS UTILITAIRES ===============

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

def translate_text(text, target_language, source_language='auto'):
    """Fonction utilitaire pour traduire un texte"""
    try:
        return translation_service.translate_message(text, source_language, target_language)
    except:
        return text

def format_last_seen(dt):
    """Formate la date de dernière connexion en texte lisible"""
    if not dt:
        return 'Jamais connecté'
    
    now = datetime.utcnow()
    diff = now - dt
    
    if diff.days > 30:
        return f'Il y a {diff.days // 30} mois'
    elif diff.days > 7:
        return f'Il y a {diff.days // 7} semaines'
    elif diff.days > 1:
        return f'Il y a {diff.days} jours'
    elif diff.days == 1:
        return 'Hier'
    elif diff.seconds > 3600:
        return f'Il y a {diff.seconds // 3600} heures'
    elif diff.seconds > 60:
        return f'Il y a {diff.seconds // 60} minutes'
    else:
        return 'À l\'instant'

# =============== GESTIONNAIRE DE CONNEXION ===============

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# =============== FONCTIONS POUR OMNI7.0 ===============

def get_or_create_omni_data(user_id):
    """Récupère ou crée les données Omni pour un utilisateur"""
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
    
    if not user_data['knows_name']:
        name_match = re.search(r'(je m\'appelle|mon nom est|je suis) (.+)', message, re.IGNORECASE)
        if name_match:
            full_name = name_match.group(2).strip()
            name_parts = full_name.split(' ')
            user_data['first_name'] = name_parts[0]
            user_data['last_name'] = ' '.join(name_parts[1:]) if len(name_parts) > 1 else None
            user_data['knows_name'] = True
            return f"Enchanté {user_data['first_name']} ! Je suis Omni7.0, votre assistant IA. Comment puis-je vous aider aujourd'hui ?"
        else:
            return "Je serais ravi de vous connaître ! Pourriez-vous me dire votre nom ?"
    
    user_name = user_data['first_name']
    
    if any(word in message_lower for word in ['bonjour', 'salut', 'hello', 'hi']):
        return f"Bonjour {user_name} ! Comment allez-vous aujourd'hui ?"
    elif any(word in message_lower for word in ['qui es-tu', 'qui êtes-vous', 'présente-toi']):
        return f"Je suis Omni7.0, votre assistant IA personnel sur MISPA."
    elif any(word in message_lower for word in ['aide', 'help', 'comment']):
        return f"""Bien sûr {user_name} ! Voici comment utiliser MISPA :

1. **Traduction** : Messages automatiquement traduits
2. **Fichiers** : Cliquez sur 📎 pour envoyer des fichiers
3. **Messages vocaux** : Maintenez 🎤 pour enregistrer
4. **Paramètres** : Accédez aux paramètres pour activer la 2FA

Avez-vous une question spécifique ?"""
    elif any(word in message_lower for word in ['merci', 'thank']):
        return f"Je vous en prie {user_name} !"
    elif any(word in message_lower for word in ['au revoir', 'bye']):
        return f"Au revoir {user_name} ! À bientôt sur MISPA !"
    else:
        responses = [
            f"C'est une excellente question {user_name}.",
            f"Je comprends votre demande {user_name}.",
            f"{user_name}, voici ce que je peux vous dire :"
        ]
        return random.choice(responses) + "\n\nN'hésitez pas à me demander plus de détails !"

# =============== FONCTIONS POUR NOTIFICATIONS ===============

def emit_invitation_notification(user_id, data):
    """Émettre une notification d'invitation"""
    socketio.emit('new_invitation', data, room=f'user_{user_id}')

def emit_invitation_accepted(user_id, data):
    """Émettre une notification d'invitation acceptée"""
    socketio.emit('invitation_accepted', data, room=f'user_{user_id}')

def emit_new_message(user_id, data):
    """Émettre un nouveau message"""
    socketio.emit('direct_message', data, room=f'user_{user_id}')

# =============== ROUTES PRINCIPALES ===============

@app.route('/')
def index():
    """Page d'accueil"""
    return render_template('index.html')

@app.route('/index.html')
def index_html():
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        two_factor_code = request.form.get('two_factor_code')
        
        user = User.query.filter_by(username=username).first()
        
        if user and security_manager.check_password(password, user.password_hash):
            if user.two_factor_enabled:
                if not two_factor_code or not security_manager.verify_2fa_code(user.two_factor_secret, two_factor_code):
                    flash('Code d\'authentification à deux facteurs incorrect', 'error')
                    return render_template('login.html')
            
            login_user(user)
            user.is_online = True
            user.last_seen = datetime.utcnow()
            db.session.commit()
            
            next_page = request.args.get('next')
            return redirect(next_page or url_for('chat'))
        else:
            flash('Nom d\'utilisateur ou mot de passe incorrect', 'error')
    
    return render_template('login.html')

@app.route('/login.html')
def login_html():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        language = request.form.get('language', 'fr')
        
        if password != confirm_password:
            flash('Les mots de passe ne correspondent pas', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Ce nom d\'utilisateur est déjà pris', 'error')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Cet email est déjà utilisé', 'error')
            return render_template('register.html')
        
        hashed_password = security_manager.hash_password(password)
        user = User(
            username=username,
            email=email,
            password_hash=hashed_password,
            language=language,
            avatar_url='/static/avatars/default.png',
            bio='',
            location='',
            created_at=datetime.utcnow()
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash('Compte créé avec succès! Vous pouvez maintenant vous connecter.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', languages=app.config['SUPPORTED_LANGUAGES'])

@app.route('/register.html')
def register_html():
    return redirect(url_for('register'))

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
                'avatar_url': contact_user.avatar_url,
                'last_seen': contact_user.last_seen.strftime('%H:%M') if contact_user.last_seen else ''
            })
    
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
        current_user.language = request.form.get('language', current_user.language)
        current_user.theme = request.form.get('theme', current_user.theme)
        current_user.status = request.form.get('status', current_user.status)
        current_user.bio = request.form.get('bio', current_user.bio)
        current_user.location = request.form.get('location', current_user.location)
        
        enable_2fa = request.form.get('enable_2fa') == 'on'
        
        if enable_2fa and not current_user.two_factor_enabled:
            current_user.two_factor_secret = security_manager.generate_2fa_secret()
            current_user.two_factor_enabled = True
        elif not enable_2fa:
            current_user.two_factor_enabled = False
        
        db.session.commit()
        flash('Paramètres mis à jour avec succès', 'success')
        
        if enable_2fa and current_user.two_factor_enabled:
            qr_code = security_manager.generate_2fa_qr_code(
                current_user.two_factor_secret,
                current_user.username
            )
            return render_template('settings.html', qr_code=qr_code, languages=app.config['SUPPORTED_LANGUAGES'])
    
    return render_template('settings.html', languages=app.config['SUPPORTED_LANGUAGES'])

@app.route('/features')
def features():
    return render_template('features.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/about.html')
def about_html():
    return redirect(url_for('about'))

@app.route('/help')
def help_page():
    return render_template('help.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/download')
def download():
    return render_template('download.html')

# =============== ROUTES DE GESTION DES CONTACTS (VERSION AMÉLIORÉE) ===============

@app.route('/contacts')
@login_required
def contacts():
    """Page principale des contacts avec tous les utilisateurs et invitations"""
    
    # 🔴 TOUS les utilisateurs sauf l'utilisateur courant
    all_users = User.query.filter(User.id != current_user.id).order_by(User.username).all()
    
    # ✅ CORRECTION: Récupérer les contacts - SANS .all()
    contact_objects = []
    contact_ids = []
    
    for contact_rel in current_user.contacts:  # InstrumentedList, pas besoin de .all()
        contact_user = User.query.get(contact_rel.contact_id)
        if contact_user:
            contact_objects.append(contact_user)
            contact_ids.append(contact_user.id)
    
    # Récupérer les invitations envoyées (par email)
    invitations = Invitation.query.filter_by(
        sender_id=current_user.id, 
        status='pending'
    ).order_by(Invitation.created_at.desc()).all()
    
    # IDs des utilisateurs avec invitation en attente
    pending_invitation_ids = []
    for invitation in Invitation.query.filter_by(
        sender_id=current_user.id, 
        status='pending'
    ).all():
        user = User.query.filter_by(email=invitation.recipient_email).first()
        if user:
            pending_invitation_ids.append(user.id)
    
    # Récupérer les groupes dont l'utilisateur est membre
    group_memberships = GroupMember.query.filter_by(user_id=current_user.id).all()
    groups = []
    for membership in group_memberships:
        group = Group.query.get(membership.group_id)
        if group:
            group.member_count = GroupMember.query.filter_by(group_id=group.id).count()
            groups.append(group)
    
    # Statistiques
    online_users_count = User.query.filter(
        User.is_online == True, 
        User.id != current_user.id
    ).count()
    
    pending_invitations_count = len(invitations)
    
    # Formater les dates pour tous les utilisateurs
    for user in all_users:
        user.last_seen_formatted = format_last_seen(user.last_seen)
        user.joined_date_formatted = user.created_at.strftime('%d/%m/%Y') if user.created_at else 'Inconnue'
        user.last_seen_timestamp = int(user.last_seen.timestamp()) if user.last_seen else 0
    
    for contact in contact_objects:
        contact.last_seen_formatted = format_last_seen(contact.last_seen)
        contact.last_seen_timestamp = int(contact.last_seen.timestamp()) if contact.last_seen else 0
    
    return render_template(
        'contacts.html',
        contacts=contact_objects,
        all_users=all_users,
        contact_ids=contact_ids,
        pending_invitation_ids=pending_invitation_ids,
        invitations=invitations,
        groups=groups,
        online_users_count=online_users_count,
        pending_invitations_count=pending_invitations_count,
        config={'SUPPORTED_LANGUAGES': app.config['SUPPORTED_LANGUAGES']}
    )

@app.route('/add_contact/<int:user_id>', methods=['POST'])
@login_required
def add_contact(user_id):
    """Envoyer une invitation à un utilisateur existant"""
    
    target_user = User.query.get(user_id)
    
    if not target_user:
        return jsonify({'success': False, 'error': 'Utilisateur non trouvé'}), 404
    
    # Vérifier si déjà contact
    existing_contact = Contact.query.filter_by(
        user_id=current_user.id, 
        contact_id=target_user.id
    ).first()
    
    if existing_contact:
        return jsonify({'success': False, 'error': 'Déjà dans vos contacts'}), 400
    
    # Vérifier si invitation déjà envoyée
    existing_invitation = Invitation.query.filter_by(
        sender_id=current_user.id,
        recipient_email=target_user.email,
        status='pending'
    ).first()
    
    if existing_invitation:
        return jsonify({'success': False, 'error': 'Invitation déjà envoyée'}), 400
    
    # Créer l'invitation
    invitation = Invitation(
        sender_id=current_user.id,
        recipient_email=target_user.email,
        recipient_name=target_user.username,
        language=target_user.language,
        message=f"{current_user.username} souhaite vous ajouter à ses contacts",
        status='pending',
        sent_date=datetime.now().strftime('%d/%m/%Y'),
        created_at=datetime.utcnow()
    )
    
    db.session.add(invitation)
    db.session.commit()
    
    # Notification en temps réel
    socketio.emit('new_invitation', {
        'sender_id': current_user.id,
        'sender_name': current_user.username,
        'sender_avatar': current_user.avatar_url,
        'invitation_id': invitation.id
    }, room=f'user_{target_user.id}')
    
    return jsonify({
        'success': True,
        'invitation': {
            'id': invitation.id,
            'email': invitation.recipient_email,
            'contact_name': invitation.recipient_name,
            'language': invitation.language,
            'message': invitation.message,
            'sent_date': invitation.sent_date
        },
        'language': target_user.language
    })

@app.route('/remove_contact/<int:user_id>', methods=['POST'])
@login_required
def remove_contact(user_id):
    """Retirer un contact"""
    
    # Supprimer la relation dans les deux sens
    contact1 = Contact.query.filter_by(
        user_id=current_user.id, 
        contact_id=user_id
    ).first()
    
    contact2 = Contact.query.filter_by(
        user_id=user_id, 
        contact_id=current_user.id
    ).first()
    
    if contact1:
        db.session.delete(contact1)
    
    if contact2:
        db.session.delete(contact2)
    
    db.session.commit()
    
    # Notification à l'autre utilisateur
    socketio.emit('contact_removed', {
        'user_id': current_user.id,
        'username': current_user.username
    }, room=f'user_{user_id}')
    
    return jsonify({'success': True})

@app.route('/resend_invitation/<int:user_id>', methods=['POST'])
@login_required
def resend_user_invitation(user_id):
    """Relancer une invitation à un utilisateur existant"""
    
    target_user = User.query.get(user_id)
    
    if not target_user:
        return jsonify({'success': False, 'error': 'Utilisateur non trouvé'}), 404
    
    invitation = Invitation.query.filter_by(
        sender_id=current_user.id,
        recipient_email=target_user.email,
        status='pending'
    ).first()
    
    if not invitation:
        return jsonify({'success': False, 'error': 'Invitation non trouvée'}), 404
    
    invitation.sent_date = datetime.now().strftime('%d/%m/%Y')
    db.session.commit()
    
    # Renvoyer notification
    socketio.emit('invitation_resent', {
        'sender_id': current_user.id,
        'sender_name': current_user.username
    }, room=f'user_{target_user.id}')
    
    return jsonify({'success': True})

@app.route('/cancel_invitation/<int:user_id>', methods=['POST'])
@login_required
def cancel_user_invitation(user_id):
    """Annuler une invitation à un utilisateur existant"""
    
    target_user = User.query.get(user_id)
    
    if not target_user:
        return jsonify({'success': False, 'error': 'Utilisateur non trouvé'}), 404
    
    invitation = Invitation.query.filter_by(
        sender_id=current_user.id,
        recipient_email=target_user.email,
        status='pending'
    ).first()
    
    if not invitation:
        return jsonify({'success': False, 'error': 'Invitation non trouvée'}), 404
    
    invitation.status = 'cancelled'
    db.session.commit()
    
    return jsonify({'success': True})

# =============== ROUTES POUR LES INVITATIONS PAR EMAIL ===============

@app.route('/api/send_invitation', methods=['POST'])
@login_required
def send_email_invitation():
    """Envoyer une invitation par email"""
    
    data = request.json
    email = data.get('email')
    language = data.get('language', 'fr')
    message = data.get('message', 'Je souhaite vous ajouter à mes contacts sur MISPA 7.0')
    
    if not email or not email.includes('@'):
        return jsonify({'success': False, 'error': 'Email invalide'}), 400
    
    # Vérifier si l'utilisateur existe déjà
    existing_user = User.query.filter_by(email=email).first()
    
    invitation = Invitation(
        sender_id=current_user.id,
        recipient_email=email,
        recipient_name=existing_user.username if existing_user else None,
        language=language,
        message=message,
        status='pending',
        sent_date=datetime.now().strftime('%d/%m/%Y'),
        created_at=datetime.utcnow()
    )
    
    db.session.add(invitation)
    db.session.commit()
    
    # TODO: Implémenter l'envoi d'email réel
    print(f"📧 Invitation envoyée à {email} de la part de {current_user.username}")
    
    return jsonify({
        'success': True,
        'invitation': {
            'id': invitation.id,
            'email': invitation.recipient_email,
            'contact_name': invitation.recipient_name,
            'language': invitation.language,
            'message': invitation.message,
            'sent_date': invitation.sent_date
        }
    })

@app.route('/resend_invitation/<int:invitation_id>', methods=['POST'])
@login_required
def resend_email_invitation(invitation_id):
    """Relancer une invitation par email"""
    
    invitation = Invitation.query.get(invitation_id)
    
    if not invitation or invitation.sender_id != current_user.id:
        return jsonify({'success': False, 'error': 'Invitation non trouvée'}), 404
    
    invitation.sent_date = datetime.now().strftime('%d/%m/%Y')
    db.session.commit()
    
    print(f"📧 Invitation relancée à {invitation.recipient_email}")
    
    return jsonify({'success': True})

@app.route('/cancel_invitation/<int:invitation_id>', methods=['POST'])
@login_required
def cancel_email_invitation(invitation_id):
    """Annuler une invitation par email"""
    
    invitation = Invitation.query.get(invitation_id)
    
    if not invitation or invitation.sender_id != current_user.id:
        return jsonify({'success': False, 'error': 'Invitation non trouvée'}), 404
    
    invitation.status = 'cancelled'
    db.session.commit()
    
    return jsonify({'success': True})

# =============== ROUTES API POUR LES CONTACTS ===============

@app.route('/api/search_users')
@login_required
def search_users():
    """Rechercher des utilisateurs"""
    
    query = request.args.get('q', '')
    
    if len(query) < 2:
        return jsonify({'users': []})
    
    users = User.query.filter(
        User.id != current_user.id,
        (User.username.ilike(f'%{query}%') | User.email.ilike(f'%{query}%'))
    ).limit(20).all()
    
    # ✅ CORRECTION: Récupérer les IDs des contacts SANS .all()
    contact_ids = []
    for contact_rel in current_user.contacts:
        contact_ids.append(contact_rel.contact_id)
    
    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'language': user.language,
            'language_name': app.config['SUPPORTED_LANGUAGES'].get(user.language, user.language),
            'profile_image': user.avatar_url,
            'is_online': user.is_online,
            'is_contact': user.id in contact_ids,
            'avatar_url': user.avatar_url
        })
    
    return jsonify({'users': users_data})

@app.route('/api/user_profile/<int:user_id>')
@login_required
def user_profile(user_id):
    """Récupérer le profil complet d'un utilisateur"""
    
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'success': False, 'error': 'Utilisateur non trouvé'}), 404
    
    # ✅ CORRECTION: Vérifier si c'est un contact SANS .all()
    is_contact = False
    for contact_rel in current_user.contacts:
        if contact_rel.contact_id == user.id:
            is_contact = True
            break
    
    profile_data = {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'language': user.language,
        'language_name': app.config['SUPPORTED_LANGUAGES'].get(user.language, user.language),
        'profile_image': user.avatar_url,
        'bio': user.bio or '',
        'location': user.location or '',
        'is_online': user.is_online,
        'last_seen': format_last_seen(user.last_seen),
        'last_seen_timestamp': int(user.last_seen.timestamp()) if user.last_seen else 0,
        'joined_date': user.created_at.strftime('%d/%m/%Y') if user.created_at else 'Inconnue',
        'is_contact': is_contact,
        'avatar_url': user.avatar_url
    }
    
    return jsonify({'success': True, 'user': profile_data})

@app.route('/api/send_translated_message', methods=['POST'])
@login_required
def send_translated_message():
    """Envoyer un message avec traduction automatique"""
    
    data = request.json
    recipient_id = data.get('recipient_id')
    message = data.get('message')
    target_language = data.get('target_language')
    
    recipient = User.query.get(recipient_id)
    
    if not recipient:
        return jsonify({'success': False, 'error': 'Destinataire non trouvé'}), 404
    
    # Traduire le message
    translated_message = translate_text(message, target_language)
    
    # Créer le message
    new_message = Message(
        sender_id=current_user.id,
        receiver_id=recipient.id,
        content=message,
        translated_content=translated_message,
        original_language=current_user.language,
        translated_language=target_language,
        timestamp=datetime.utcnow(),
        is_delivered=True
    )
    
    db.session.add(new_message)
    db.session.commit()
    
    # Notification en temps réel
    socketio.emit('new_message', {
        'message_id': new_message.id,
        'sender_id': current_user.id,
        'sender_name': current_user.username,
        'sender_avatar': current_user.avatar_url,
        'receiver_id': recipient.id,
        'content': message,
        'translated_content': translated_message,
        'timestamp': new_message.timestamp.strftime('%H:%M')
    }, room=f'user_{recipient.id}')
    
    return jsonify({
        'success': True,
        'translated_message': translated_message,
        'message_id': new_message.id
    })

@app.route('/api/create_group', methods=['POST'])
@login_required
def create_group():
    """Créer un nouveau groupe"""
    
    data = request.get_json()
    name = data.get('name')
    description = data.get('description', '')
    member_ids = data.get('member_ids', [])
    
    if not name:
        return jsonify({'success': False, 'error': 'Le nom du groupe est requis'}), 400
    
    # Créer le groupe
    group = Group(
        name=name,
        description=description,
        created_by=current_user.id,
        created_at=datetime.utcnow()
    )
    
    db.session.add(group)
    db.session.flush()
    
    # Ajouter le créateur comme admin
    creator_member = GroupMember(
        group_id=group.id,
        user_id=current_user.id,
        is_admin=True,
        joined_at=datetime.utcnow()
    )
    db.session.add(creator_member)
    
    # Ajouter les autres membres
    for member_id in member_ids:
        if member_id != current_user.id:
            member = GroupMember(
                group_id=group.id,
                user_id=member_id,
                is_admin=False,
                joined_at=datetime.utcnow()
            )
            db.session.add(member)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'group_id': group.id,
        'name': group.name
    })

# =============== ROUTES POUR LES MESSAGES ===============

@app.route('/get_messages/<int:contact_id>')
@login_required
def get_messages(contact_id):
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
            'file_size': msg.file_size,
            'duration': msg.duration,
            'latitude': msg.latitude,
            'longitude': msg.longitude
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
    
    sender_lang = current_user.language
    receiver = User.query.get(receiver_id)
    
    if not receiver:
        return jsonify({'error': 'Destinataire non trouvé'}), 404
    
    receiver_lang = receiver.language
    
    translated_content = content
    if sender_lang != receiver_lang:
        translated_content = translation_service.translate_message(
            content, sender_lang, receiver_lang
        )
    
    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content,
        translated_content=translated_content,
        original_language=sender_lang,
        translated_language=receiver_lang,
        message_type=message_type,
        is_delivered=True,
        timestamp=datetime.utcnow()
    )
    
    db.session.add(message)
    db.session.commit()
    
    socketio.emit('new_message', {
        'message_id': message.id,
        'sender_id': current_user.id,
        'receiver_id': receiver_id,
        'content': content,
        'translated_content': translated_content,
        'timestamp': message.timestamp.strftime('%H:%M'),
        'sender_name': current_user.username,
        'sender_avatar': current_user.avatar_url,
        'sender_language': sender_lang,
        'receiver_language': receiver_lang
    }, room=f'user_{receiver_id}')
    
    return jsonify({
        'success': True,
        'message_id': message.id,
        'translated_content': translated_content
    })

@app.route('/send_message_direct', methods=['POST'])
@login_required
def send_message_direct():
    """Envoyer un message direct (même sans être contact)"""
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    content = data.get('content')
    message_type = data.get('message_type', 'text')
    
    receiver = User.query.get(receiver_id)
    if not receiver:
        return jsonify({'success': False, 'message': 'Utilisateur non trouvé'})
    
    message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content,
        message_type=message_type,
        is_read=False,
        timestamp=datetime.utcnow()
    )
    db.session.add(message)
    db.session.commit()
    
    translated_content = translate_text(content, receiver.language)
    
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

# =============== ROUTES POUR LES FICHIERS ===============

@app.route('/upload_file', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    file = request.files['file']
    receiver_id = request.form.get('receiver_id')
    
    if not receiver_id:
        return jsonify({'error': 'Destinataire non spécifié'}), 400
    
    if file and file.filename != '' and allowed_file(file.filename):
        original_filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{current_user.id}_{original_filename}"
        
        file_type = get_file_type(original_filename)
        subfolder = file_type if file_type in ['images', 'videos', 'audio', 'documents'] else 'others'
        
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], subfolder, unique_filename)
        file.save(save_path)
        
        file_url = f"/{save_path}"
        file_size = os.path.getsize(save_path)
        
        sender_lang = current_user.language
        receiver = User.query.get(receiver_id)
        receiver_lang = receiver.language if receiver else sender_lang
        
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
            file_type=file_type,
            timestamp=datetime.utcnow()
        )
        
        db.session.add(file_message)
        db.session.commit()
        
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
    if 'files[]' not in request.files:
        return jsonify({'error': 'Aucun fichier sélectionné'}), 400
    
    files = request.files.getlist('files[]')
    receiver_id = request.form.get('receiver_id')
    
    if not receiver_id:
        return jsonify({'error': 'Destinataire non spécifié'}), 400
    
    uploaded_files = []
    
    for file in files:
        if file and file.filename != '' and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            unique_filename = f"{timestamp}_{current_user.id}_{original_filename}"
            
            file_type = get_file_type(original_filename)
            subfolder = file_type if file_type in ['images', 'videos', 'audio', 'documents'] else 'others'
            
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], subfolder, unique_filename)
            file.save(save_path)
            
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
            file_url=json.dumps(uploaded_files),
            timestamp=datetime.utcnow()
        )
        
        db.session.add(file_message)
        db.session.commit()
        
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
    if 'audio' not in request.files:
        return jsonify({'error': 'Aucun audio enregistré'}), 400
    
    audio_file = request.files['audio']
    receiver_id = request.form.get('receiver_id')
    duration = request.form.get('duration', 0)
    
    if not receiver_id:
        return jsonify({'error': 'Destinataire non spécifié'}), 400
    
    if audio_file and audio_file.filename != '':
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"voice_{timestamp}_{current_user.id}.webm"
        
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], 'audio', filename)
        audio_file.save(save_path)
        
        file_url = f"/{save_path}"
        file_size = os.path.getsize(save_path)
        
        sender_lang = current_user.language
        receiver = User.query.get(receiver_id)
        receiver_lang = receiver.language if receiver else sender_lang
        
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
            duration=int(duration) if duration else 0,
            timestamp=datetime.utcnow()
        )
        
        db.session.add(voice_message)
        db.session.commit()
        
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

@app.route('/download_file/<path:file_url>')
@login_required
def download_file(file_url):
    file_path = file_url.lstrip('/')
    
    if not os.path.exists(file_path):
        return jsonify({'error': 'Fichier non trouvé'}), 404
    
    filename = os.path.basename(file_path).split('_', 2)[-1] if '_' in os.path.basename(file_path) else os.path.basename(file_path)
    
    return send_file(file_path, as_attachment=True, download_name=filename)

@app.route('/get_file_stats')
@login_required
def get_file_stats():
    sent_files = Message.query.filter(
        Message.sender_id == current_user.id,
        Message.message_type.in_(['file', 'multiple_files', 'voice'])
    ).count()
    
    received_files = Message.query.filter(
        Message.receiver_id == current_user.id,
        Message.message_type.in_(['file', 'multiple_files', 'voice'])
    ).count()
    
    total_size = db.session.query(db.func.sum(Message.file_size)).filter(
        Message.sender_id == current_user.id,
        Message.file_size.isnot(None)
    ).scalar() or 0
    
    return jsonify({
        'sent_files': sent_files,
        'received_files': received_files,
        'total_size': total_size,
        'formatted_size': format_file_size(total_size)
    })

# =============== ROUTES POUR LES LOCALISATIONS ET CONTACTS ===============

@app.route('/send_location', methods=['POST'])
@login_required
def send_location():
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    
    if not receiver_id or latitude is None or longitude is None:
        return jsonify({'error': 'Données manquantes'}), 400
    
    sender_lang = current_user.language
    receiver = User.query.get(receiver_id)
    receiver_lang = receiver.language if receiver else sender_lang
    
    location_message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content="📍 Ma localisation",
        translated_content="📍 My location",
        original_language=sender_lang,
        translated_language=receiver_lang,
        message_type='location',
        latitude=latitude,
        longitude=longitude,
        timestamp=datetime.utcnow()
    )
    
    db.session.add(location_message)
    db.session.commit()
    
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
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    contact_info = data.get('contact_info')
    
    if not receiver_id or not contact_info:
        return jsonify({'error': 'Données manquantes'}), 400
    
    try:
        contact_data = json.loads(contact_info)
    except:
        return jsonify({'error': 'Format de contact invalide'}), 400
    
    sender_lang = current_user.language
    receiver = User.query.get(receiver_id)
    receiver_lang = receiver.language if receiver else sender_lang
    
    contact_message = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=f"👤 Contact: {contact_data.get('name', 'Sans nom')}",
        translated_content=f"👤 Contact: {contact_data.get('name', 'Unnamed')}",
        original_language=sender_lang,
        translated_language=receiver_lang,
        message_type='contact',
        contact_info=contact_info,
        timestamp=datetime.utcnow()
    )
    
    db.session.add(contact_message)
    db.session.commit()
    
    socketio.emit('new_contact_message', {
        'message_id': contact_message.id,
        'sender_id': current_user.id,
        'receiver_id': receiver_id,
        'contact_info': contact_data,
        'timestamp': contact_message.timestamp.strftime('%H:%M'),
        'sender_name': current_user.username
    }, room=f'user_{receiver_id}')
    
    return jsonify({'success': True, 'message_id': contact_message.id})

# =============== ROUTES POUR LA GESTION DES INVITATIONS DE CONTACTS ===============

@app.route('/send_invitation', methods=['POST'])
@login_required
def send_invitation():
    data = request.get_json()
    username = data.get('username')
    
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'success': False, 'message': 'Utilisateur non trouvé'})
    
    if user.id == current_user.id:
        return jsonify({'success': False, 'message': 'Vous ne pouvez pas vous ajouter vous-même'})
    
    existing = ContactInvitation.query.filter_by(
        sender_id=current_user.id,
        receiver_id=user.id,
        status='pending'
    ).first()
    
    if existing:
        return jsonify({'success': False, 'message': 'Invitation déjà envoyée'})
    
    invitation = ContactInvitation(
        sender_id=current_user.id,
        receiver_id=user.id,
        status='pending',
        created_at=datetime.utcnow()
    )
    db.session.add(invitation)
    db.session.commit()
    
    emit_invitation_notification(user.id, {
        'id': invitation.id,
        'from_username': current_user.username,
        'from_avatar': current_user.avatar_url
    })
    
    return jsonify({'success': True})

@app.route('/get_invitations', methods=['GET'])
@login_required
def get_invitations():
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
    data = request.get_json()
    invitation_id = data.get('invitation_id')
    
    invitation = ContactInvitation.query.get_or_404(invitation_id)
    
    if invitation.receiver_id != current_user.id:
        return jsonify({'success': False, 'message': 'Non autorisé'})
    
    invitation.status = 'accepted'
    invitation.updated_at = datetime.utcnow()
    
    contact1 = Contact(user_id=invitation.sender_id, contact_id=invitation.receiver_id, created_at=datetime.utcnow())
    contact2 = Contact(user_id=invitation.receiver_id, contact_id=invitation.sender_id, created_at=datetime.utcnow())
    
    db.session.add(contact1)
    db.session.add(contact2)
    db.session.commit()
    
    emit_invitation_accepted(invitation.sender_id, {
        'username': current_user.username,
        'avatar_url': current_user.avatar_url
    })
    
    return jsonify({'success': True})

@app.route('/reject_invitation', methods=['POST'])
@login_required
def reject_invitation():
    data = request.get_json()
    invitation_id = data.get('invitation_id')
    
    invitation = ContactInvitation.query.get_or_404(invitation_id)
    
    if invitation.receiver_id != current_user.id:
        return jsonify({'success': False, 'message': 'Non autorisé'})
    
    invitation.status = 'rejected'
    invitation.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True})

# =============== ROUTES POUR LES AVATARS ===============

@app.route('/upload_avatar', methods=['POST'])
@login_required
def upload_avatar():
    try:
        if 'avatar' not in request.files:
            return jsonify({'success': False, 'message': 'Aucun fichier'})
        
        file = request.files['avatar']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Aucun fichier sélectionné'})
        
        filename = secure_filename(f"user_{current_user.id}_{int(time.time())}.jpg")
        
        upload_folder = os.path.join('static', 'avatars')
        os.makedirs(upload_folder, exist_ok=True)
        
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        try:
            from PIL import Image
            img = Image.open(file_path)
            img.thumbnail((300, 300))
            img.save(file_path, 'JPEG', quality=85)
        except:
            pass
        
        avatar_url = url_for('static', filename=f'avatars/{filename}')
        current_user.avatar_url = avatar_url
        current_user.profile_picture = filename
        db.session.commit()
        
        return jsonify({'success': True, 'avatar_url': avatar_url})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# =============== ROUTES API ===============

@app.route('/api/translate', methods=['POST'])
@login_required
def translate_text_api():
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

@app.route('/api/contact_info/<int:contact_id>')
@login_required
def get_contact_info(contact_id):
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
        'last_seen_formatted': format_last_seen(contact_user.last_seen),
        'profile_picture': contact_user.profile_picture,
        'avatar_url': contact_user.avatar_url,
        'bio': contact_user.bio,
        'location': contact_user.location,
        'created_at': contact_user.created_at.strftime('%d/%m/%Y') if contact_user.created_at else ''
    })

@app.route('/api/chat_stats')
@login_required
def get_chat_stats():
    total_messages = Message.query.filter(
        (Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id)
    ).count()
    
    total_contacts = Contact.query.filter_by(user_id=current_user.id).count()
    total_groups = GroupMember.query.filter_by(user_id=current_user.id).count()
    
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

@app.route('/api/unread_messages')
@login_required
def get_unread_messages():
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

@app.route('/api/mark_as_read/<int:contact_id>', methods=['POST'])
@login_required
def mark_as_read(contact_id):
    messages = Message.query.filter(
        Message.sender_id == contact_id,
        Message.receiver_id == current_user.id,
        Message.is_read == False
    ).all()
    
    for message in messages:
        message.is_read = True
    
    db.session.commit()
    
    socketio.emit('messages_read', {
        'contact_id': contact_id,
        'user_id': current_user.id
    }, room=f'user_{contact_id}')
    
    return jsonify({'success': True, 'count': len(messages)})

@app.route('/api/omni', methods=['POST'])
@login_required
def omni_assistant():
    data = request.get_json()
    message = data.get('message', '')
    user_id = current_user.id
    
    user_data = get_or_create_omni_data(user_id)
    response = process_omni_message(message, user_data)
    update_omni_data(user_id, user_data)
    
    return jsonify({
        'response': response,
        'user_name': user_data.get('first_name'),
        'knows_name': user_data.get('knows_name', False)
    })

# =============== ROUTES DE TEST ===============

@app.route('/create_test_user')
def create_test_user():
    if User.query.filter_by(username='test').first():
        return jsonify({'message': 'Utilisateur test déjà existant'})
    
    test_user = User(
        username='test',
        email='test@mispa.com',
        password_hash=security_manager.hash_password('test123'),
        language='fr',
        avatar_url='/static/avatars/default.png',
        bio='Utilisateur de test',
        location='Testland',
        created_at=datetime.utcnow()
    )
    
    db.session.add(test_user)
    db.session.commit()
    
    return jsonify({'message': 'Utilisateur test créé', 'username': 'test', 'password': 'test123'})

@app.route('/create_sample_users')
def create_sample_users():
    """Créer des utilisateurs d'exemple pour tester Explorer"""
    sample_users = [
        {'username': 'alice', 'email': 'alice@mispa.com', 'language': 'en', 'bio': 'Software developer'},
        {'username': 'bob', 'email': 'bob@mispa.com', 'language': 'es', 'bio': 'Traveler'},
        {'username': 'charlie', 'email': 'charlie@mispa.com', 'language': 'de', 'bio': 'Engineer'},
        {'username': 'diana', 'email': 'diana@mispa.com', 'language': 'it', 'bio': 'Designer'},
        {'username': 'elena', 'email': 'elena@mispa.com', 'language': 'pt', 'bio': 'Teacher'},
        {'username': 'fatou', 'email': 'fatou@mispa.com', 'language': 'fr', 'bio': 'Étudiante'},
        {'username': 'ibrahim', 'email': 'ibrahim@mispa.com', 'language': 'ar', 'bio': 'Ingénieur'},
        {'username': 'wei', 'email': 'wei@mispa.com', 'language': 'zh', 'bio': 'Architect'},
        {'username': 'anna', 'email': 'anna@mispa.com', 'language': 'ru', 'bio': 'Doctor'}
    ]
    
    created = []
    for user_data in sample_users:
        if not User.query.filter_by(username=user_data['username']).first():
            user = User(
                username=user_data['username'],
                email=user_data['email'],
                password_hash=security_manager.hash_password('password123'),
                language=user_data['language'],
                avatar_url='/static/avatars/default.png',
                bio=user_data['bio'],
                location='Sample Location',
                created_at=datetime.utcnow()
            )
            db.session.add(user)
            created.append(user_data['username'])
    
    db.session.commit()
    
    return jsonify({'message': 'Utilisateurs créés', 'users': created})

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'OK',
        'timestamp': datetime.utcnow().isoformat(),
        'users_count': User.query.count(),
        'messages_count': Message.query.count()
    })

# =============== SOCKETIO HANDLERS ===============

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        join_room(f'user_{current_user.id}')
        current_user.is_online = True
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        
        contacts = Contact.query.filter_by(user_id=current_user.id).all()
        for contact in contacts:
            emit('user_status', {
                'user_id': current_user.id,
                'is_online': True,
                'status': current_user.status,
                'last_seen': current_user.last_seen.strftime('%H:%M')
            }, room=f'user_{contact.contact_id}')

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        current_user.is_online = False
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        
        contacts = Contact.query.filter_by(user_id=current_user.id).all()
        for contact in contacts:
            emit('user_status', {
                'user_id': current_user.id,
                'is_online': False,
                'last_seen': current_user.last_seen.strftime('%H:%M'),
                'last_seen_formatted': format_last_seen(current_user.last_seen)
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
    receiver_id = data.get('receiver_id')
    progress = data.get('progress')
    filename = data.get('filename')
    
    emit('upload_progress', {
        'sender_id': current_user.id,
        'filename': filename,
        'progress': progress
    }, room=f'user_{receiver_id}')

# =============== FONCTION DE CRÉATION DES TABLES ===============

def create_tables():
    with app.app_context():
        db.create_all()
        
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@mispa.com',
                password_hash=security_manager.hash_password('admin123'),
                language='fr',
                avatar_url='/static/avatars/default.png',
                bio='Administrateur système',
                location='MISPA HQ',
                created_at=datetime.utcnow()
            )
            db.session.add(admin)
            db.session.commit()

# =============== POINT D'ENTRÉE PRINCIPAL ===============

if __name__ == '__main__':
    create_tables()
    print("=" * 50)
    print("MBAJO 7.0 - MISPA Messenger")
    print("=" * 50)
    print("✅ Application démarrée sur http://localhost:5000")
    print("✅ Mode debug activé")
    print("=" * 50)
    print("\n📱 Routes Contacts ajoutées :")
    print("   - /contacts : Page des contacts avec Explorer")
    print("   - /add_contact/<user_id> : Ajouter un contact")
    print("   - /remove_contact/<user_id> : Retirer un contact")
    print("   - /resend_invitation/<user_id> : Relancer invitation")
    print("   - /cancel_invitation/<user_id> : Annuler invitation")
    print("   - /api/send_invitation : Invitation par email")
    print("   - /api/search_users : Recherche d'utilisateurs")
    print("   - /api/user_profile/<user_id> : Profil utilisateur")
    print("   - /api/send_translated_message : Message traduit")
    print("   - /api/create_group : Création de groupe")
    print("=" * 50)
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)