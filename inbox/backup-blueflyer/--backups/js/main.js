import AltTextGenerator from './alt.js';

// Initialize the alt text generator
window.altTextGenerator = new AltTextGenerator();

// Global state
let session;

// API endpoints
const API = {
    BASE_URL: 'https://bsky.social/xrpc',
    SESSION: '/com.atproto.server.createSession',
    PROFILE: '/app.bsky.actor.getProfile',
    CREATE_RECORD: '/com.atproto.repo.createRecord',
    UPLOAD_BLOB: '/com.atproto.repo.uploadBlob',
    REFRESH_SESSION: '/com.atproto.server.refreshSession'
};

// Store image uploads
const imageUploads = new Map();

// API utilities
const api = {
    async post(endpoint, body, headers = {}) {
        try {
            const response = await fetch(API.BASE_URL + endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...headers
                },
                body: JSON.stringify(body)
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            }
            
            return response.json();
        } catch (error) {
            console.error('API Post Error:', error);
            throw error;
        }
    },

    async get(endpoint, headers = {}) {
        try {
            const response = await fetch(API.BASE_URL + endpoint, { headers });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            }
            
            return response.json();
        } catch (error) {
            console.error('API Get Error:', error);
            throw error;
        }
    }
};

// Session Management
function saveSession(sessionData) {
    session = sessionData;
    // Save session to localStorage
    localStorage.setItem('bsky_session', JSON.stringify({
        ...sessionData,
        expiresAt: Date.now() + (2 * 60 * 60 * 1000) // 2 hours from now
    }));
}

function clearSession() {
    session = null;
    localStorage.removeItem('bsky_session');
}

async function loadSession() {
    const savedSession = localStorage.getItem('bsky_session');
    if (savedSession) {
        try {
            const parsed = JSON.parse(savedSession);
            // Check if session is expired
            if (parsed.expiresAt && Date.now() < parsed.expiresAt) {
                session = parsed;
                document.getElementById('loginForm').classList.add('hidden');
                document.getElementById('userProfile').classList.remove('hidden');
                await fetchProfile();
                return true;
            }
        } catch (error) {
            console.error('Error loading session:', error);
            clearSession();
        }
    }
    return false;
}

// Authentication
window.login = async function() {
    try {
        const handle = document.getElementById('handle').value;
        const password = document.getElementById('password').value;

        if (!handle || !password) {
            alert('Please enter both handle and password');
            return;
        }

        const data = await api.post(API.SESSION, {
            identifier: handle,
            password: password
        });

        if (!data.accessJwt) throw new Error('Invalid login credentials');

        saveSession(data);
        document.getElementById('loginForm').classList.add('hidden');
        document.getElementById('userProfile').classList.remove('hidden');
        await fetchProfile();
        announceMessage('Successfully logged in');
    } catch (error) {
        console.error('Login failed:', error);
        alert('Login failed: ' + error.message);
    }
};

window.logout = function() {
    clearSession();
    document.getElementById('loginForm').classList.remove('hidden');
    document.getElementById('userProfile').classList.add('hidden');
    announceMessage('Successfully logged out');
};

// Profile management
async function fetchProfile() {
    try {
        const profile = await api.get(
            `${API.PROFILE}?actor=${session.did}`,
            { Authorization: `Bearer ${session.accessJwt}` }
        );

        updateProfileUI(profile);
    } catch (error) {
        console.error('Failed to fetch profile:', error);
        alert('Failed to fetch profile: ' + error.message);
    }
}

function updateProfileUI(profile) {
    if (!profile) return;

    const avatar = document.getElementById('avatar');
    const displayName = document.getElementById('displayName');
    const handleName = document.getElementById('handleName');

    avatar.src = profile.avatar || 'https://placehold.co/100';
    avatar.alt = `${profile.displayName || 'User'}'s profile picture`;
    displayName.textContent = profile.displayName || 'Unknown User';
    handleName.textContent = '@' + profile.handle;
}

