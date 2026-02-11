// Gestion de la navigation
function navigateTo(page, params = {}) {
    switch(page) {
        case 'login':
            window.location.href = '/login';
            break;
        case 'register':
            window.location.href = '/register';
            break;
        case 'chat':
            window.location.href = '/chat';
            break;
        case 'settings':
            window.location.href = '/settings';
            break;
        case 'contacts':
            window.location.href = '/contacts';
            break;
        case 'home':
            window.location.href = '/';
            break;
        default:
            console.error('Page inconnue:', page);
    }
}

// Navigation pour les boutons d'authentification
document.addEventListener('DOMContentLoaded', function() {
    // Boutons de la page d'accueil
    const loginBtn = document.getElementById('loginBtn');
    const registerBtn = document.getElementById('registerBtn');
    
    if (loginBtn) {
        loginBtn.addEventListener('click', function(e) {
            e.preventDefault();
            navigateTo('login');
        });
    }
    
    if (registerBtn) {
        registerBtn.addEventListener('click', function(e) {
            e.preventDefault();
            navigateTo('register');
        });
    }
    
    // Boutons dans les formulaires
    const backToHomeBtn = document.getElementById('backToHome');
    if (backToHomeBtn) {
        backToHomeBtn.addEventListener('click', function(e) {
            e.preventDefault();
            navigateTo('home');
        });
    }
    
    // Redirection après connexion/inscription réussie
    if (window.location.pathname === '/login' && document.referrer.includes('/register')) {
        showNotification('Compte créé avec succès! Vous pouvez maintenant vous connecter.', 'success');
    }
});

// Gestion du retour en arrière
window.addEventListener('popstate', function(event) {
    if (event.state && event.state.page) {
        loadPage(event.state.page);
    }
});

// Chargement dynamique de contenu (optionnel)
function loadPage(page) {
    fetch(`/partials/${page}`)
        .then(response => response.text())
        .then(html => {
            document.getElementById('content').innerHTML = html;
            window.history.pushState({page: page}, '', `/${page}`);
            initPageScripts();
        })
        .catch(error => {
            console.error('Erreur chargement page:', error);
            navigateTo(page);
        });
}

// Initialisation des scripts de page
function initPageScripts() {
    // Initialisation spécifique à chaque page
    if (window.location.pathname.includes('/chat')) {
        initChatPage();
    } else if (window.location.pathname.includes('/settings')) {
        initSettingsPage();
    }
}