import json
import os
from translatepy import Translator
from translatepy.exceptions import TranslatepyException

class TranslationService:
    def __init__(self):
        self.translator = Translator()
        self.custom_translations = {}
        self.custom_translations_file = 'custom_translations.json'
        self.load_custom_translations()
    
    def load_custom_translations(self):
        """Charge les traductions personnalisées"""
        try:
            if os.path.exists(self.custom_translations_file):
                with open(self.custom_translations_file, 'r', encoding='utf-8') as f:
                    self.custom_translations = json.load(f)
            else:
                self.custom_translations = {}
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Erreur lors du chargement des traductions personnalisées: {e}")
            self.custom_translations = {}
    
    def save_custom_translations(self):
        """Sauvegarde les traductions personnalisées"""
        try:
            with open(self.custom_translations_file, 'w', encoding='utf-8') as f:
                json.dump(self.custom_translations, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des traductions: {e}")
    
    def translate_message(self, text, from_lang, to_lang):
        """
        Traduit un message d'une langue à une autre
        """
        if not text or not isinstance(text, str):
            return text
            
        # Si les langues sont identiques, retourner le texte original
        if from_lang == to_lang:
            return text
        
        try:
            # Vérifier d'abord les traductions personnalisées
            if (from_lang in self.custom_translations and 
                to_lang in self.custom_translations[from_lang] and
                text in self.custom_translations[from_lang][to_lang]):
                return self.custom_translations[from_lang][to_lang][text]
            
            # Utiliser le service de traduction
            result = self.translator.translate(text, destination_language=to_lang)
            translation = str(result)
            
            # Stocker la traduction pour une utilisation future
            if from_lang not in self.custom_translations:
                self.custom_translations[from_lang] = {}
            if to_lang not in self.custom_translations[from_lang]:
                self.custom_translations[from_lang][to_lang] = {}
            
            self.custom_translations[from_lang][to_lang][text] = translation
            self.save_custom_translations()
            
            return translation
            
        except TranslatepyException as e:
            print(f"Erreur de traduction translatepy: {e}")
            return text
        except Exception as e:
            print(f"Erreur générale de traduction: {e}")
            return text
    
    def detect_language(self, text):
        """Détecte la langue d'un texte"""
        if not text or not isinstance(text, str):
            return 'en'
            
        try:
            result = self.translator.language(text)
            return str(result.result.language) if hasattr(result, 'result') else 'en'
        except TranslatepyException as e:
            print(f"Erreur de détection de langue: {e}")
            return 'en'
        except Exception as e:
            print(f"Erreur générale de détection: {e}")
            return 'en'
    
    def add_custom_translation(self, from_lang, to_lang, original, translation):
        """Ajoute une traduction personnalisée"""
        if not original or not translation:
            return False
            
        try:
            if from_lang not in self.custom_translations:
                self.custom_translations[from_lang] = {}
            if to_lang not in self.custom_translations[from_lang]:
                self.custom_translations[from_lang][to_lang] = {}
            
            self.custom_translations[from_lang][to_lang][original] = translation
            self.save_custom_translations()
            return True
        except Exception as e:
            print(f"Erreur lors de l'ajout de la traduction personnalisée: {e}")
            return False
    
    def add_new_language(self, language_code, language_name):
        """Ajoute une nouvelle langue supportée"""
        try:
            # Cette fonction modifie le fichier config.py
            config_path = 'config.py'
            
            if not os.path.exists(config_path):
                print(f"Fichier de configuration {config_path} non trouvé")
                return False
            
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Vérifier si la langue existe déjà
            if f"'{language_code}': '{language_name}'" in content:
                print(f"La langue {language_name} ({language_code}) existe déjà")
                return False
            
            # Ajouter la nouvelle langue dans le dictionnaire SUPPORTED_LANGUAGES
            lines = content.split('\n')
            new_lines = []
            in_supported_languages = False
            added = False
            
            for i, line in enumerate(lines):
                new_lines.append(line)
                
                # Chercher le dictionnaire SUPPORTED_LANGUAGES
                if 'SUPPORTED_LANGUAGES' in line and '=' in line:
                    in_supported_languages = True
                
                # Dans le dictionnaire, ajouter avant la fermeture
                if in_supported_languages and line.strip() == '}':
                    # Ajouter la nouvelle langue avant la fermeture
                    indent = ' ' * (len(line) - len(line.lstrip()))
                    new_lines[-1] = f"{indent}    '{language_code}': '{language_name}',"
                    new_lines.append(line)
                    added = True
                    in_supported_languages = False
            
            if added:
                with open(config_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(new_lines))
                print(f"Langue {language_name} ({language_code}) ajoutée avec succès")
                return True
            else:
                print("Impossible d'ajouter la langue: dictionnaire SUPPORTED_LANGUAGES non trouvé")
                return False
                
        except Exception as e:
            print(f"Erreur lors de l'ajout de la nouvelle langue: {e}")
            return False
    
    def get_supported_languages(self):
        """Retourne la liste des langues supportées"""
        try:
            # Tenter de charger depuis config.py
            from config import Config
            return Config.SUPPORTED_LANGUAGES
        except ImportError:
            # Langues par défaut si config.py n'est pas disponible
            return {
                'en': 'English',
                'fr': 'Français',
                'es': 'Español',
                'zh': '中文',
                'hi': 'हिन्दी',
                'ar': 'العربية',
                'pt': 'Português',
                'bn': 'বাংলা',
                'ru': 'Русский',
                    'ja': '日本語',
                'de': 'Deutsch',
                'ko': '한국어',
                'it': 'Italiano',
                'tr': 'Türkçe',
                'vi': 'Tiếng Việt',
                'th': 'ไทย',
                'pl': 'Polski',
                'nl': 'Nederlands',
                'sv': 'Svenska',
                'fa': 'فارسی'
            }
    
    def clear_custom_translations(self):
        """Efface toutes les traductions personnalisées"""
        try:
            self.custom_translations = {}
            self.save_custom_translations()
            print("Traductions personnalisées effacées")
            return True
        except Exception as e:
            print(f"Erreur lors de l'effacement des traductions: {e}")
            return False
    
    def get_translation_stats(self):
        """Retourne des statistiques sur les traductions"""
        total_translations = 0
        language_pairs = 0
        
        for from_lang in self.custom_translations:
            for to_lang in self.custom_translations[from_lang]:
                language_pairs += 1
                total_translations += len(self.custom_translations[from_lang][to_lang])
        
        return {
            'total_translations': total_translations,
            'language_pairs': language_pairs,
            'custom_translations': self.custom_translations
        }

# Instance globale avec gestion d'erreur
try:
    translation_service = TranslationService()
    print("Service de traduction initialisé avec succès")
except Exception as e:
    print(f"Erreur lors de l'initialisation du service de traduction: {e}")
    # Créer une instance basique en cas d'erreur
    translation_service = type('TranslationServiceFallback', (), {
        'translate_message': lambda self, text, from_lang, to_lang: text,
        'detect_language': lambda self, text: 'en',
        'add_custom_translation': lambda self, *args: False,
        'get_supported_languages': lambda self: {'en': 'English', 'fr': 'Français'}
    })()