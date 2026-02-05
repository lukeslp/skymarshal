import AltTextGenerator from './alt_o.js';

// Initialize the alt text generator
window.altTextGenerator = new AltTextGenerator();

// Add styles for the loading screen
const style = document.createElement('style');
style.textContent = `
    .preview-loading {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.85);
        display: flex;
        align-items: center;
        justify-content: center;
        opacity: 0.95;
        transition: opacity 0.3s ease;
    }

    .preview-loading.done {
        opacity: 1;
        pointer-events: none;
    }

    .loading-content {
        max-width: 90%;
        text-align: center;
        color: #fff;
        padding: 1.5rem;
    }

    .loading-spinner {
        width: 40px;
        height: 40px;
        border: 3px solid rgba(255, 255, 255, 0.3);
        border-radius: 50%;
        border-top-color: #fff;
        animation: spin 1s linear infinite;
        margin: 0 auto 1.5rem;
    }

    .loading-status {
        font-size: 1.1rem;
        font-weight: 500;
        margin-bottom: 1rem;
        color: #fff;
    }

    .loading-steps {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
        margin-bottom: 1rem;
        opacity: 0.7;
    }

    .loading-step {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.9rem;
        opacity: 0.6;
        transition: opacity 0.3s ease;
    }

    .loading-step[data-active="true"] {
        opacity: 1;
        color: #3b82f6;
    }

    .loading-step[data-done="true"] {
        opacity: 0.8;
        color: #22c55e;
    }

    .loading-step i {
        width: 1.2rem;
        text-align: center;
    }

    .loading-warning {
        font-size: 0.85rem;
        color: #fbbf24;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
    }

    .loading-step[data-error="true"] {
        opacity: 0.8;
        color: #ef4444 !important;
    }

    .preview-loading.error .loading-warning {
        color: #ef4444;
    }

    .preview-loading.error .loading-spinner {
        border-top-color: #ef4444;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);

// Global state
let session;
let pullToRefreshEnabled = false;
let startY = 0;
let currentY = 0;
let pulling = false;
let ptrElement = null;
let refreshing = false;

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
            const url = API.BASE_URL + (endpoint.startsWith('/') ? endpoint : '/' + endpoint);
            const response = await fetch(url, {
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
            const url = API.BASE_URL + (endpoint.startsWith('/') ? endpoint : '/' + endpoint);
            const response = await fetch(url, { headers });
            
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
    // Save session to localStorage with proper expiration handling
    localStorage.setItem('bsky_session', JSON.stringify({
        ...sessionData,
        savedAt: Date.now(),
        expiresAt: Date.now() + (2 * 60 * 60 * 1000) // 2 hours from now
    }));
}

function clearSession() {
    session = null;
    localStorage.removeItem('bsky_session');
    // Clear any other session-related data
    localStorage.removeItem('bsky_user_profile');
    // Don't manipulate the logout button visibility
}

async function refreshSession() {
    try {
        const refreshResponse = await api.post(
            API.REFRESH_SESSION,
            {},
            { Authorization: `Bearer ${session.refreshJwt}` }
        );

        if (refreshResponse.accessJwt && refreshResponse.refreshJwt) {
            saveSession(refreshResponse);
            return true;
        }
        return false;
    } catch (error) {
        console.error('Session refresh failed:', error);
        return false;
    }
}

async function validateSession(sessionData) {
    if (!sessionData || !sessionData.accessJwt || !sessionData.refreshJwt) {
        return false;
    }

    // Check if session is close to expiration (within 5 minutes)
    const expiresAt = sessionData.expiresAt || 0;
    const isNearExpiration = Date.now() > (expiresAt - 5 * 60 * 1000);
    
    if (isNearExpiration) {
        // Try to refresh the session
        session = sessionData; // Temporarily set session for refresh
        const refreshed = await refreshSession();
        if (!refreshed) {
            clearSession();
            return false;
        }
        return true;
    }

    return true;
}

async function loadSession() {
    try {
        const savedSession = localStorage.getItem('bsky_session');
        if (!savedSession) {
            return false;
        }

        const sessionData = JSON.parse(savedSession);
        const isValid = await validateSession(sessionData);
        
        if (isValid) {
            session = sessionData;
            document.getElementById('loginForm').classList.add('hidden');
            document.getElementById('userProfile').classList.remove('hidden');
            await fetchProfile();
            
            // Save profile data for faster loading
            const profile = await api.get(
                `${API.PROFILE}?actor=${session.did}`,
                { Authorization: `Bearer ${session.accessJwt}` }
            );
            localStorage.setItem('bsky_user_profile', JSON.stringify(profile));
            
            return true;
        }
    } catch (error) {
        console.error('Error loading session:', error);
        clearSession();
    }
    return false;
}

// Add screen reader announcement utilities
function announceToScreenReader(message, isAlert = false) {
    const element = document.getElementById(isAlert ? 'sr-alerts' : 'sr-announcements');
    element.textContent = message;
}

// Authentication
async function login() {
    const handle = document.getElementById('handle').value.trim();
    const password = document.getElementById('password').value;

    if (!handle || !password) {
        announceToScreenReader('Please enter both handle and password', true);
        showToast({
            type: 'error',
            message: 'Please enter both handle and password',
            duration: 3000
        });
        return;
    }

    try {
        announceToScreenReader('Logging in, please wait...');
        
        // Create session
        const createSession = await api.post(API.SESSION, {
            identifier: handle,
            password: password
        });

        if (!createSession.accessJwt || !createSession.refreshJwt) {
            throw new Error('Invalid session response');
        }

        // Save session
        saveSession(createSession);

        // Clear password field
        document.getElementById('password').value = '';

        // Update UI
        document.getElementById('loginForm').classList.add('hidden');
        document.getElementById('userProfile').classList.remove('hidden');

        // Fetch and update profile
        await fetchProfile();

        announceToScreenReader('Successfully logged in');
        showToast({
            type: 'success',
            message: 'Successfully logged in!',
            duration: 3000
        });

    } catch (error) {
        console.error('Login failed:', error);
        clearSession();
        
        const errorMessage = error.status === 401 
            ? 'Invalid handle or password' 
            : 'Login failed. Please try again.';
        
        announceToScreenReader(errorMessage, true);
        showToast({
            type: 'error',
            message: errorMessage,
            duration: 5000
        });
    }
}

// Expose login function to window object
window.login = login;

window.logout = function() {
    clearSession();
    document.getElementById('loginForm').classList.remove('hidden');
    document.getElementById('userProfile').classList.add('hidden');
    announceToScreenReader('Successfully logged out');
};

window.toggleCoverPhoto = function(button) {
    const container = button.closest('.cover-photo-container');
    const isExpanding = !container.classList.contains('expanded');
    container.classList.toggle('expanded');
    announceToScreenReader(isExpanding ? 'Cover photo expanded' : 'Cover photo collapsed');
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

    // Update basic info
    const avatar = document.getElementById('avatar');
    const displayName = document.getElementById('displayName');
    const handleName = document.getElementById('handleName');
    const coverPhoto = document.getElementById('coverPhoto');

    avatar.src = profile.avatar || 'https://placehold.co/100';
    avatar.alt = `${profile.displayName || 'User'}'s profile picture`;
    displayName.textContent = profile.displayName || 'Unknown User';
    handleName.textContent = '@' + profile.handle;

    // Update cover photo if available
    if (profile.banner) {
        coverPhoto.style.backgroundImage = `url(${profile.banner})`;
    } else {
        coverPhoto.style.backgroundImage = 'none';
    }

    // Update stats
    document.getElementById('postCount').textContent = profile.postsCount?.toLocaleString() || '0';
    document.getElementById('followingCount').textContent = profile.followsCount?.toLocaleString() || '0';
    document.getElementById('followerCount').textContent = profile.followersCount?.toLocaleString() || '0';
    
    // Format and set join date
    if (profile.indexedAt) {
        const joinDate = new Date(profile.indexedAt);
        document.getElementById('joinDate').textContent = joinDate.toLocaleDateString(undefined, {
            year: 'numeric',
            month: 'short'
        });
    }
}

