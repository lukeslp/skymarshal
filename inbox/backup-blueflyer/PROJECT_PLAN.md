# Unified Accessible Bluesky Client Project Plan

## Bug Fixes

### 2024-02-21
- Fixed login endpoint reference in main.js
   - Issue: Login was failing with 404 error due to incorrect API endpoint reference.
   - Fix: Changed API.CREATE_SESSION to API.SESSION.
   - Impact: Login functionality restored.
   - Endpoint: POST https://bsky.social/xrpc/com.atproto.server.createSession 

- Added comprehensive debugging to alt.js
   - Issue: Alt text generation hanging indefinitely.
   - Changes: Detailed console logging through the image processing, API calls, and alt text generation.
   - Impact: Better tracking of failures.

- Improved stream handling in alt.js
   - Issue: Alt text generation hanging due to unhandled stream states.
   - Changes: Implemented a 30-second timeout, proper stream cleanup, and improved error propagation.
   - Impact: More reliable alt text generation.

- Enhanced loading UI for image processing
   - Changes: Step-by-step progress indicators, visual feedback for processing stages, improved error handling, and multi-image progress tracking.
   - Accessibility: ARIA labels for screen readers and clear error messaging.
   - Visuals: Semi-transparent overlay, spinner with step indicators, and color-coded success/error states.

## 1. Project Overview and Goals

The project is to build an accessible Bluesky client web application that integrates with the Bluesky API for user authentication, full profile display, a real-time updating feed, and robust post interactions (including threads, likes, reposts, etc.). A core focus is accessibility—ensuring keyboard navigation, adherence to ARIA guidelines, and support for alternative input methods—while also delivering a responsive, mobile-first design with progressive web app (PWA) capabilities.

## 2. Core Requirements

- **Authentication & User Data:** Integrate with the Bluesky API for secure login and display comprehensive user profiles.
- **Feed Implementation:** Provide a continuously updating feed with selectable filters and full post interactions.
- **Posting System:** Allow creation of rich text posts with media uploads, processed via backend-driven alt text generation and OCR as needed.
- **Notification System:** Deliver accessible real-time notifications with ARIA live region updates.

## 3. File Structure and Project Architecture

- **Backend:** Python + Flask application with API endpoints for authentication, profile data, image upload, alt text generation, and OCR processing.
- **Frontend:** Organized HTML, CSS, and JavaScript files managing the UI, including separate modules for sessions, posts, feeds, and error handling.
- **Workers:** Dedicated scripts for image compression and asynchronous alt text processing where applicable.

## 4. Backend Implementation (Python + Flask)

The backend leverages Flask along with endpoints defined in api_test.py to handle:
- User authentication and session management
- Profile retrieval
- Image uploads (via APITester.upload_to_coze)
- Alt text generation (via the external chat_with_image endpoint)
- OCR processing through multiple methods (URL, base64, or file upload)

## 5. Frontend Implementation (HTML, CSS, JavaScript)

- **HTML:** Employs semantic markup, ARIA roles, and skip links for enhanced accessibility.
- **CSS:** Uses responsive design, theming via CSS variables, and clear focus styles for interactable elements.
- **JavaScript:** Organized into modular components for session management, post submission, feed updates, and error handling.

## 6. Alt Text Generation, OCR Integration, and Image Processing

Image uploads trigger the following workflow:
1. **Image Upload:** Executed via APITester.upload_to_coze with the required endpoint and credentials.
2. **Alt Text Generation:** The uploaded image is processed with a call to the `chat_with_image` endpoint, streaming delta responses to form the final alt text.
3. **OCR Processing:** For text-heavy images, one of the OCR endpoints is called depending on the context (URL, base64, or file upload).
4. **Image Utilities:** Supplementary functions ensure images are correctly formatted and optimized before further processing.

## 7. Post Creation and Submission Workflow

Posts are created by collecting text and image data (with associated alt text/OCR output). The data is submitted to the backend for storage and distribution, with ARIA live region updates ensuring that users receive real-time feedback on processing status or errors.

## 8. Accessibility and Mobile Considerations

- **Core Accessibility:** ARIA labels and roles, semantic HTML, clear error messaging, and keyboard navigability.
- **Advanced Features:** Screen reader optimizations, live region announcements, and support for alternative input methods.
- **Mobile Optimization:** Touch-friendly UI elements, responsive design layouts, and performance optimizations for reduced load times.

## 9. Progressive Enhancements and Future Extensions

- **PWA Functionality:** Implementation of a manifest and service worker for offline support and caching.
- **Enhanced Interactions:** Future features include threaded conversations, media editing tools, and custom feed creation.
- **Continuous Improvement:** Ongoing updates to alt text/OCR models and user interface refinements based on user feedback.

## 10. Testing, Documentation, and Maintenance

- Comprehensive accessibility testing (e.g., screen readers, keyboard navigation).
- Regular performance reviews, dependency updates, and integration tests to ensure stability.
- Detailed user and technical documentation to facilitate onboarding and maintenance.

## 11. Implementation Phases

- **Phase 1:** Establish project setup, environment, and basic UI components with authentication.
- **Phase 2:** Integrate real-time feeds, post interactions, and backend-driven alt text generation.
- **Phase 3:** Enhance accessibility features, including ARIA live regions and improved keyboard navigation.
- **Phase 4:** Add PWA capabilities and advanced functionalities such as threaded posts and media editing tools.

## 12. Future Enhancements and Success Metrics

- **New Features:** Custom feed creation, advanced search, and in-browser media editing.
- **Success Metrics:** Achieve WCAG 2.1 Level AAA standards, optimal performance metrics (e.g., <2s initial load time), and positive user feedback.

## 13. Support Plan

- Provide thorough user documentation, troubleshooting guides, and clear onboarding instructions.
- Maintain a regular schedule for code reviews, dependency updates, and performance monitoring.

## 14. Conclusion

This unified project plan outlines a comprehensive approach to building an accessible Bluesky client that integrates robust backend API support, a user-centric accessible front-end, and forward-thinking progressive enhancements. Future updates will continue to be recorded as per the guidelines, ensuring the project evolves based on user needs and technological advancements.

<!-- Updated dropzone upload implementation -->

- Updated js/dropzone-config.js to replace the existing upload implementation with DropzoneJS.
  - Added a custom preview template that includes an alt text textarea.
  - Preserved the geometry and behavior to accommodate 1-4 images with previews as before for Bsky.

<!-- Style Updates for Dropzone Implementation -->
- Updated preview template and styles to match existing design:
  - Added sequence numbers for multiple images
  - Styled remove and retry buttons consistently with existing design
  - Preserved loading states and alt text editor appearance
  - Maintained existing hover effects and transitions 