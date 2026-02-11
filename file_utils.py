import os
import magic
from PIL import Image
import ffmpeg
from moviepy.editor import VideoFileClip

class FileProcessor:
    @staticmethod
    def get_mime_type(file_path):
        """Obtenir le type MIME d'un fichier"""
        mime = magic.Magic(mime=True)
        return mime.from_file(file_path)
    
    @staticmethod
    def create_thumbnail(image_path, thumb_path, size=(200, 200)):
        """Créer une miniature pour une image"""
        try:
            with Image.open(image_path) as img:
                img.thumbnail(size, Image.Resampling.LANCZOS)
                img.save(thumb_path, 'JPEG', quality=85)
            return True
        except Exception as e:
            print(f"Erreur création thumbnail: {e}")
            return False
    
    @staticmethod
    def extract_video_thumbnail(video_path, thumb_path, time_sec=1):
        """Extraire une miniature d'une vidéo"""
        try:
            # Utiliser ffmpeg pour extraire une image
            (
                ffmpeg
                .input(video_path, ss=time_sec)
                .output(thumb_path, vframes=1)
                .run(capture_stdout=True, capture_stderr=True)
            )
            return True
        except Exception as e:
            print(f"Erreur extraction thumbnail vidéo: {e}")
            return False
    
    @staticmethod
    def get_video_duration(video_path):
        """Obtenir la durée d'une vidéo"""
        try:
            clip = VideoFileClip(video_path)
            duration = clip.duration
            clip.close()
            return duration
        except:
            return 0
    
    @staticmethod
    def compress_image(image_path, quality=85):
        """Compresser une image"""
        try:
            with Image.open(image_path) as img:
                # Convertir en RGB si nécessaire
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = rgb_img
                
                # Sauvegarder compressé
                img.save(image_path, 'JPEG', quality=quality, optimize=True)
            return True
        except Exception as e:
            print(f"Erreur compression image: {e}")
            return False
    
    @staticmethod
    def is_file_safe(file_path):
        """Vérifier si un fichier est sûr"""
        unsafe_extensions = {'.exe', '.bat', '.cmd', '.sh', '.php', '.js', '.vbs'}
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext in unsafe_extensions:
            return False
        
        # Vérifier le type MIME
        mime_type = FileProcessor.get_mime_type(file_path)
        unsafe_mimes = {
            'application/x-msdownload',
            'application/x-msdos-program',
            'application/x-shellscript'
        }
        
        if mime_type in unsafe_mimes:
            return False
        
        return True