// Add image optimization utilities
const imageOptimization = {
    // Check if the browser supports WebP
    async supportsWebP() {
        if (!self.createImageBitmap) return false;
        
        const webpData = 'data:image/webp;base64,UklGRh4AAABXRUJQVlA4TBEAAAAvAAAAAAfQ//73v/+BiOh/AAA=';
        const blob = await fetch(webpData).then(r => r.blob());
        return createImageBitmap(blob).then(() => true, () => false);
    },

    // Create optimized srcset for responsive images
    async createSrcSet(file) {
        const sizes = [400, 800, 1200];
        const srcSet = [];
        
        for (const size of sizes) {
            const resized = await this.resizeImage(file, size);
            const url = URL.createObjectURL(resized);
            srcSet.push(`${url} ${size}w`);
        }
        
        return srcSet.join(', ');
    },

    // Resize image while maintaining aspect ratio
    async resizeImage(file, maxWidth) {
        return new Promise((resolve) => {
            const img = new Image();
            const objectUrl = URL.createObjectURL(file);
            
            img.onload = () => {
                URL.revokeObjectURL(objectUrl);
                const aspectRatio = img.height / img.width;
                const width = Math.min(maxWidth, img.width);
                const height = width * aspectRatio;
                
                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;
                
                const ctx = canvas.getContext('2d', { alpha: false });
                ctx.fillStyle = '#FFFFFF';
                ctx.fillRect(0, 0, width, height);
                ctx.drawImage(img, 0, 0, width, height);
                
                canvas.toBlob(resolve, 'image/jpeg', 0.85);
            };
            
            img.src = objectUrl;
        });
    }
};

