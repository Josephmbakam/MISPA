# test_translation.py
from translate_service import translation_service

# Test de traduction
text = "Bonjour le monde"
translated = translation_service.translate_message(text, 'fr', 'en')
print(f"Traduction: '{text}' -> '{translated}'")

# Test de détection de langue
detected = translation_service.detect_language(text)
print(f"Langue détectée: {detected}")

# Test d'ajout de traduction personnalisée
success = translation_service.add_custom_translation('fr', 'en', 'Merci', 'Thank you')
print(f"Ajout traduction personnalisée: {success}")

# Test statistiques
stats = translation_service.get_translation_stats()
print(f"Statistiques: {stats}")