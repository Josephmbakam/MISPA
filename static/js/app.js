// JavaScript principal pour MISPA 7.0

// Initialisation de Socket.IO
const socket = io();

// Variables globales
let currentUser = null;
let currentChat = null;
let isTyping = false;
let typingTimeout = null;

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    // Vérifier si l'utilisateur est connecté
    checkAuthStatus();
    
    // Initialiser les composants
    initComponents();
    
    // Configurer les événements
    setupEventListeners();
});

// Vérifier le statut d'authentification
function checkAuthStatus() {
    // Vérifier si un token existe
    const token = localStorage.getItem('mispa_token');
    if (token) {
        // Valider le token
        validateToken(token);
    }
}

// Valider le token d'authentification
function validateToken(token) {
    fetch('/api/validate_token', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.valid) {
            currentUser = data.user;
            updateUIForUser();
        } else {
            // Token invalide, déconnecter
            logout();
        }
    })
    .catch(error => {
        console.error('Erreur validation token:', error);
    });
}

// Initialiser les composants
function initComponents() {
    // Initialiser les tooltips
    initTooltips();
    
    // Initialiser les animations
    initAnimations();
    
    // Initialiser le thème
    initTheme();
}

// Configurer les événements
function setupEventListeners() {
    // Gestionnaire de déconnexion
    const logoutBtn = document.querySelector('[data-action="logout"]');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }
    
    // Gestionnaire de recherche
    const searchInput = document.querySelector('.search-input');
    if (searchInput) {
        searchInput.addEventListener('input', handleSearch);
    }
    
    // Gestionnaire de messages
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.addEventListener('input', handleTyping);
        messageInput.addEventListener('keypress', handleMessageKeyPress);
    }
    
    // Gestionnaire d'envoi de message
    const sendBtn = document.getElementById('sendBtn');
    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }
}

// Mettre à jour l'interface pour l'utilisateur connecté
function updateUIForUser() {
    if (!currentUser) return;
    
    // Mettre à jour le nom d'utilisateur
    const usernameElements = document.querySelectorAll('.username-display');
    usernameElements.forEach(el => {
        el.textContent = currentUser.username;
    });
    
    // Mettre à jour l'avatar
    const avatarElements = document.querySelectorAll('.user-avatar');
    avatarElements.forEach(el => {
        el.textContent = currentUser.username.charAt(0).toUpperCase();
    });
    
    // Afficher les éléments réservés aux utilisateurs connectés
    const authElements = document.querySelectorAll('.auth-only');
    authElements.forEach(el => {
        el.style.display = 'block';
    });
    
    // Cacher les éléments pour les non-connectés
    const guestElements = document.querySelectorAll('.guest-only');
    guestElements.forEach(el => {
        el.style.display = 'none';
    });
}

// Gestion de la recherche
function handleSearch(event) {
    const searchTerm = event.target.value.trim();
    
    if (searchTerm.length < 2) {
        return;
    }
    
    // Rechercher des utilisateurs
    searchUsers(searchTerm);
}

// Rechercher des utilisateurs
function searchUsers(query) {
    fetch(`/api/search_users?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            displaySearchResults(data.users);
        })
        .catch(error => {
            console.error('Erreur recherche:', error);
        });
}

// Afficher les résultats de recherche
function displaySearchResults(users) {
    const resultsContainer = document.getElementById('searchResults');
    if (!resultsContainer) return;
    
    resultsContainer.innerHTML = '';
    
    if (users.length === 0) {
        resultsContainer.innerHTML = '<p class="no-results">Aucun utilisateur trouvé</p>';
        return;
    }
    
    users.forEach(user => {
        const userElement = document.createElement('div');
        userElement.className = 'search-result-item';
        userElement.innerHTML = `
            <div class="result-avatar">${user.username.charAt(0).toUpperCase()}</div>
            <div class="result-info">
                <div class="result-name">${user.username}</div>
                <div class="result-email">${user.email}</div>
            </div>
            ${user.is_contact ? 
                '<span class="result-status">Contact</span>' : 
                '<button class="btn-add-contact" data-user-id="${user.id}">Ajouter</button>'
            }
        `;
        resultsContainer.appendChild(userElement);
    });
    
    // Ajouter les événements aux boutons
    resultsContainer.querySelectorAll('.btn-add-contact').forEach(btn => {
        btn.addEventListener('click', function() {
            const userId = this.dataset.userId;
            addContact(userId);
        });
    });
}

// Ajouter un contact
function addContact(userId) {
    fetch(`/api/add_contact/${userId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Contact ajouté avec succès', 'success');
            // Actualiser les résultats de recherche
            const searchInput = document.querySelector('.search-input');
            if (searchInput.value) {
                searchUsers(searchInput.value);
            }
        } else {
            showNotification(data.error || 'Erreur lors de l\'ajout', 'error');
        }
    })
    .catch(error => {
        console.error('Erreur:', error);
        showNotification('Erreur de connexion', 'error');
    });
}