// Update image processing utility
async function processImage(file) {
    const img = new Image();
    const canvas = document.createElement('canvas');
    const MAX_SIZE = 2048;
    
    // Create a loading placeholder
    const placeholder = await createPlaceholder(file);
    
    // Load the image
    await new Promise((resolve, reject) => {
        img.onload = resolve;
        img.onerror = reject;
        img.src = URL.createObjectURL(file);
    });

    // Calculate dimensions while maintaining aspect ratio
    let { width, height } = img;
    const aspectRatio = {
        width: width,
        height: height
    };

    // Scale down if necessary
    if (width > height && width > MAX_SIZE) {
        height = Math.round((height / width) * MAX_SIZE);
        width = MAX_SIZE;
    } else if (height > MAX_SIZE) {
        width = Math.round((width / height) * MAX_SIZE);
        height = MAX_SIZE;
    }

    // Set canvas dimensions
    canvas.width = width;
    canvas.height = height;
    
    // Get context and configure image rendering
    const ctx = canvas.getContext('2d', { alpha: false });
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = 'high';
    
    // Draw image
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(img, 0, 0, width, height);

    // Generate optimized versions
    const srcSet = await imageOptimization.createSrcSet(file);
    const supportsWebP = await imageOptimization.supportsWebP();
    
    // Convert to blob with proper encoding
    const blob = await new Promise(resolve => {
        canvas.toBlob(resolve, supportsWebP ? 'image/webp' : 'image/jpeg', 0.92);
    });

    // Clean up
    URL.revokeObjectURL(img.src);

    return {
        blob,
        aspectRatio,
        type: supportsWebP ? 'image/webp' : 'image/jpeg',
        placeholder,
        srcSet
    };
}

// Create low-quality image placeholder
async function createPlaceholder(file) {
    return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                canvas.width = 40;
                canvas.height = (40 * img.height) / img.width;
                
                const ctx = canvas.getContext('2d', { alpha: false });
                ctx.fillStyle = '#FFFFFF';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                
                resolve(canvas.toDataURL('image/jpeg', 0.5));
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    });
}

// Update image preview creation
function createImagePreview(file, imageId, imageNumber, totalImages) {
    const previewContainer = document.createElement('div');
    previewContainer.className = 'image-preview-container';
    previewContainer.id = imageId;
    
    previewContainer.innerHTML = `
        <div class="preview-controls">
            <div class="preview-sequence-number">${imageNumber}</div>
            <div class="image-controls">
                <button type="button" class="image-control-btn try-again-btn" aria-label="Try generating alt text again" title="Regenerate description">
                    <i class="fas fa-sync-alt"></i>
                </button>
                <button type="button" class="image-control-btn remove-btn" aria-label="Remove image" title="Remove image">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        </div>
        <img src="" 
             alt="Image preview" 
             class="preview-image"
             loading="lazy"
             decoding="async">
        <div class="preview-loading">
            <div class="loading-content">
                <img src="https://actuallyusefulai.com/bsky/assets/spinner_transparent.gif" 
                     alt="Loading spinner"
                     class="loading-spinner">
                <div class="loading-status">Processing image ${imageNumber}${totalImages > 1 ? ` of ${totalImages}` : ''}</div>
                <div class="loading-warning">
                    <i class="fas fa-exclamation-circle"></i>
                    Always double check! AI can be wrong.
                </div>
            </div>
        </div>
        <div class="alt-text-area">
            <div class="alt-text-editor"
                 contenteditable="true"
                 role="textbox"
                 aria-multiline="true"
                 aria-label="Image description"
                 placeholder="Image description (alt text)"></div>
        </div>
    `;

    return previewContainer;
}

