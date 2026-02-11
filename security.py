import pyotp # type: ignore
import qrcode # type: ignore
from io import BytesIO
import base64
import bcrypt # type: ignore
from datetime import datetime, timedelta
import secrets

class SecurityManager:
    @staticmethod
    def hash_password(password):
        """Hash un mot de passe avec bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def check_password(password, hashed):
        """Vérifie un mot de passe"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    
    @staticmethod
    def generate_2fa_secret():
        """Génère un secret pour l'authentification à deux facteurs"""
        return pyotp.random_base32()
    
    @staticmethod
    def generate_2fa_qr_code(secret, username):
        """Génère un QR code pour l'authentification à deux facteurs"""
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(name=username, issuer_name="MISPA")
        
        # Générer le QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)
        
        # Créer une image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convertir en base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    @staticmethod
    def verify_2fa_code(secret, code):
        """Vérifie un code d'authentification à deux facteurs"""
        totp = pyotp.TOTP(secret)
        return totp.verify(code)
    
    @staticmethod
    def generate_session_token():
        """Génère un token de session sécurisé"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_password_reset_token():
        """Génère un token de réinitialisation de mot de passe"""
        return secrets.token_urlsafe(64)
    
    @staticmethod
    def encrypt_message(message, key):
        """Chiffre un message (simplifié)"""
        # Dans une application réelle, utiliser une bibliothèque de chiffrement
        import hashlib
        from cryptography.fernet import Fernet # type: ignore
        
        # Générer une clé à partir du mot de passe
        key_hash = hashlib.sha256(key.encode()).digest()
        fernet = Fernet(base64.urlsafe_b64encode(key_hash))
        
        encrypted = fernet.encrypt(message.encode())
        return encrypted.decode()
    
    @staticmethod
    def decrypt_message(encrypted_message, key):
        """Déchiffre un message (simplifié)"""
        try:
            import hashlib
            from cryptography.fernet import Fernet # type: ignore
            
            key_hash = hashlib.sha256(key.encode()).digest()
            fernet = Fernet(base64.urlsafe_b64encode(key_hash))
            
            decrypted = fernet.decrypt(encrypted_message.encode())
            return decrypted.decode()
        except:
            return None

security_manager = SecurityManager()