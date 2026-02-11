import subprocess
import sys
import os

def run_command(command):
    """Exécute une commande et affiche le résultat"""
    print(f"Exécution: {command}")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Succès: {result.stdout}")
            return True
        else:
            print(f"✗ Échec: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ Erreur: {e}")
        return False

def main():
    print("=== Installation de MISPA Messenger ===")
    
    # Mettre à jour pip
    print("\n1. Mise à jour de pip...")
    run_command(f"{sys.executable} -m pip install --upgrade pip")
    
    # Liste des packages à installer
    packages = [
        "flask",
        "flask-sqlalchemy",
        "flask-login",
        "flask-wtf",
        "flask-socketio",
        "eventlet",
        "translatepy",
        "pyotp",
        "qrcode",
        "pillow",
        "bcrypt",
        "cryptography",
        "werkzeug",
        "wtforms",
        "email-validator",
        "python-socketio"
    ]
    
    # Installer chaque package
    print("\n2. Installation des packages...")
    for package in packages:
        print(f"\nInstallation de {package}...")
        run_command(f"{sys.executable} -m pip install {package}")
    
    # Vérifier l'installation
    print("\n3. Vérification de l'installation...")
    import_check = """
import flask
import flask_sqlalchemy
import flask_login
import flask_socketio
import eventlet
import translatepy
import pyotp
import qrcode
import bcrypt
print("✓ Tous les packages importés avec succès!")
"""
    
    try:
        exec(import_check)
    except ImportError as e:
        print(f"✗ Erreur d'importation: {e}")
        return False
    
    print("\n=== Installation terminée avec succès! ===")
    print("\nPour lancer l'application:")
    print("cd \"C:\\Users\\Mbajo\\Desktop\\MISPA\"")
    print("python app.py")
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        # Demander si l'utilisateur veut lancer l'appli
        response = input("\nVoulez-vous lancer l'application maintenant? (o/n): ")
        if response.lower() == 'o':
            try:
                print("\nLancement de l'application...")
                import app
            except Exception as e:
                print(f"Erreur lors du lancement: {e}")