// Update image handling
async function handleImageUpload(files) {
    // Check total number of images (existing + new)
    const totalImages = imageUploads.size + files.length;
    if (totalImages > 4) {
        showToast({
            type: 'error',
            message: 'Maximum 4 images allowed per post',
            duration: 3000
        });
        announceToScreenReader('Maximum 4 images allowed per post', true);
        return;
    }

    announceToScreenReader('Processing image upload, please wait...');
    
    try {
        for (const [index, file] of Array.from(files).entries()) {
            // Check file size (max 25MB)
            if (file.size > 25 * 1024 * 1024) {
                showToast({
                    type: 'error',
                    message: `File ${file.name} is too large. Maximum size is 25MB`,
                    duration: 3000
                });
                continue;
            }

            // Check file type
            if (!file.type.startsWith('image/')) {
                showToast({
                    type: 'error',
                    message: `File ${file.name} is not an image`,
                    duration: 3000
                });
                continue;
            }

            const imageId = `img-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            const imageNumber = imageUploads.size + 1;
            
            // Create and add preview container
            const previewContainer = createImagePreview(file, imageId, imageNumber, totalImages);
            document.getElementById('imageContainer').appendChild(previewContainer);
            
            // Get preview image and loading elements
            const previewImg = previewContainer.querySelector('.preview-image');
            const loadingOverlay = previewContainer.querySelector('.preview-loading');
            
            try {
                // Process the image
                const { blob, placeholder, srcSet } = await processImage(file);
                
                // Set the placeholder immediately
                previewImg.src = placeholder;
                
                // Store the processed file
                imageUploads.set(imageId, {
                    file: new File([blob], file.name, { type: blob.type }),
                    container: previewContainer,
                    altText: ''
                });

                // Set the srcset for responsive images
                previewImg.srcset = srcSet;
                previewImg.sizes = '(max-width: 400px) 100vw, 400px';
                
                // Generate alt text
                const altText = await window.altTextGenerator.generateAltText(file);
                
                // Update UI
                const altTextArea = previewContainer.querySelector('.alt-text-area');
                const editorEl = altTextArea.querySelector('.alt-text-editor');
                
                // Set alt text first
                editorEl.textContent = altText;
                imageUploads.get(imageId).altText = altText;
                
                // Make alt text area visible first
                altTextArea.classList.add('ready');
                
                // Then fade out and remove loading overlay
                loadingOverlay.classList.add('done');
                setTimeout(() => {
                    if (loadingOverlay && loadingOverlay.parentNode) {
                        loadingOverlay.parentNode.removeChild(loadingOverlay);
                    }
                }, 300);
                
                announceToScreenReader(`Generated description for image ${imageNumber}`);

                // Show success toast for each processed image
                showToast({
                    type: 'success',
                    message: `Image ${imageNumber} processed successfully`,
                    duration: 2000
                });
            } catch (error) {
                console.error('Error processing image:', error);
                handleImageError(previewContainer, error);
                showToast({
                    type: 'error',
                    message: `Error processing image ${imageNumber}: ${error.message}`,
                    duration: 3000
                });
            }
        }
        
        const successMessage = files.length === 1 
            ? 'Image processed successfully' 
            : `${files.length} images processed successfully`;
        announceToScreenReader(successMessage);

    } catch (error) {
        const errorMessage = 'Error uploading images: ' + error.message;
        announceToScreenReader(errorMessage, true);
        showToast({
            type: 'error',
            message: errorMessage,
            duration: 3000
        });
        console.error('Image upload failed:', error);
    }
}

// Handle image processing errors
function handleImageError(container, error) {
    const loadingOverlay = container.querySelector('.preview-loading');
    const altTextArea = container.querySelector('.alt-text-area');
    const editorEl = altTextArea.querySelector('.alt-text-editor');
    
    // Update loading status to show error
    const loadingStatus = loadingOverlay.querySelector('.loading-status');
    loadingStatus.textContent = 'Error processing image';
    loadingStatus.style.color = '#ef4444';
    
    // Set error message in editor
    editorEl.textContent = 'Error processing image. Please try again or enter a description manually.';
    
    // Make alt text area visible
    altTextArea.classList.add('ready');
    
    // Add error class to loading overlay
    loadingOverlay.classList.add('error');
    
    // Fade out and remove loading overlay after delay
    setTimeout(() => {
        loadingOverlay.classList.add('done');
        setTimeout(() => {
            if (loadingOverlay && loadingOverlay.parentNode) {
                loadingOverlay.parentNode.removeChild(loadingOverlay);
            }
        }, 300);
    }, 2000);
    
    announceToScreenReader('Error processing image. Please add description manually.');
}

// Post handling
function setupPostForm() {
    document.getElementById('newPostForm').addEventListener('submit', async (event) => {
        event.preventDefault();
        showPostPreview();
    });
}

function showPostPreview() {
    const postText = document.getElementById('postText').textContent;
    const previewText = document.getElementById('previewText');
    const previewImages = document.getElementById('previewImages');
    
    // Update preview user info
    document.getElementById('previewAvatar').src = document.getElementById('avatar').src;
    document.getElementById('previewDisplayName').textContent = document.getElementById('displayName').textContent;
    document.getElementById('previewHandle').textContent = document.getElementById('handleName').textContent;
    
    // Set preview text
    previewText.textContent = postText;
    
    // Clear and populate preview images
    previewImages.innerHTML = '';
    
    // Create Bluesky-style preview container
    const previewContainer = document.createElement('div');
    previewContainer.className = 'bsky-preview-container';
    
    // Add images in Bluesky grid style if there are any
    if (imageUploads.size > 0) {
        const imageGrid = document.createElement('div');
        imageGrid.className = `bsky-image-grid grid-${imageUploads.size}`;
        
        for (const [imageId, imageData] of imageUploads) {
            const imgWrapper = document.createElement('div');
            imgWrapper.className = 'image-wrapper';
            const img = imageData.container.querySelector('img');
            const altText = imageData.container.querySelector('.alt-text-editor').textContent;
            
            imgWrapper.innerHTML = `
                <img src="${img.src}" alt="${altText}" style="object-fit: cover;">
                <div class="alt-text-overlay" role="region" aria-label="Image description">
                    ${altText}
                </div>
            `;
            imageGrid.appendChild(imgWrapper);
        }
        previewContainer.appendChild(imageGrid);
    }
    
    previewImages.appendChild(previewContainer);
    
    // Show modal
    document.getElementById('postPreviewModal').classList.remove('hidden');
}

// Make closePreviewModal globally available
window.closePreviewModal = function() {
    document.getElementById('postPreviewModal').classList.add('hidden');
}

// Update confirmAndPost to handle image upload correctly
window.confirmAndPost = async function() {
    const submitButton = document.querySelector('#postPreviewModal .btn-primary');
    const originalButtonText = submitButton.textContent;
    
    try {
        submitButton.disabled = true;
        submitButton.innerHTML = `
            <span class="loading-spinner" role="status" aria-label="Posting..."></span>
            Posting...
        `;
        announceToScreenReader("Creating your post...");
        
        const images = [];
        
        for (const [imageId, imageData] of imageUploads) {
            try {
                // Process the image
                const { blob, aspectRatio, type } = await processImage(imageData.file);
                
                if (blob.size > 1000000) {
                    throw new Error('Image too large. Maximum size is 1MB.');
                }

                // Create form data for proper binary upload
                const formData = new FormData();
                formData.append('file', blob, 'image.jpg');

                // Upload to Bluesky with correct headers
                const uploadData = await fetch(API.BASE_URL + API.UPLOAD_BLOB, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${session.accessJwt}`,
                    },
                    body: blob
                }).then(r => r.json());
                
                images.push({
                    image: uploadData.blob,
                    alt: imageData.container.querySelector('.alt-text-editor').textContent,
                    aspectRatio
                });
            } catch (error) {
                console.error('Error processing image:', error);
                throw new Error(`Failed to process image: ${error.message}`);
            }
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
                        images
                    } : undefined
                }
            },
            { Authorization: `Bearer ${session.accessJwt}` }
        );

        // Close preview modal
        closePreviewModal();

        // Create post URL
        const postUri = postResponse.uri;
        const postRkey = postUri.split('/').pop();
        const postUrl = `https://bsky.app/profile/${session.handle}/post/${postRkey}`;
        
        showToast({
            type: 'success',
            message: 'Post published successfully!',
            link: {
                url: postUrl,
                text: 'View Post'
            },
            duration: 5000
        });

        clearPostForm();
        announceToScreenReader('Post published successfully. You can now view it on Bluesky.');

    } catch (error) {
        console.error('Failed to create post:', error);
        showToast({
            type: 'error',
            message: `Failed to create post: ${error.message}`,
            duration: 7000
        });
        announceToScreenReader(`Error creating post: ${error.message}`);
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = originalButtonText;
    }
};