// Image handling
function setupImageHandling() {
    document.getElementById('imageUpload').addEventListener('change', async (e) => {
        const files = Array.from(e.target.files);
        if (!files.length) return;

        if (files.length + imageUploads.size > 4) {
            alert('Maximum 4 images allowed');
            return;
        }

        // Create all previews immediately
        const previews = files.map((file, index) => {
            const imageId = `img-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            
            const previewContainer = document.createElement('div');
            previewContainer.className = 'image-preview-container';
            previewContainer.id = imageId;
            previewContainer.innerHTML = `
                <div class="preview-controls">
                    <div class="preview-sequence-number">${index + 1}</div>
                    <div class="image-controls">
                        <button type="button" class="image-control-btn try-again-btn" aria-label="Try generating alt text again" title="Regenerate description">
                            <i class="fas fa-sync-alt"></i>
                        </button>
                        <button type="button" class="image-control-btn remove-btn" aria-label="Remove image" title="Remove image">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                </div>
                <img src="${URL.createObjectURL(file)}" alt="Image preview" class="preview-image">
                <div class="preview-loading">
                    <div class="loading-spinner"></div>
                    <div class="preview-loading-text">
                        Generating description...
                        <div><i>Always double check! I can be very wrong!</i></div>
                        <br>
                        <div>Image ${index + 1} of ${files.length}</div>
                    </div>
                </div>
                <div class="alt-text-area">
                    <div 
                        class="alt-text-editor"
                        contenteditable="true"
                        role="textbox"
                        aria-multiline="true"
                        aria-label="Image description"
                        placeholder="Image description (alt text)"></div>
                </div>
            `;

            document.getElementById('imageContainer').appendChild(previewContainer);
            
            imageUploads.set(imageId, {
                file,
                container: previewContainer,
                altText: ''
            });

            // Set up remove button handler
            previewContainer.querySelector('.remove-btn').addEventListener('click', () => {
                URL.revokeObjectURL(previewContainer.querySelector('img').src);
                previewContainer.remove();
                imageUploads.delete(imageId);
            });

            // Set up try again button handler
            previewContainer.querySelector('.try-again-btn').addEventListener('click', async () => {
                const loadingOverlay = document.createElement('div');
                loadingOverlay.className = 'preview-loading';
                loadingOverlay.innerHTML = `
                    <div class="loading-spinner"></div>
                    <div class="preview-loading-text">
                        Regenerating description...
                    </div>
                `;
                previewContainer.appendChild(loadingOverlay);

                // Hide the alt text area while regenerating
                const altTextArea = previewContainer.querySelector('.alt-text-area');
                altTextArea.classList.remove('ready');

                try {
                    const imageData = imageUploads.get(imageId);
                    if (!imageData || !imageData.file) {
                        throw new Error('Original image data not found');
                    }

                    const newAltText = await window.altTextGenerator.generateAltText(imageData.file, true);
                    
                    const editorEl = altTextArea.querySelector('.alt-text-editor');
                    editorEl.textContent = newAltText;
                    imageUploads.get(imageId).altText = newAltText;
                    
                    // Show the alt text area again
                    setTimeout(() => altTextArea.classList.add('ready'), 100);
                    
                    announceMessage('Generated new description for image');
                } catch (error) {
                    console.error('Error regenerating description:', error);
                    const editorEl = altTextArea.querySelector('.alt-text-editor');
                    editorEl.textContent = 'Error regenerating description. Please try again or enter a description manually.';
                    
                    // Show the alt text area even on error
                    setTimeout(() => altTextArea.classList.add('ready'), 100);
                    
                    announceMessage('Error regenerating description. Please try again or enter manually.');
                } finally {
                    loadingOverlay.style.opacity = '0';
                    setTimeout(() => loadingOverlay.remove(), 300);
                }
            });

            return { imageId, previewContainer, file };
        });

        // Process each preview sequentially
        for (const [index, preview] of previews.entries()) {
            try {
                const { imageId, previewContainer, file } = preview;
                
                // Generate alt text
                const altText = await window.altTextGenerator.generateAltText(file);
                
                // Remove loading overlay
                const loadingOverlay = previewContainer.querySelector('.preview-loading');
                loadingOverlay.style.opacity = '0';
                setTimeout(() => loadingOverlay.remove(), 300);
                
                // Update alt text and show container
                const altTextArea = previewContainer.querySelector('.alt-text-area');
                const editorEl = altTextArea.querySelector('.alt-text-editor');
                editorEl.textContent = altText;
                imageUploads.get(imageId).altText = altText;
                
                // Show the alt text area with animation
                setTimeout(() => altTextArea.classList.add('ready'), 100);
                
                announceMessage(`Generated description for image ${index + 1} of ${files.length}`);
            } catch (error) {
                console.error('Error processing image:', error);
                const { previewContainer } = preview;
                
                // Remove loading overlay
                const loadingOverlay = previewContainer.querySelector('.preview-loading');
                loadingOverlay.style.opacity = '0';
                setTimeout(() => loadingOverlay.remove(), 300);
                
                // Show error in alt text editor and show container
                const altTextArea = previewContainer.querySelector('.alt-text-area');
                const editorEl = altTextArea.querySelector('.alt-text-editor');
                editorEl.textContent = 'Error generating description. Please enter a description manually.';
                
                // Show the alt text area with animation
                setTimeout(() => altTextArea.classList.add('ready'), 100);
                
                announceMessage(`Error processing image ${index + 1}. Please add description manually.`);
            }
        }
    });
}

// Post handling
function setupPostForm() {
    document.getElementById('newPostForm').addEventListener('submit', async (event) => {
        event.preventDefault();
        
        try {
            const images = [];
            
            for (const [imageId, imageData] of imageUploads) {
                const blob = await fetch(imageData.container.querySelector('img').src).then(r => r.blob());
                const uploadData = await api.post(
                    API.UPLOAD_BLOB,
                    blob,
                    {
                        Authorization: `Bearer ${session.accessJwt}`,
                        'Content-Type': imageData.file.type
                    }
                );
                
                images.push({
                    image: uploadData.blob,
                    alt: imageData.container.querySelector('.alt-text-editor').textContent
                });
            }

            const postResponse = await api.post(
                API.CREATE_RECORD,
                {
                    repo: session.did,
                    collection: 'app.bsky.feed.post',
                    record: {
                        text: document.getElementById('postText').textContent,
                        createdAt: new Date().toISOString(),
                        embed: images.length ? {
                            $type: 'app.bsky.embed.images',
                            images: images.map(img => ({
                                ...img,
                                alt: imageUploads.get(img.id)?.container.querySelector('.alt-text-editor').textContent || ''
                            }))
                        } : undefined
                    }
                },
                { Authorization: `Bearer ${session.accessJwt}` }
            );

            // Create and show the post link
            const postUri = postResponse.uri;
            const postRkey = postUri.split('/').pop();
            const postUrl = `https://bsky.app/profile/${session.handle}/post/${postRkey}`;
            
            // Create success message with link
            const successMessage = document.createElement('div');
            successMessage.className = 'post-success-message';
            successMessage.innerHTML = `
                <div class="success-content">
                    <i class="fas fa-check-circle"></i>
                    <p>Post created successfully!</p>
                    <a href="${postUrl}" target="_blank" rel="noopener noreferrer" class="post-link">
                        <i class="fas fa-external-link-alt"></i>
                        View Post
                    </a>
                </div>
            `;
            
            // Add to page
            document.getElementById('newPostForm').appendChild(successMessage);
            
            // Remove after 10 seconds
            setTimeout(() => {
                successMessage.style.opacity = '0';
                setTimeout(() => successMessage.remove(), 300);
            }, 10000);

            clearPostForm();
            announceMessage('Post created successfully');
        } catch (error) {
            console.error('Failed to create post:', error);
            alert('Failed to create post: ' + error.message);
        }
    });
}

function clearPostForm() {
    document.getElementById('postText').textContent = '';
    document.getElementById('imageUpload').value = '';
    document.getElementById('imageContainer').innerHTML = '';
    imageUploads.clear();
    
    // Remove any existing success messages
    const existingMessages = document.querySelectorAll('.post-success-message');
    existingMessages.forEach(msg => msg.remove());
}

// Accessibility
function announceMessage(message) {
    const announcement = document.createElement('div');
    announcement.setAttribute('role', 'status');
    announcement.setAttribute('aria-live', 'polite');
    announcement.className = 'sr-only';
    announcement.textContent = message;
    document.body.appendChild(announcement);
    setTimeout(() => announcement.remove(), 1000);
}

// Setup paste handling
function setupPasteHandling() {
    const postText = document.getElementById('postText');
    
    postText.addEventListener('paste', async (e) => {
        // Get clipboard items
        const items = Array.from(e.clipboardData.items);
        const imageItems = items.filter(item => item.type.startsWith('image/'));
        
        if (imageItems.length > 0) {
            e.preventDefault(); // Prevent default paste for images
            
            // Check image limit
            if (imageItems.length + imageUploads.size > 4) {
                alert('Maximum 4 images allowed');
                return;
            }
            
            // Process each image
            for (const item of imageItems) {
                const file = item.getAsFile();
                if (file) {
                    // Create a fake change event to reuse existing image handling
                    const fakeEvent = {
                        target: {
                            files: [file]
                        }
                    };
                    
                    // Process the image using existing handler
                    const imageUpload = document.getElementById('imageUpload');
                    const changeEvent = new Event('change');
                    Object.defineProperty(changeEvent, 'target', {value: fakeEvent.target});
                    imageUpload.dispatchEvent(changeEvent);
                }
            }
        }
    });
}

// Initialize
function initialize() {
    document.getElementById('loginForm').classList.remove('hidden');
    document.getElementById('userProfile').classList.add('hidden');
    setupImageHandling();
    setupPostForm();
    setupPasteHandling();
    loadSession();
}

// Start the application
initialize(); 