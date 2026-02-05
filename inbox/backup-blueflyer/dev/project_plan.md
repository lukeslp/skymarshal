Below is the unified project plan document that combines all the ideas, details, and specifications from both plans without losing any content:

# Unified Accessible Bluesky Client Project Plan

This document outlines the comprehensive plan for building an accessible Bluesky client web application. The client will integrate with the Bluesky API to authenticate users, display full profile data, provide a continuously updating "firehose" feed, and support robust post interactions (threads, likes, reposts, etc.). A core focus is on accessibility—supporting keyboard navigation, ARIA guidelines, and alternative input methods (e.g., switch control and eye tracking)—while ensuring a responsive, mobile-first design and progressive web app (PWA) functionality.

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
6. [Alt Text Generation, OCR Integration, and Image Processing](#alt-text-generation-ocr-integration-and-image-processing)
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
- **Provides a "Firehose" Feed:** Offers a constantly updating feed (with selectable filters and feed sources via a dropdown) that displays posts from the user's subscribed channels.
- **Enables Full Post Interaction:** Supports viewing threads, reposting, liking, quoting posts, lightbox image viewing, and automatic detection of social cards for external links.
- **Integrates Alt Text & OCR Generation:** Automatically generates accessible descriptions for uploaded images using our API implementation. This includes both alt text generation and OCR processing for text-only images.
- **Delivers an Accessible Experience:** Meets web standards with semantic HTML, proper ARIA roles, keyboard navigability, and support for alternative input methods (switch control, eye tracking).
- **Optimizes for Mobile and Desktop:** Ensures responsive design, touch-friendly interactions, and progressive web app (PWA) features.
- **Supports Offline and Enhanced Interactions:** Prepares for offline drafts, PWA caching, and potential future enhancements such as advanced search and media editing.

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
- **Real-Time "Firehose" Feed:** Continuously update the feed with posts from selected sources.
- **Feed Selection & Filtering:** Allow users to choose from different feed types (e.g., Following, For You, My Content, Notifications) via a dropdown.
- **Post Interactions:** Enable thread viewing, likes, reposts, quote posts, and dynamic social card generation (for external links).
- **Image Lightbox:** Provide a lightbox view for images with keyboard and mouse accessibility.

### Posting System
- **Rich Text Post Creation:** Allow users to create posts with text and media.
- **Image Upload with Automated Processing:** Integrate an image upload flow that triggers both alt text generation and OCR processing as needed (see Section 6).
- **Thread Creation and Management:** Facilitate threaded conversations.
- **Offline Draft Support & Post Preview:** Allow users to save drafts and preview posts before submission.

### Notification System
- **Real-Time Notification Updates:** Display notifications in a dedicated, filterable feed.
- **Accessibility-Focused Display:** Ensure notifications are announced via ARIA live regions and fully navigable via keyboard.
- **Optional Sound and Haptic Feedback:** Provide additional cues where applicable.

---

## 3. File Structure and Project Architecture

To maintain a clean, scalable codebase, the project is organized with a clear separation between backend, frontend, and worker scripts for mobile optimization and asynchronous tasks.

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
│   │   │   ├── feed.js         # Retrieves feeds and implements live "firehose" updates
│   │   │   ├── profile.js      # Fetches and displays user profile information
│   │   │   └── api.js          # Utility functions for API calls and endpoint definitions
│   │   ├── utils/
│   │   │   ├── error.js        # Centralized error handling functions
│   │   │   └── accessibility.js# Functions for ARIA announcements, live region updates, and focus management
│   │   └── alt-text-generator.js # (Deprecated) Alt text generation logic now handled via API endpoints in the backend
│   └── README.md               # Frontend documentation and setup instructions
├── workers/
│   ├── imageCompression.js    # Web worker for image compression on mobile devices
│   └── altTextWorker.js       # Web worker for asynchronous alt text generation tasks (deprecated in favor of API implementation)
└── PROJECT_PLAN.md             # This comprehensive project plan document

---

## 4. Backend Implementation (Python + Flask)

### Setup and Dependencies
- **Environment:** Use a virtual environment.
- **Dependencies:** List required packages (Flask, flask-cors, requests, etc.) in `requirements.txt`.
- **Security:** Configure HTTPS and robust error messaging for production use.

### API Implementation
The backend now leverages the implementation provided in `api_test.py`. This file contains robust API calls including:

- **Image Upload:** `APITester.upload_to_coze(file_path)` strictly uses the defined endpoint and credentials to upload an image.
- **Alt Text Generation:** After a successful upload, alt text generation is triggered via the API endpoint (assumed to be implemented as `APITester.test_alt_text(file_id)`).
- **OCR Processing:** Three methods for OCR are provided:
  - `APITester.test_ocr_url(url)` for OCR using a URL.
  - `APITester.test_ocr_base64(image_path)` for OCR using a base64-encoded image.
  - `APITester.test_ocr_file(file_path)` for OCR via direct file upload.
- **Image Processing Utilities:** Functions like `create_test_image()` are maintained for image resizing, testing, and demonstration purposes.

A minimal Flask application example integrating these endpoints is as follows:

```python
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
# Import authentication, profile, and API functions

app = Flask(__name__, static_folder='../frontend')
CORS(app)  # Enable CORS for cross-origin requests

@app.route('/api/login', methods=['POST'])
def login():
    credentials = request.get_json()
    try:
        token = authenticate(credentials)  # Implement your authentication logic
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
```

---

## 5. Frontend Implementation (HTML, CSS, JavaScript)

### HTML – Semantic Markup & Accessibility
The main HTML file (index.html) employs semantic tags, ARIA roles, and skip links for keyboard users. Note that alt text generation is now handled entirely via the backend API; legacy client-side implementations have been removed.

Example excerpt from index.html:

```html
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
    <p>Open source tool with automatic alt text and OCR generation. No data is stored.</p>
  </footer>
  <script type="module" src="js/main.js"></script>
</body>
```

### CSS – Theming, Responsiveness & Accessibility
- **CSS Variables:** Ensure consistent theming (light/dark modes).
- **Responsive Layouts:** Use media queries for a mobile-first design.
- **Focus Styles:** Interactive elements include clear focus indicators.

## 5.1 Core Components Implementation

### 5.1.1 Enhanced Post Creator
```javascript
class PostCreator {
  constructor() {
    this.state = {
      text: '',
      images: new Map(),
      isProcessing: false
    };
    
    this.setupMobileUI();
    this.initializeEventListeners();
    this.setupAccessibility();
  }

  setupAccessibility() {
    // ARIA attributes and keyboard navigation
    this.element.setAttribute('role', 'form');
    this.element.setAttribute('aria-label', 'Create post');
    
    // Keyboard shortcuts
    this.registerKeyboardShortcuts();
    
    // Focus management
    this.setupFocusTrap();
  }
}
```

### 5.1.2 Alt Text Generation System
```javascript
class EnhancedAltTextGenerator {
  constructor() {
    this.model = null;
    this.isProcessing = false;
    this.queue = new Map();
  }

  async generateAltText(image, options = {}) {
    const {
      preferSpeed = false,
      enhanceDetail = true,
      accessibility = true
    } = options;

    // Generate initial quick description
    const quickAlt = await this.generateQuickAlt(image);
    
    // If enhanced detail requested, improve description
    if (enhanceDetail) {
      const enhancedAlt = await this.enhanceDescription(quickAlt);
      return this.formatAccessibleAlt(enhancedAlt);
    }
    
    return this.formatAccessibleAlt(quickAlt);
  }

  formatAccessibleAlt(altText) {
    return altText
      .replace(/([.!?])([^\s])/g, '$1 $2')
      .replace(/\s+/g, ' ')
      .trim();
  }
}
```

### 5.1.3 Mobile-Optimized Media Handler
```javascript
class MediaUploadManager {
  constructor() {
    this.maxSize = 5 * 1024 * 1024; // 5MB
    this.supportedTypes = ['image/jpeg', 'image/png', 'image/gif'];
    this.compressionWorker = new Worker('workers/imageCompression.js');
  }

  async handleUpload(files) {
    const optimizedImages = [];
    
    for (const file of files) {
      if (file.size > this.maxSize) {
        const compressed = await this.compressImage(file);
        optimizedImages.push(compressed);
      } else {
        optimizedImages.push(file);
      }
    }
    
    return optimizedImages;
  }
}
```

---

## 6. Alt Text Generation, OCR Integration, and Image Processing

Alt text generation is a central component of our accessibility strategy. In this implementation, **all image-to-text tasks use the API methods as defined in api_test.py**. This ensures consistency and maintainability across the project. The process consists of the following steps:

1. **Image Upload:**
   - Images are first uploaded using the method `APITester.upload_to_coze(file_path)`, which strictly follows the defined endpoint, authentication, and payload structure.

2. **Alt Text Generation:**
   - After a successful upload, the client invokes the external API by calling the `chat_with_image` endpoint. Specifically, the application calls:
     ```javascript
     const altText = await api.chatWithImage(fileId, "Please describe this image", "drummer");
     ```
     This endpoint streams a response composed of delta messages and a final complete message that is concatenated to form the final alt text. This replaces any previous local OCR or pytesseract-based methods.

3. **OCR Processing for Text-Only Images:**
   - For images containing primarily text, OCR is applied using one of three endpoints based on context:
     - `APITester.test_ocr_url(url)` for OCR using a URL.
     - `APITester.test_ocr_base64(image_path)` for OCR using a base64 string.
     - `APITester.test_ocr_file(file_path)` for OCR via direct file upload.

4. **Image Processing Utilities:**
   - Additional functions such as `create_test_image()` remain available to generate test images, resize images, or perform other pre-processing tasks as needed. These utilities ensure that images are correctly formatted and optimized before further processing or display.

**Note:** This API-driven approach replaces any prior or alternative client-side implementations for alt text or OCR generation. It guarantees that the implementation is identical to the one in api_test.py, ensuring flawless consistency and function.

---

## 7. Post Creation and Submission Workflow

When submitting a post, the app collects the text content along with any uploaded images (and their alt text/OCR data) and sends a post record to the backend. The workflow is as follows:

- **Image Processing:** Uploaded images are handled using the API endpoints described in Section 6.
- **Post Record Submission:** The post data—consisting of text and processed image data—is sent to the backend API for storage and further distribution.
- **Feedback Mechanisms:** The user receives real-time status updates (via ARIA live regions) on both successful submissions and any errors encountered.

---

## 8. Accessibility and Mobile Considerations

Accessibility is a core requirement. The design and implementation will ensure:

### Core Accessibility Features
- **ARIA Labels & Roles:** All interactive elements include descriptive ARIA labels and appropriate roles.
- **Semantic HTML:** Use of HTML5 elements (e.g., <header>, <main>, <footer>) combined with skip links for improved keyboard navigation.
- **Error Messaging:** Clear error messages are communicated via ARIA live regions.

### Advanced Accessibility Features
- **Keyboard Navigation and Shortcuts:** Implement comprehensive keyboard navigability and shortcuts (e.g., via a dedicated KeyboardManager module).
- **Screen Reader Optimization:** Dynamic content updates are announced using ARIA live regions.
- **Alternative Input Methods:** Support for switch control and eye tracking is provided to accommodate a wide range of user interfaces.

### Mobile Optimization
- **Touch Interface Adjustments:** Buttons and interactive elements are optimized for touch (minimum size guidelines, spacing).
- **Responsive Design:** Media queries ensure that the layout adapts to various screen sizes.
- **Performance Considerations:** Lazy loading and mobile-specific optimizations are implemented to reduce load times.

---

## 9. Progressive Enhancements and Future Extensions

- **PWA Support:** Implement a manifest.json and a service worker for offline capabilities and caching.
- **Advanced Post Interactions:** Additional features like threaded conversations, reposting, and advanced media editing may be added in subsequent iterations.
- **Enhanced Search and Custom Feeds:** Future enhancements may include advanced search functionality and custom feed creation.
- **Testing and Feedback:** Implement continuous integration tests, accessibility audits, and gather user feedback for ongoing improvements.

---

## 10. Testing, Documentation, and Maintenance

### Testing Strategy
- **Accessibility Testing:** Conduct tests with screen readers (e.g., NVDA, VoiceOver) and keyboard-only navigation.
- **Mobile Responsiveness:** Verify touch target sizes and layout adaptiveness across device types.
- **Functionality Testing:** Test API interactions, media upload processes, and the full image-to-text pipeline (including OCR and alt text generation).

### Documentation
- **User Documentation:** Provide clear setup instructions, usage guides, and troubleshooting steps.
- **Technical Documentation:** Maintain API documentation, detailed code comments, and changelogs for each module.

### Maintenance Plan
- **Regular Updates:** Schedule weekly dependency updates and monthly accessibility audits.
- **Performance Monitoring:** Deploy analytics to continuously monitor performance and error rates.

---

## 11. Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
- Project setup and environment configuration.
- Basic authentication and core API integration using the provided implementations in api_test.py.
- Establish fundamental UI components.

### Phase 2: Core Features (Weeks 3-4)
- Implement real-time feed updates and post interactions.
- Integrate the alt text generation and OCR endpoints for image processing.
- Develop user profile display and session management.

### Phase 3: Accessibility (Weeks 5-6)
- Implement ARIA roles, keyboard navigation, and live region updates.
- Optimize for screen reader support and alternative input methods.
- Enhance mobile and touch-friendly interactions.

### Phase 4: Mobile & Enhancements (Weeks 7-8)
- Add PWA functionality, offline support, and advanced performance optimizations.
- Integrate additional features such as threaded posts and media editing tools.

---

## 12. Future Enhancements and Success Metrics

### Future Enhancements
- **Custom Feed Creation and Advanced Search:** Empower users to create personalized feeds and provide robust search functionality.
- **Enhanced Media Editing:** Introduce tools for in-browser image editing and draft management.
- **Improved Alt Text & OCR Models:** Update the AI models as advancements in image-to-text processing arise.

### Success Metrics
- **Accessibility Compliance:** Achieve WCAG 2.1 Level AAA standards and perfect Lighthouse accessibility scores.
- **Performance Metrics:** Maintain an initial load time of under 2s and interaction response times below 100ms.
- **User Satisfaction:** Garner positive feedback as measured by accessibility audits, user surveys, and consistent low error rates.

---

## 13. Support Plan

### User Support
- **Documentation:** Provide detailed installation guides, accessibility references, and troubleshooting documents.
- **Issue Tracking:** Utilize a version-controlled bug tracker for timely updates and fixes.

### Technical Support
- **Maintenance:** Schedule regular code reviews, dependency updates, and security audits.
- **Feedback Integration:** Implement continuous user feedback loops for feature enhancements and bug resolution.

---

## 14. Conclusion

By adhering to this unified project plan, we will build a robust and accessible Bluesky client that leverages the proven API implementations from api_test.py for all image-to-text requirements. This includes automatic alt text generation, OCR processing, and essential image processing utilities, ensuring that our application is both highly functional and fully accessible. As we iterate on features and gather feedback, this document will evolve to reflect new requirements and improvements.

Happy coding!

---

You can now use this unified document as your working project plan. Feel free to modify or extend any section as new requirements emerge during development.