// Toast notification system
function showToast({ type, message, link, duration = 5000 }) {
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'polite');

    const icon = type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle';
    
    toast.innerHTML = `
        <div class="toast-content">
            <i class="fas ${icon} toast-icon"></i>
            <p class="toast-message">${message}</p>
            ${link ? `
                <a href="${link.url}" 
                   target="_blank" 
                   rel="noopener noreferrer" 
                   class="toast-link">
                    ${link.text}
                    <i class="fas fa-external-link-alt"></i>
                </a>
            ` : ''}
        </div>
        <button class="toast-close" aria-label="Close notification">
            <i class="fas fa-times"></i>
        </button>
    `;

    // Add close button functionality
    toast.querySelector('.toast-close').addEventListener('click', () => {
        toast.classList.add('toast-hiding');
        setTimeout(() => toast.remove(), 300);
    });

    // Auto-dismiss
    if (duration) {
        setTimeout(() => {
            if (document.body.contains(toast)) {
                toast.classList.add('toast-hiding');
                setTimeout(() => toast.remove(), 300);
            }
        }, duration);
    }

    document.body.appendChild(toast);
    // Trigger entrance animation
    requestAnimationFrame(() => toast.classList.add('toast-visible'));
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
    
    if (!postText) return;

    postText.addEventListener('paste', async (e) => {
        // Get clipboard items
        const items = Array.from(e.clipboardData.items);
        const imageItems = items.filter(item => item.type.startsWith('image/'));
        
        if (imageItems.length > 0) {
            e.preventDefault(); // Prevent default paste for images
            
            // Check image limit
            if (imageItems.length + imageUploads.size > 4) {
                showToast({
                    type: 'error',
                    message: 'Maximum 4 images allowed per post',
                    duration: 3000
                });
                announceToScreenReader('Maximum 4 images allowed per post', true);
                return;
            }
            
            // Process each image
            for (const item of imageItems) {
                const file = item.getAsFile();
                if (file) {
                    await handleImageUpload([file]);
                }
            }

            showToast({
                type: 'success',
                message: `${imageItems.length} image${imageItems.length > 1 ? 's' : ''} pasted successfully`,
                duration: 2000
            });
        }
    });
}

