// PWA Installation Handler
let deferredPrompt;

// Listen for the beforeinstallprompt event
window.addEventListener('beforeinstallprompt', (e) => {
    // Prevent the default prompt
    e.preventDefault();
    // Store the event for later use
    deferredPrompt = e;
    
    // Add install button to the UI if not already present
    if (!document.getElementById('installButton')) {
        const button = document.createElement('button');
        button.id = 'installButton';
        button.className = 'btn btn-primary';
        button.textContent = 'Install App';
        button.addEventListener('click', async () => {
            if (!deferredPrompt) return;
            
            try {
                // Show the prompt
                await deferredPrompt.prompt();
                // Wait for user choice
                const result = await deferredPrompt.userChoice;
                if (result.outcome === 'accepted') {
                    console.log('User accepted the install prompt');
                    if (typeof showToast === 'function') {
                        showToast({
                            type: 'success',
                            message: 'App installed successfully!',
                            duration: 3000
                        });
                    }
                }
            } catch (error) {
                console.error('Install prompt error:', error);
            } finally {
                deferredPrompt = null;
                button.remove();
            }
        });
        
        // Add button to the header or appropriate container
        const container = document.querySelector('header') || document.body;
        container.appendChild(button);
    }
});

// Listen for successful installation
window.addEventListener('appinstalled', () => {
    console.log('PWA was installed');
    deferredPrompt = null;
    // Remove install button if it exists
    const installButton = document.getElementById('installButton');
    if (installButton) {
        installButton.remove();
    }
}); 