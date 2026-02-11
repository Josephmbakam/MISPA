# migrate_db.py
from app import app, db
from sqlalchemy import text

print("🚀 Début de la migration...")

with app.app_context():
    # 1. Ajouter la colonne bio
    try:
        db.session.execute(text('ALTER TABLE user ADD COLUMN bio TEXT'))
        print("✅ Colonne 'bio' ajoutée avec succès")
    except Exception as e:
        print("ℹ️ Colonne 'bio' déjà existante ou erreur:", e)
    
    # 2. Ajouter la colonne location
    try:
        db.session.execute(text('ALTER TABLE user ADD COLUMN location VARCHAR(100)'))
        print("✅ Colonne 'location' ajoutée avec succès")
    except Exception as e:
        print("ℹ️ Colonne 'location' déjà existante ou erreur:", e)
    
    # 3. Ajouter la colonne recipient_name (si elle n'existe pas)
    try:
        db.session.execute(text('ALTER TABLE invitation ADD COLUMN recipient_name VARCHAR(80)'))
        print("✅ Colonne 'recipient_name' ajoutée avec succès")
    except Exception as e:
        print("ℹ️ Colonne 'recipient_name' déjà existante ou erreur:", e)
    
    # 4. Ajouter la colonne language (si elle n'existe pas)
    try:
        db.session.execute(text('ALTER TABLE invitation ADD COLUMN language VARCHAR(10) DEFAULT "fr"'))
        print("✅ Colonne 'language' ajoutée avec succès")
    except Exception as e:
        print("ℹ️ Colonne 'language' déjà existante ou erreur:", e)
    
    # 5. Ajouter la colonne message (si elle n'existe pas)
    try:
        db.session.execute(text('ALTER TABLE invitation ADD COLUMN message TEXT'))
        print("✅ Colonne 'message' ajoutée avec succès")
    except Exception as e:
        print("ℹ️ Colonne 'message' déjà existante ou erreur:", e)
    
    # 6. Ajouter la colonne sent_date (si elle n'existe pas)
    try:
        db.session.execute(text('ALTER TABLE invitation ADD COLUMN sent_date VARCHAR(20)'))
        print("✅ Colonne 'sent_date' ajoutée avec succès")
    except Exception as e:
        print("ℹ️ Colonne 'sent_date' déjà existante ou erreur:", e)
    
    db.session.commit()
    
    # 7. Vérification finale
    print("\n🔍 Vérification des colonnes...")
    result = db.session.execute(text("PRAGMA table_info(user)")).fetchall()
    columns = [col[1] for col in result]
    print("📋 Colonnes de la table 'user':", columns)
    
    if 'bio' in columns and 'location' in columns:
        print("🎉 SUCCÈS ! Toutes les colonnes sont présentes.")
    else:
        print("⚠️ Certaines colonnes manquent encore.")

print("✨ Migration terminée !")