function clearPostForm() {
    // Clear the post text
    const postText = document.getElementById('postText');
    if (postText) {
        postText.textContent = '';
    }

    // Clear file input
    const imageUpload = document.getElementById('imageUpload');
    if (imageUpload) {
        imageUpload.value = '';
    }

    // Clear image container and revoke object URLs
    const imageContainer = document.getElementById('imageContainer');
    if (imageContainer) {
        // Revoke all object URLs before clearing
        const images = imageContainer.querySelectorAll('img');
        images.forEach(img => {
            if (img.src.startsWith('blob:')) {
                URL.revokeObjectURL(img.src);
            }
        });
        imageContainer.innerHTML = '';
    }

    // Clear image uploads map
    if (imageUploads) {
        imageUploads.clear();
    }
}

// Pull to refresh functionality
function setupPullToRefresh() {
    if (!window.matchMedia('(display-mode: standalone)').matches) {
        return; // Only enable in standalone mode (PWA)
    }

    pullToRefreshEnabled = true;
    
    // Create PTR element if it doesn't exist
    if (!ptrElement) {
        ptrElement = document.createElement('div');
        ptrElement.className = 'ptr-element';
        ptrElement.innerHTML = `
            <div class="ptr-indicator">
                <div class="ptr-spinner"></div>
                <div class="ptr-text">Pull to refresh</div>
            </div>
        `;
        document.body.insertBefore(ptrElement, document.body.firstChild);
    }

    // Touch event handlers
    document.addEventListener('touchstart', onTouchStart, { passive: true });
    document.addEventListener('touchmove', onTouchMove, { passive: false });
    document.addEventListener('touchend', onTouchEnd, { passive: true });
}