// Gestion de la saisie de message
function handleTyping(event) {
    if (!currentChat || !isTyping) {
        isTyping = true;
        socket.emit('typing', {
            chat_id: currentChat,
            is_typing: true
        });
    }
    
    // Réinitialiser le timeout
    clearTimeout(typingTimeout);
    typingTimeout = setTimeout(() => {
        if (isTyping) {
            isTyping = false;
            socket.emit('typing', {
                chat_id: currentChat,
                is_typing: false
            });
        }
    }, 1000);
}

// Gestion des touches dans le champ de message
function handleMessageKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Envoyer un message
function sendMessage() {
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();
    
    if (!message || !currentChat) {
        return;
    }
    
    const messageData = {
        chat_id: currentChat,
        content: message,
        type: 'text'
    };
    
    // Ajouter le message à l'interface immédiatement (optimistic update)
    addMessageToUI({
        id: Date.now(),
        sender_id: currentUser.id,
        content: message,
        timestamp: new Date().toISOString(),
        is_sent: true
    });
    
    // Effacer le champ de saisie
    messageInput.value = '';
    
    // Envoyer au serveur
    socket.emit('send_message', messageData);
}

// Ajouter un message à l'interface
function addMessageToUI(message) {
    const messagesContainer = document.getElementById('messagesContainer');
    if (!messagesContainer) return;
    
    const messageElement = document.createElement('div');
    messageElement.className = `message ${message.sender_id === currentUser.id ? 'message-sent' : 'message-received'}`;
    
    const time = new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    messageElement.innerHTML = `
        <div class="message-content">
            ${message.content}
            <div class="message-time">${time}</div>
        </div>
    `;
    
    messagesContainer.appendChild(messageElement);
    
    // Scroll vers le bas
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Déconnexion
function logout() {
    localStorage.removeItem('mispa_token');
    socket.disconnect();
    
    // Rediriger vers la page de connexion
    window.location.href = '/login';
}

// Afficher une notification
function showNotification(message, type = 'info') {
    // Créer l'élément de notification
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        </div>
        <button class="notification-close">&times;</button>
    `;
    
    // Ajouter au document
    document.body.appendChild(notification);
    
    // Animation d'entrée
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    // Fermer automatiquement après 5 secondes
    const autoClose = setTimeout(() => {
        closeNotification(notification);
    }, 5000);
    
    // Bouton de fermeture
    notification.querySelector('.notification-close').addEventListener('click', function() {
        clearTimeout(autoClose);
        closeNotification(notification);
    });
    
    // Fermer la notification
    function closeNotification(notif) {
        notif.classList.remove('show');
        setTimeout(() => {
            if (notif.parentNode) {
                notif.parentNode.removeChild(notif);
            }
        }, 300);
    }
}

// Initialiser les tooltips
function initTooltips() {
    const tooltips = document.querySelectorAll('[data-tooltip]');
    
    tooltips.forEach(element => {
        element.addEventListener('mouseenter', function() {
            const tooltipText = this.dataset.tooltip;
            const tooltip = document.createElement('div');
            tooltip.className = 'tooltip';
            tooltip.textContent = tooltipText;
            
            document.body.appendChild(tooltip);
            
            const rect = this.getBoundingClientRect();
            tooltip.style.left = rect.left + (rect.width / 2) - (tooltip.offsetWidth / 2) + 'px';
            tooltip.style.top = rect.top - tooltip.offsetHeight - 10 + 'px';
        });
        
        element.addEventListener('mouseleave', function() {
            const tooltip = document.querySelector('.tooltip');
            if (tooltip) {
                tooltip.parentNode.removeChild(tooltip);
            }
        });
    });
}

// Initialiser les animations
function initAnimations() {
    // Animation au scroll
    const animatedElements = document.querySelectorAll('.animate-on-scroll');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animated');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1 });
    
    animatedElements.forEach(element => {
        observer.observe(element);
    });
}

// Initialiser le thème
function initTheme() {
    const savedTheme = localStorage.getItem('mispa_theme') || 'dark';
    document.body.setAttribute('data-theme', savedTheme);
    
    // Mettre à jour le sélecteur de thème
    const themeSelect = document.getElementById('themeSelect');
    if (themeSelect) {
        themeSelect.value = savedTheme;
        themeSelect.addEventListener('change', function() {
            const theme = this.value;
            document.body.setAttribute('data-theme', theme);
            localStorage.setItem('mispa_theme', theme);
            
            // Envoyer la préférence au serveur
            if (currentUser) {
                updateUserTheme(theme);
            }
        });
    }
}

// Mettre à jour le thème de l'utilisateur
function updateUserTheme(theme) {
    fetch('/api/update_theme', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ theme: theme })
    })
    .catch(error => {
        console.error('Erreur mise à jour thème:', error);
    });
}

// Gestion des fichiers
function handleFileUpload(files, chatId) {
    const formData = new FormData();
    formData.append('chat_id', chatId);
    
    for (let i = 0; i < files.length; i++) {
        formData.append('files[]', files[i]);
    }
    
    // Afficher la progression
    const progressBar = document.createElement('div');
    progressBar.className = 'upload-progress';
    progressBar.innerHTML = `
        <div class="progress-bar">
            <div class="progress-fill" style="width: 0%"></div>
        </div>
        <div class="progress-text">0%</div>
    `;
    
    const messagesContainer = document.getElementById('messagesContainer');
    if (messagesContainer) {
        messagesContainer.appendChild(progressBar);
    }
    
    // Envoyer les fichiers
    fetch('/api/upload_files', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            progressBar.querySelector('.progress-fill').style.width = '100%';
            progressBar.querySelector('.progress-text').textContent = '100%';
            
            // Ajouter les messages de fichier
            data.files.forEach(file => {
                addFileMessageToUI(file, chatId);
            });
            
            // Supprimer la barre de progression après un délai
            setTimeout(() => {
                if (progressBar.parentNode) {
                    progressBar.parentNode.removeChild(progressBar);
                }
            }, 1000);
        }
    })
    .catch(error => {
        console.error('Erreur upload:', error);
        progressBar.innerHTML = '<div class="upload-error">Erreur lors du téléchargement</div>';
    });
}

// Ajouter un message de fichier à l'interface
function addFileMessageToUI(file, chatId) {
    const messagesContainer = document.getElementById('messagesContainer');
    if (!messagesContainer) return;
    
    const messageElement = document.createElement('div');
    messageElement.className = 'message message-sent file-message';
    
    const icon = getFileIcon(file.type);
    const size = formatFileSize(file.size);
    
    messageElement.innerHTML = `
        <div class="message-content">
            <div class="file-info">
                <div class="file-icon">${icon}</div>
                <div class="file-details">
                    <div class="file-name">${file.name}</div>
                    <div class="file-size">${size}</div>
                </div>
                <a href="${file.url}" class="download-btn" download>
                    <i class="fas fa-download"></i>
                </a>
            </div>
            <div class="message-time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
        </div>
    `;
    
    messagesContainer.appendChild(messageElement);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Obtenir l'icône d'un fichier selon son type
function getFileIcon(fileType) {
    const icons = {
        'image': 'fas fa-image',
        'video': 'fas fa-video',
        'audio': 'fas fa-music',
        'pdf': 'fas fa-file-pdf',
        'word': 'fas fa-file-word',
        'excel': 'fas fa-file-excel',
        'powerpoint': 'fas fa-file-powerpoint',
        'archive': 'fas fa-file-archive',
        'text': 'fas fa-file-alt',
        'code': 'fas fa-file-code'
    };
    
    if (fileType.startsWith('image/')) return icons.image;
    if (fileType.startsWith('video/')) return icons.video;
    if (fileType.startsWith('audio/')) return icons.audio;
    if (fileType === 'application/pdf') return icons.pdf;
    if (fileType.includes('word')) return icons.word;
    if (fileType.includes('excel') || fileType.includes('spreadsheet')) return icons.excel;
    if (fileType.includes('powerpoint') || fileType.includes('presentation')) return icons.powerpoint;
    if (fileType.includes('zip') || fileType.includes('rar') || fileType.includes('archive')) return icons.archive;
    if (fileType.includes('text')) return icons.text;
    if (fileType.includes('javascript') || fileType.includes('python') || fileType.includes('code')) return icons.code;
    
    return 'fas fa-file';
}

// Formater la taille d'un fichier
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Gestion de l'enregistrement vocal
let mediaRecorder = null;
let audioChunks = [];

function startVoiceRecording() {
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            
            mediaRecorder.addEventListener('dataavailable', event => {
                audioChunks.push(event.data);
            });
            
            mediaRecorder.addEventListener('stop', () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                sendVoiceMessage(audioBlob);
                
                // Arrêter le stream
                stream.getTracks().forEach(track => track.stop());
            });
            
            mediaRecorder.start();
            
            // Mettre à jour l'interface
            document.getElementById('voiceBtn').classList.add('recording');
        })
        .catch(error => {
            console.error('Erreur enregistrement:', error);
            showNotification('Impossible d\'accéder au microphone', 'error');
        });
}

function stopVoiceRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        document.getElementById('voiceBtn').classList.remove('recording');
    }
}

function sendVoiceMessage(audioBlob) {
    if (!currentChat) return;
    
    const formData = new FormData();
    formData.append('chat_id', currentChat);
    formData.append('audio', audioBlob, 'voice_message.webm');
    
    fetch('/api/send_voice_message', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            addVoiceMessageToUI(data.message);
        }
    })
    .catch(error => {
        console.error('Erreur envoi audio:', error);
        showNotification('Erreur lors de l\'envoi du message vocal', 'error');
    });
}

function addVoiceMessageToUI(message) {
    const messagesContainer = document.getElementById('messagesContainer');
    if (!messagesContainer) return;
    
    const messageElement = document.createElement('div');
    messageElement.className = 'message message-sent voice-message';
    
    const time = new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    messageElement.innerHTML = `
        <div class="message-content">
            <div class="voice-message-player">
                <button class="play-btn">
                    <i class="fas fa-play"></i>
                </button>
                <div class="waveform">
                    <div class="wave"></div>
                    <div class="wave"></div>
                    <div class="wave"></div>
                    <div class="wave"></div>
                    <div class="wave"></div>
                </div>
                <div class="duration">${message.duration || '0:00'}</div>
            </div>
            <div class="message-time">${time}</div>
        </div>
    `;
    
    messagesContainer.appendChild(messageElement);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    // Ajouter l'événement de lecture
    const playBtn = messageElement.querySelector('.play-btn');
    playBtn.addEventListener('click', function() {
        const audio = new Audio(message.url);
        audio.play();
        
        // Animation de la waveform pendant la lecture
        const waves = messageElement.querySelectorAll('.wave');
        waves.forEach(wave => wave.classList.add('playing'));
        
        audio.addEventListener('ended', () => {
            waves.forEach(wave => wave.classList.remove('playing'));
        });
    });
}

// Traduction de texte
function translateText(text, targetLanguage) {
    return fetch('/api/translate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            text: text,
            target_language: targetLanguage
        })
    })
    .then(response => response.json())
    .then(data => {
        return data.translation;
    })
    .catch(error => {
        console.error('Erreur traduction:', error);
        return text; // Retourner le texte original en cas d'erreur
    });
}

// Gestionnaire d'erreurs global
window.addEventListener('error', function(event) {
    console.error('Erreur globale:', event.error);
    showNotification('Une erreur est survenue', 'error');
});

// Exporter les fonctions nécessaires
window.MISPA = {
    logout: logout,
    showNotification: showNotification,
    translateText: translateText,
    startVoiceRecording: startVoiceRecording,
    stopVoiceRecording: stopVoiceRecording
};
