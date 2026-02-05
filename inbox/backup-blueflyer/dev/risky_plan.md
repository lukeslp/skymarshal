Below is the updated unified project plan. In the Alt Text Generation and Image Upload Flow section, we now replace the previous local/pytesseract–based implementation with the EXACT API-based method from your provided @api_test.py code. This means that all image–to–text tasks (including alt text generation) will now use the Coze file upload endpoint along with the chat_with_image endpoint (defaulting to the “drummer” endpoint) to generate image descriptions.

# Unified Accessible Bluesky Client Project Plan

This document outlines the comprehensive plan for building an accessible Bluesky client web application. The client will integrate with the Bluesky API to authenticate users, display full profile data, provide a continuously updating “firehose” feed, and support robust post interactions (threads, likes, reposts, etc.). A core focus is on accessibility—supporting keyboard navigation, ARIA guidelines, and alternative input methods (switch control, eye tracking)—while ensuring a responsive, mobile-first design and progressive web app (PWA) functionality.

> **Important Update:**  
> All alt text generation and image–text tasks will now use the provided API implementation (see `@api_test.py`). In particular, when generating alt text, the application will:
> 1. Upload the image using the Coze API endpoint (`https://api.coze.com/v1/files/upload`) with the provided credentials.
> 2. Call the `chat_with_image` endpoint on the base URL `https://actuallyusefulai.com/api/v1/prod` (defaulting to the "drummer" endpoint) with the message “Please describe this image.”
> 3. Process the streaming response to build the final alt text.
>
> Any previous alt text generation code (including local OCR/Tesseract-based methods) is to be completely replaced by this API-driven implementation.

---

## Table of Contents