function onTouchStart(e) {
    if (!pullToRefreshEnabled || refreshing || window.scrollY > 0) return;
    
    startY = e.touches[0].pageY;
    currentY = startY;
    pulling = true;
}

function onTouchMove(e) {
    if (!pulling) return;
    
    currentY = e.touches[0].pageY;
    const pullDistance = currentY - startY;
    
    if (pullDistance > 0) {
        e.preventDefault();
        const progress = Math.min(pullDistance / 100, 1);
        ptrElement.style.transform = `translate3d(0, ${pullDistance * 0.5}px, 0)`;
        
        // Update text based on pull distance
        const ptrText = ptrElement.querySelector('.ptr-text');
        if (progress >= 1) {
            ptrText.textContent = 'Release to refresh';
        } else {
            ptrText.textContent = 'Pull to refresh';
        }
    }
}

async function onTouchEnd() {
    if (!pulling) return;
    pulling = false;
    
    const pullDistance = currentY - startY;
    const progress = Math.min(pullDistance / 100, 1);
    
    if (progress >= 1) {
        // Start refresh
        refreshing = true;
        ptrElement.style.transform = 'translate3d(0, 30px, 0)';
        ptrElement.querySelector('.ptr-text').textContent = 'Refreshing...';
        
        try {
            await fetchProfile();
            showToast({
                type: 'success',
                message: 'Profile refreshed',
                duration: 2000
            });
        } catch (error) {
            showToast({
                type: 'error',
                message: 'Failed to refresh profile',
                duration: 2000
            });
        }
        
        // Reset after refresh
        setTimeout(() => {
            ptrElement.style.transform = 'translate3d(0, -100%, 0)';
            refreshing = false;
        }, 1000);
    } else {
        // Reset without refresh
        ptrElement.style.transform = 'translate3d(0, -100%, 0)';
    }
}

function setupImageHandling() {
    const imageUpload = document.getElementById('imageUpload');
    const dropzone = document.querySelector('.file-upload-dropzone');

    if (!imageUpload || !dropzone) return;

    // File input change handler
    imageUpload.addEventListener('change', (e) => {
        handleImageUpload(e.target.files);
    });

    // Drag and drop handlers
    dropzone.addEventListener('dragenter', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('drag-over');
    });

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add('drag-over');
    });

    dropzone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!dropzone.contains(e.relatedTarget)) {
            dropzone.classList.remove('drag-over');
        }
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove('drag-over');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleImageUpload(files);
        }
    });

    // Keyboard accessibility
    dropzone.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            imageUpload.click();
        }
    });

    // Click handler
    dropzone.addEventListener('click', () => {
        imageUpload.click();
    });

    // Prevent the default browser behavior for file drops
    document.addEventListener('dragover', (e) => e.preventDefault());
    document.addEventListener('drop', (e) => e.preventDefault());
}

// PWA Installation
let deferredPrompt;

function initializeInstallButton() {
    const installButton = document.getElementById('installButton');
    
    // Listen for the beforeinstallprompt event
    window.addEventListener('beforeinstallprompt', (e) => {
        // Prevent Chrome 67 and earlier from automatically showing the prompt
        e.preventDefault();
        // Stash the event so it can be triggered later
        deferredPrompt = e;
        // Show the install button
        if (installButton) {
            installButton.classList.remove('hidden');
            
            // Handle install button click
            installButton.addEventListener('click', async () => {
                // Hide the button
                installButton.classList.add('hidden');
                // Show the prompt
                deferredPrompt.prompt();
                // Wait for the user to respond to the prompt
                const { outcome } = await deferredPrompt.userChoice;
                // Clear the deferredPrompt
                deferredPrompt = null;
                
                announceToScreenReader(
                    outcome === 'accepted' 
                        ? 'Installing application...' 
                        : 'Installation cancelled'
                );
            });
        }
    });

    // Listen for successful installation
    window.addEventListener('appinstalled', () => {
        // Clear the deferredPrompt
        deferredPrompt = null;
        // Announce success
        announceToScreenReader('Application installed successfully');
        showToast({
            type: 'success',
            message: 'blueFlyer installed successfully!',
            duration: 3000
        });
    });
}