1. [Project Overview and Goals](#project-overview-and-goals)
2. [Core Requirements](#core-requirements)
   - [Authentication & User Data](#authentication--user-data)
   - [Feed Implementation](#feed-implementation)
   - [Posting System](#posting-system)
   - [Notification System](#notification-system)
3. [File Structure and Project Architecture](#file-structure-and-project-architecture)
4. [Backend Implementation (Python + Flask)](#backend-implementation-python--flask)
5. [Frontend Implementation (HTML, CSS, JavaScript)](#frontend-implementation-html-css-javascript)
6. [Alt Text Generation and Image Upload Flow](#alt-text-generation-and-image-upload-flow)
7. [Post Creation and Submission Workflow](#post-creation-and-submission-workflow)
8. [Accessibility and Mobile Considerations](#accessibility-and-mobile-considerations)
   - [Core Accessibility Features](#core-accessibility-features)
   - [Advanced Accessibility Features](#advanced-accessibility-features)
   - [Mobile Optimization](#mobile-optimization)
9. [Progressive Enhancements and Future Extensions](#progressive-enhancements-and-future-extensions)
10. [Testing, Documentation, and Maintenance](#testing-documentation-and-maintenance)
11. [Implementation Phases](#implementation-phases)
12. [Future Enhancements and Success Metrics](#future-enhancements-and-success-metrics)
13. [Support Plan](#support-plan)
14. [Conclusion](#conclusion)

---

## 1. Project Overview and Goals

The goal is to build an accessible, fully featured Bluesky client web app that:

- **Authenticates Users:** Integrates with the Bluesky API for login and session management.
- **Displays Comprehensive User Information:** Shows profile picture, join date, post count, follower/following counts, bio, and any other data available.
- **Provides a “Firehose” Feed:** Offers a continuously updating feed (with selectable filters via a dropdown) that displays posts from the user’s subscribed channels.
- **Enables Full Post Interaction:** Supports viewing threads, reposting, liking, quoting posts, lightbox image viewing, and dynamic social card generation (for external links).
- **Integrates Alt Text Generation:** **[Updated]** Uses an external API (via Coze upload and chat endpoints) to generate descriptive alt text for images.
- **Delivers an Accessible Experience:** Meets web standards with semantic HTML, proper ARIA roles, keyboard navigability, and support for alternative input methods (switch control, eye tracking).
- **Optimizes for Mobile and Desktop:** Ensures responsive design, touch-friendly interactions, and PWA features.
- **Supports Offline and Enhanced Interactions:** Prepares for offline drafts, caching, and potential future enhancements such as advanced search and media editing.

---

## 2. Core Requirements

### Authentication & User Data
- **Bluesky API Integration:** Users log in using their Bluesky credentials.
- **Full Profile Display:** Retrieve and present all available profile data:
  - Profile picture
  - Join date
  - Post count
  - Follower/Following counts
  - Bio (with rich text support)
  - Any additional data provided by the API

### Feed Implementation
- **Real-Time “Firehose” Feed:** Continuously update the feed with posts from selected sources.
- **Feed Selection & Filtering:** Allow users to choose from different feed types (e.g., Following, For You, My Content, Notifications) via a dropdown.
- **Post Interactions:** Enable thread viewing, likes, reposts, quote posts, and dynamic social card generation.
- **Image Lightbox:** Provide a lightbox view for images with keyboard and mouse accessibility.

### Posting System
- **Rich Text Post Creation:** Allow users to create posts with text and media.
- **Image Upload with Alt Text Generation:**  
  **[Updated]** Upon image upload, the client:
  1. Uploads the image using the Coze API.
  2. Calls the chat endpoint with the message “Please describe this image” to generate alt text.
  3. Displays the generated alt text (with manual override if necessary).
- **Thread Creation and Management:** Facilitate threaded conversations.
- **Offline Draft Support & Post Preview:** Allow users to save drafts and preview posts before submission.

### Notification System
- **Real-Time Notification Updates:** Display notifications in a dedicated, filterable feed.
- **Accessibility-Focused Display:** Ensure that notifications are announced via ARIA live regions and are fully navigable via keyboard.
- **Optional Sound and Haptic Feedback:** Provide additional cues where applicable.

---

## 3. File Structure and Project Architecture

The project is organized with a clear separation between backend, frontend, and worker scripts for mobile optimization and asynchronous tasks.

bluesky-client/
├── assets/
│   ├── icons/
│   └── images/
├── backend/
│   ├── app.py                  # Flask application serving API proxy endpoints
│   ├── bluefame.py             # Module with Bluesky API interactions (authentication, profile, feed, etc.)
│   ├── requirements.txt        # Python dependencies (Flask, flask-cors, requests, etc.)
│   └── README.md               # Backend-specific documentation
├── frontend/
│   ├── index.html              # Main HTML file with semantic markup and accessibility features
│   ├── upload.html             # Page for post creation and media upload
│   ├── manifest.json           # Web App Manifest for PWA support
│   ├── css/
│   │   ├── styles.css          # Aggregated stylesheet using CSS variables, responsive design, and theming
│   │   └── components/         # Component-level styles (buttons, modals, feeds, etc.)
│   ├── js/
│   │   ├── main.js             # App initialization and event listeners
│   │   ├── config/
│   │   │   └── elements.js     # DOM element references
│   │   ├── handlers/
│   │   │   └── eventListeners.js  # Bindings for DOM events
│   │   ├── services/
│   │   │   ├── session.js      # Session management (login, logout, token storage)
│   │   │   ├── post.js         # Handles image upload, alt text generation, and post submission
│   │   │   ├── image.js        # Image handling (wrapping images with alt text buttons, modals)
│   │   │   ├── feed.js         # Retrieves feeds and implements live “firehose” updates
│   │   │   ├── profile.js      # Fetches and displays user profile information
│   │   │   ├── api.js          # Utility functions for API calls and endpoint definitions
│   │   │   └── altTextGenerator.js  # [Updated] New module wrapping the external API alt text generation method
│   │   ├── utils/
│   │   │   ├── error.js        # Centralized error handling functions
│   │   │   └── accessibility.js# Functions for ARIA announcements, live region updates, and focus management
│   └── README.md               # Frontend documentation and setup instructions
├── workers/
│   ├── imageCompression.js    # Web worker for image compression on mobile devices
│   └── altTextWorker.js       # Web worker for asynchronous alt text generation tasks (if needed)
└── PROJECT_PLAN.md             # This comprehensive project plan document

---

## 4. Backend Implementation (Python + Flask)

### Setup and Dependencies
- **Environment:** Use a virtual environment.
- **Dependencies:** List required packages (Flask, flask-cors, requests, etc.) in `requirements.txt`.
- **Security:** Configure HTTPS and robust error messaging for production use.

### Flask Application Overview

The backend serves as a secure proxy to the Bluesky API for:
- **Authentication:** Accepting login credentials and returning an access token.
- **Profile Data:** Fetching detailed user profile information.
- **Feed Retrieval:** Proxying real-time feed updates.
- **Post Creation:** Handling post submissions (including image uploads and alt text data).

*Example snippet (from `app.py`):*

```python
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
# Import authentication and profile functions from bluefame.py

app = Flask(__name__, static_folder='../frontend')
CORS(app)  # Enable CORS for cross-origin requests

@app.route('/api/login', methods=['POST'])
def login():
    credentials = request.get_json()
    try:
        token = authenticate(credentials)
        return jsonify({"accessToken": token})
    except Exception as e:
        return jsonify({"error": str(e)}), 401

@app.route('/api/profile', methods=['GET'])
def profile():
    try:
        token = request.headers.get("Authorization")
        profile_data = get_profile(token)
        return jsonify(profile_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(debug=True)

5. Frontend Implementation (HTML, CSS, JavaScript)

HTML – Semantic Markup & Accessibility

The main HTML file (index.html) employs semantic tags, ARIA roles, and skip links for keyboard users.

Excerpt from index.html:

<body>
  <a href="#main-content" class="skip-link">Skip to main content</a>
  <header role="banner" class="site-header container">
    <h1 class="site-title">blueFlyer</h1>
    <p class="site-subtitle">Accessible Media Poster</p>
  </header>
  <main id="main-content">
    <!-- Login Form -->
    <form id="loginForm" class="form-group" role="form" aria-labelledby="login-title">
      <h2 id="login-title" class="visually-hidden">Log in</h2>
      <label for="handle">Handle:</label>
      <input type="text" id="handle" class="form-input" placeholder="you.bsky.social" required aria-label="Bluesky handle">
      <label for="password">Password:</label>
      <input type="password" id="password" class="form-input" placeholder="Your App Password" required aria-label="App password">
      <button type="button" class="btn btn-primary" aria-label="Log in to Bluesky">Login</button>
    </form>

    <!-- User Profile & Feed -->
    <div id="userProfile" class="hidden">
      <section class="profile-section" aria-label="User profile">
        <!-- Dynamically populated user profile content -->
      </section>
      <section class="feed-container" aria-label="User feed">
        <select id="feedSelector" class="feed-selector" aria-label="Select feed type">
          <option value="following">Following</option>
          <option value="algorithm">For You</option>
          <option value="my-content">My Content</option>
          <option value="notifications">Notifications</option>
        </select>
        <div id="feed" class="feed"></div>
      </section>
    </div>
  </main>
  <footer role="contentinfo" class="site-footer container">
    <p>Open source tool with automatic alt text generation. No data is stored.</p>
  </footer>
  <script type="module" src="js/main.js"></script>
</body>

CSS – Theming, Responsiveness & Accessibility
	•	CSS Variables: For consistent theming (light/dark modes).
	•	Responsive Layouts: Use media queries for mobile-first design.
	•	Focus Styles: Ensure interactive elements have clear focus indicators.

JavaScript – Modular and Accessible Interactions
	•	Modular Structure: Organized into modules (session, profile, feed, post, image, alt text generation).
	•	Modern Syntax: ES6+ with robust error handling.
	•	ARIA Live Regions: Announce dynamic updates (see accessibility.js).

Example snippet from frontend/js/services/session.js:

export async function login(handle, password) {
  try {
    const response = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ handle, password })
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Login failed');
    }
    localStorage.setItem('accessToken', data.accessToken);
    return data;
  } catch (error) {
    console.error('Login Error:', error);
    throw error;
  }
}

6. Alt Text Generation and Image Upload Flow

[Updated Implementation Using External API]

When a user uploads an image, the alt text generation process will now follow these steps:
	1.	Image Upload:
The client uploads the image using the Coze API endpoint:
POST https://api.coze.com/v1/files/upload
with the proper credentials (e.g., the provided coze_token). Upon success, the API returns a file_id.
	2.	Alt Text Generation:
With the returned file_id, the client calls the chat endpoint on:
https://actuallyusefulai.com/api/v1/prod/chat/drummer
(or other endpoints as needed) passing in the payload:

{
  "message": "Please describe this image",
  "file_id": "<returned_file_id>",
  "user_id": "test_user"
}

The API streams a response which includes:
	•	Delta messages: Containing partial text.
	•	Complete message: Finalizing the generated alt text.

	3.	Response Handling:
The client assembles the streaming response (concatenating text from each delta message) until a complete message is received. This final text is then used as the alt text for the image.
	4.	Error Handling:
If any step fails (upload or chat call), the system logs the error and prompts the user to manually enter alt text.

Pseudocode for integration in altTextGenerator.js:

export async function generateAltText(file) {
  // Step 1: Upload the image using the Coze API
  const uploadResponse = await api.uploadToCoze(file);
  if (!uploadResponse.success) {
    throw new Error("Image upload failed: " + uploadResponse.error);
  }
  const fileId = uploadResponse.file_id;

  // Step 2: Call chat_with_image endpoint to generate alt text
  // Here we use the "drummer" endpoint by default.
  const altText = await api.chatWithImage(fileId, "Please describe this image", "drummer");
  return altText;
}

Note:
	•	The external API code (as provided in @api_test.py) includes detailed handling of streaming responses and logging.
	•	All previous local implementations (e.g., using pytesseract) are removed in favor of this unified method.

7. Post Creation and Submission Workflow

When submitting a post, the client collects text and any uploaded images (with their generated alt text) and sends the post record to the backend. With the updated alt text generation, the image processing now follows the above flow.

Example snippet from frontend/js/services/post.js:

export async function handlePostSubmit(event) {
  event.preventDefault();
  try {
      const session = getSession();
      const images = [];

      // Process each uploaded image
      for (const [imageId, imageData] of imageUploads) {
          // Convert image preview URL to blob
          const blob = await fetch(imageData.container.querySelector('img').src).then(r => r.blob());
          // Upload image and generate alt text using the new API method
          const uploadResponse = await api.uploadToCoze(blob);
          if (!uploadResponse.success) {
              throw new Error("Image upload failed for " + imageData.file.name);
          }
          const fileId = uploadResponse.file_id;
          const altText = await api.chatWithImage(fileId, "Please describe this image", "drummer");
          images.push({
              image: uploadResponse.blob,  // or other identifier returned by the upload
              alt: altText
          });
      }

      // Submit the post record with text and embedded images if any
      await api.post(
          API.CREATE_RECORD,
          {
              repo: session.did,
              collection: 'app.bsky.feed.post',
              record: {
                  text: elements.postText.value,
                  createdAt: new Date().toISOString(),
                  embed: images.length ? {
                      $type: 'app.bsky.embed.images',
                      images: images
                  } : undefined
              }
          },
          { Authorization: `Bearer ${session.accessJwt}` }
      );
      clearPostForm();
      elements.createPostModal.classList.add('hidden');
      announcePostSuccess();
  } catch (error) {
      handleError(error, 'Failed to create post');
  }
}

8. Accessibility and Mobile Considerations

Core Accessibility Features
	•	ARIA Labels & Roles: All interactive elements include descriptive ARIA labels and proper roles.
	•	Semantic HTML: Use <header>, <main>, <footer>, and skip links for improved keyboard navigation.
	•	Error Handling: Clear error messages are announced via ARIA live regions.

Advanced Accessibility Features
	•	Keyboard Navigation and Shortcuts:

const KeyboardManager = {
  shortcuts: new Map([
    ['n', 'New post'],
    ['j', 'Next item'],
    ['k', 'Previous item'],
    ['/', 'Search'],
    ['?', 'Show keyboard shortcuts']
  ]),
  initialize() {
    document.addEventListener('keydown', this.handleKeyPress.bind(this));
    this.createShortcutsModal();
  }
};


	•	Screen Reader Optimization:

const ScreenReaderAnnouncer = {
  announce(message, priority = 'polite') {
    const announcement = document.createElement('div');
    announcement.setAttribute('role', 'status');
    announcement.setAttribute('aria-live', priority);
    announcement.classList.add('sr-only');
    announcement.textContent = message;
    
    document.body.appendChild(announcement);
    setTimeout(() => announcement.remove(), 3000);
  }
};


	•	Switch Control & Eye Tracking Support:
(See code examples for managing focus and scanning intervals.)

Mobile Optimization
	•	Touch Interface: Ensure interactive elements have a minimum size (e.g., 44px) and adequate spacing.
	•	Responsive Design: Use mobile-first CSS media queries for optimal display.
	•	Performance & Lazy Loading: Implement lazy loading for images and asynchronous resource fetching.

9. Progressive Enhancements and Future Extensions
	•	PWA Support:
	•	Include a manifest.json and implement a service worker for caching/offline use.
	•	Interactive Extensions:
	•	Advanced thread interactions, reposting, and likes.
	•	Enhanced media editing and draft saving.
	•	Custom feed creation and advanced search capabilities.
	•	Codebase Organization:
	•	Consider frameworks (e.g., Vue.js) for improved state management as features grow.
	•	Implement unit and integration tests for all components.

10. Testing, Documentation, and Maintenance

Testing Strategy
	•	Accessibility Testing:
	•	Screen reader tests (NVDA, VoiceOver, TalkBack)
	•	Keyboard navigation and switch control tests
	•	Color contrast and font scaling checks
	•	Mobile Testing:
	•	Verify touch target sizes and responsive layouts on various devices.
	•	Performance testing across devices.
	•	Functional Testing:
	•	API integration tests (including alt text generation via the new API).
	•	Media upload and post submission tests.
	•	Offline functionality and PWA behavior tests.

Documentation Requirements
	•	User Documentation:
	•	Installation and usage guides.
	•	Accessibility features and keyboard shortcuts reference.
	•	Technical Documentation:
	•	API and component documentation.
	•	Detailed accessibility and alt text generation implementation notes.

Maintenance Plan
	•	Regular Updates:
	•	Weekly dependency and security updates.
	•	Quarterly accessibility and performance reviews.
	•	Monitoring:
	•	Performance analytics and error tracking.
	•	Continuous user feedback collection.

11. Implementation Phases

Phase 1: Foundation (Weeks 1-2)
	•	Project setup and environment configuration.
	•	Basic authentication and core API integration.
	•	Establish fundamental UI components.

Phase 2: Core Features (Weeks 3-4)
	•	Implement live “firehose” feed.
	•	Develop post creation and media upload with new alt text generation.
	•	Build profile display and session management.

Phase 3: Accessibility (Weeks 5-6)
	•	Integrate ARIA roles, keyboard navigation, and live region updates.
	•	Add screen reader, switch control, and eye tracking support.
	•	Optimize mobile and touch-friendly interactions.

Phase 4: Mobile & Enhancements (Weeks 7-8)
	•	Implement PWA features and offline support.
	•	Perform performance optimizations and add advanced accessibility features.
	•	Integrate additional interactive elements (threading, notifications).

12. Future Enhancements and Success Metrics

Future Enhancements
	•	Custom feed creation and advanced search functionality.
	•	Enhanced media editing and draft management.
	•	Improved alt text generation models and additional input method support.

Success Metrics
	•	Accessibility Compliance:
	•	WCAG 2.1 Level AAA adherence.
	•	Perfect Lighthouse accessibility scores.
	•	Performance Metrics:
	•	< 2s initial load time.
	•	< 100ms interaction response time.
	•	90+ Lighthouse performance score.
	•	User Satisfaction:
	•	Positive feedback from accessibility audits and user surveys.
	•	Low error rates and high usage metrics.

13. Support Plan

User Support
	•	Comprehensive documentation and troubleshooting guides.
	•	Issue tracking and regular updates based on user feedback.

Technical Support
	•	Ongoing code maintenance and bug fixes.
	•	Regular security audits and performance optimizations.

14. Conclusion

By following this unified project plan, we will build a robust, accessible Bluesky client that prioritizes both functionality and user accessibility. With the updated alt text generation method—using the Coze file upload and chat_with_image endpoints—the system will deliver high-quality, AI-generated image descriptions reliably. This document is a living guide that will evolve as we iterate on features, gather feedback, and implement further enhancements.

Happy coding!

---

This updated plan now reflects the EXACT API method for alt text generation (and any image–text tasks) as specified in your `@api_test.py` file. If any further clarification on specific functions is needed, please let me know.