// Initialize function
async function initialize() {
    try {
        // Check for existing session
        const hasSession = await loadSession();
        
        // Setup event listeners and handlers
        setupImageHandling();
        setupPostForm();
        setupPasteHandling();
        setupPullToRefresh();
        
        // Add character counter for post text
        const postText = document.getElementById('postText');
        if (postText) {
            postText.addEventListener('input', updateCharCount);
            updateCharCount(); // Initial count
        }

        // Setup form submission
        const newPostForm = document.getElementById('newPostForm');
        if (newPostForm) {
            newPostForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                await createPost();
            });
        }

        // Initialize install button handler
        initializeInstallButton();

        if (!hasSession) {
            document.getElementById('loginForm').classList.remove('hidden');
            document.getElementById('userProfile').classList.add('hidden');
        }
    } catch (error) {
        console.error('Initialization error:', error);
        announceToScreenReader('There was an error initializing the application', true);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initialize);

function countCharacters(text) {
    // Count emojis as two characters
    const emojiRegex = /\p{Emoji}/gu;
    const emojiCount = (text.match(emojiRegex) || []).length;
    const totalLength = text.length + emojiCount;
    return totalLength;
}

function updateCharCount() {
    const postText = document.getElementById('postText');
    const charCount = document.getElementById('charCount');
    const text = postText.textContent;
    const totalLength = countCharacters(text);
    const remaining = 300 - totalLength;
    charCount.textContent = `${remaining}`;
    
    if (remaining < 0) {
        charCount.style.color = 'red';
        postText.textContent = text.slice(0, 300);
        showToast({
            type: 'error',
            message: 'Maximum character limit reached',
            duration: 2000
        });
    } else if (remaining <= 20) {
        charCount.style.color = 'orange';
        if (remaining === 20) {
            showToast({
                type: 'warning',
                message: 'Only 20 characters remaining',
                duration: 2000
            });
        }
    } else {
        charCount.style.color = '';
    }
}

// Add event listener to update character count
const postText = document.getElementById('postText');
postText.addEventListener('input', updateCharCount);

// Add keyboard navigation support
document.addEventListener('DOMContentLoaded', function() {
    // Handle keyboard navigation for file upload button
    const fileUploadLabel = document.querySelector('.file-upload-button');
    if (fileUploadLabel) {
        fileUploadLabel.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                document.getElementById('imageUpload').click();
            }
        });
    }

    // Handle keyboard navigation for contenteditable
    const postEditor = document.getElementById('postText');
    if (postEditor) {
        postEditor.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && e.ctrlKey) {
                e.preventDefault();
                document.querySelector('#newPostForm button[type="submit"]').click();
            }
        });
    }

    // Announce character count changes
    const charCount = document.getElementById('charCount');
    if (postEditor && charCount) {
        let lastCount = 300;
        postEditor.addEventListener('input', function() {
            const remaining = 300 - this.textContent.length;
            if (Math.floor(remaining / 50) !== Math.floor(lastCount / 50)) {
                announceToScreenReader(`${remaining}`);
            }
            lastCount = remaining;
        });
    }
});

// Add keyboard support for modal
function openPreviewModal() {
    const modal = document.getElementById('postPreviewModal');
    modal.classList.remove('hidden');
    announceToScreenReader('Post preview modal opened');
    
    // Focus the first focusable element
    const focusableElements = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (focusableElements.length) focusableElements[0].focus();
}

function closePreviewModal() {
    const modal = document.getElementById('postPreviewModal');
    modal.classList.add('hidden');
    announceToScreenReader('Post preview modal closed');
    
    // Return focus to the post button
    document.querySelector('#newPostForm button[type="submit"]').focus();
}

// Add modal keyboard trap
document.addEventListener('keydown', function(e) {
    const modal = document.getElementById('postPreviewModal');
    if (modal && !modal.classList.contains('hidden')) {
        if (e.key === 'Escape') {
            closePreviewModal();
            return;
        }
        
        if (e.key === 'Tab') {
            const focusableElements = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
            const firstElement = focusableElements[0];
            const lastElement = focusableElements[focusableElements.length - 1];
            
            if (e.shiftKey) {
                if (document.activeElement === firstElement) {
                    e.preventDefault();
                    lastElement.focus();
                }
            } else {
                if (document.activeElement === lastElement) {
                    e.preventDefault();
                    firstElement.focus();
                }
            }
        }
    }
}); 