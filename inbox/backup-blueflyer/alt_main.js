// Alt Text Generator Configuration
const ALT_TEXT_CONFIG = {
    model: "coolhand/altllama:13b",
    systemPrompt: `You're an Alt Text Specialist, dedicated to creating precise and accessible alt text for digital images, especially memes. Your primary goal is to ensure visually impaired individuals can engage with imagery by providing concise, accurate, and ethically-minded descriptions.

Create Alt Text:
- Depict essential visuals and visible text accurately.
- Avoid adding social-emotional context or narrative interpretations unless specifically requested.
- Refrain from speculating on artists' intentions.
- Avoid prepending with "Alt text:" for direct usability.
- Maintain clarity and consistency for all descriptions, including direct image links.
- Character limit: All descriptions must be under 1000 characters.

DO NOT add any commentary or other text before or after the alt text. Output ONLY the alt text description.`,
    userPrompt: `Describe this image with precise, factual details about the visual elements and any visible text. Focus on:
1. Main subjects and their arrangement
2. Important visual details that affect meaning
3. Any text present in the image, quoted exactly
4. Relevant context clues (like platform UI elements for screenshots)
5. Meme template identification if applicable

Avoid:
- Emotional interpretation
- Speculation about intent
- Commentary outside the visual elements
- Prepending "Alt text:" or similar markers

Provide ONLY the description, no additional text.`
};

// Image Processing Configuration
const IMAGE_CONFIG = {
    maxWidth: 2048,
    maxHeight: 2048,
    maxFileSize: 975000, // ~975KB to leave room for overhead
    quality: 0.85,
    fallbackQuality: 0.7,
    format: 'image/jpeg'
};

// Alt Text Generator Class
class AltTextGenerator {
    constructor() {
        this.currentModel = ALT_TEXT_CONFIG.model;
        this.maxRetries = 2;
        console.log('AltTextGenerator initialized with model:', this.currentModel);
    }

    async resizeImage(input, maxDimension = IMAGE_CONFIG.maxWidth) {
        console.log('Starting image resize process...', { maxDimension });
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            
            img.onload = async () => {
                console.log('Image loaded with dimensions:', { width: img.width, height: img.height });
                try {
                    // Create canvas with original dimensions first
                    const canvas = document.createElement('canvas');
                    let width = img.width;
                    let height = img.height;
                    
                    // Calculate dimensions while maintaining aspect ratio
                    if (width > height && width > maxDimension) {
                        height = Math.round((height * maxDimension) / width);
                        width = maxDimension;
                    } else if (height > maxDimension) {
                        width = Math.round((width * maxDimension) / height);
                        height = maxDimension;
                    }

                    console.log('Calculated dimensions:', { width, height });

                    // Set canvas dimensions
                    canvas.width = width;
                    canvas.height = height;
                    
                    // Get context with alpha enabled
                    const ctx = canvas.getContext('2d');
                    
                    // Clear canvas and set white background
                    ctx.clearRect(0, 0, width, height);
                    ctx.fillStyle = '#FFFFFF';
                    ctx.fillRect(0, 0, width, height);
                    
                    // Draw image with proper smoothing
                    ctx.imageSmoothingEnabled = true;
                    ctx.imageSmoothingQuality = 'high';
                    ctx.drawImage(img, 0, 0, width, height);

                    // Convert to blob with initial quality
                    let blob = await new Promise(resolve => {
                        canvas.toBlob(resolve, 'image/jpeg', IMAGE_CONFIG.quality);
                    });

                    console.log('Initial blob size:', blob.size);

                    // If file is too large, try with lower quality
                    if (blob.size > IMAGE_CONFIG.maxFileSize) {
                        console.log('Image too large, reducing quality...');
                        blob = await new Promise(resolve => {
                            canvas.toBlob(resolve, 'image/jpeg', IMAGE_CONFIG.fallbackQuality);
                        });

                        // If still too large, scale down dimensions
                        if (blob.size > IMAGE_CONFIG.maxFileSize) {
                            console.log('Still too large, scaling down dimensions...');
                            const scale = Math.sqrt(IMAGE_CONFIG.maxFileSize / blob.size);
                            width = Math.round(width * scale);
                            height = Math.round(height * scale);

                            console.log('New scaled dimensions:', { width, height });

                            canvas.width = width;
                            canvas.height = height;

                            // Clear and set white background again
                            ctx.clearRect(0, 0, width, height);
                            ctx.fillStyle = '#FFFFFF';
                            ctx.fillRect(0, 0, width, height);

                            // Draw scaled image
                            ctx.imageSmoothingEnabled = true;
                            ctx.imageSmoothingQuality = 'high';
                            ctx.drawImage(img, 0, 0, width, height);

                            blob = await new Promise(resolve => {
                                canvas.toBlob(resolve, 'image/jpeg', IMAGE_CONFIG.fallbackQuality);
                            });
                            console.log('Final blob size after scaling:', blob.size);
                        }
                    }

                    // Convert final blob to base64
                    const reader = new FileReader();
                    reader.onloadend = () => {
                        const base64 = reader.result.split('base64,')[1];
                        console.log('Image processing complete');
                        resolve({
                            base64,
                            width,
                            height,
                            size: blob.size,
                            blob
                        });
                    };
                    reader.onerror = (error) => {
                        console.error('Error reading blob:', error);
                        reject(error);
                    };
                    reader.readAsDataURL(blob);
                } catch (error) {
                    console.error('Error processing image:', error);
                    reject(error);
                }
            };
            
            img.onerror = (error) => {
                console.error('Error loading image:', error);
                reject(new Error('Failed to load image'));
            };

            // Handle both File objects and URLs
            if (input instanceof File) {
                console.log('Processing File input');
                const reader = new FileReader();
                reader.onload = (e) => {
                    img.src = e.target.result;
                };
                reader.onerror = () => {
                    reject(new Error('Failed to read file'));
                };
                reader.readAsDataURL(input);
            } else if (typeof input === 'string') {
                console.log('Processing URL input');
                // For URLs, add cache buster if it's a Bluesky CDN URL
                const url = input.includes('cdn.bsky.app') ? 
                    `${input}?t=${Date.now()}` : 
                    input;
                img.src = url;
            } else {
                reject(new Error('Invalid input: must be File or URL string'));
            }
        });
    }

    async makeApiCall(imageInput, tryDifferentApproach = false) {
        console.log('Starting API call...', { tryDifferentApproach });
        const requestBody = {
            model: this.currentModel,
            messages: [
                { role: "system", content: ALT_TEXT_CONFIG.systemPrompt },
                { role: "user", content: tryDifferentApproach ? 
                    ALT_TEXT_CONFIG.userPrompt + "\n\nPlease try a different approach for this description, focusing on different aspects or details of the image." :
                    ALT_TEXT_CONFIG.userPrompt 
                }
            ],
            stream: true
        };

        // Handle various image input types
        try {
            let processedImage;
            
            if (typeof imageInput === 'string') {
                console.log('Processing string input type:', imageInput.substring(0, 50) + '...');
                if (imageInput.includes('cdn.bsky.app')) {
                    console.log('Processing Bluesky CDN URL');
                    processedImage = await this.resizeImage(imageInput);
                } else if (imageInput.match(/^[A-Za-z0-9+/=]+$/)) {
                    console.log('Processing base64 content');
                    processedImage = await this.resizeImage(`data:image/jpeg;base64,${imageInput}`);
                } else if (imageInput.startsWith('data:')) {
                    console.log('Processing data URL');
                    processedImage = await this.resizeImage(imageInput);
                } else {
                    console.log('Processing generic URL');
                    const response = await fetch(imageInput);
                    const blob = await response.blob();
                    processedImage = await this.resizeImage(URL.createObjectURL(blob));
                }
            } else if (imageInput instanceof Blob || imageInput instanceof File) {
                console.log('Processing Blob/File input');
                processedImage = await this.resizeImage(imageInput);
            } else {
                throw new Error('Invalid image input type');
            }

            // Add processed image to request
            requestBody.messages[requestBody.messages.length - 1].images = [processedImage.base64];
            requestBody.messages[requestBody.messages.length - 1].imageMetadata = {
                width: processedImage.width,
                height: processedImage.height,
                size: processedImage.size,
                mimeType: 'image/jpeg'
            };

            console.log('Making API request to:', 'https://ai.assisted.space/api/chat');
            console.log('Request metadata:', {
                width: processedImage.width,
                height: processedImage.height,
                size: processedImage.size
            });

            // Make API request
            const response = await fetch('https://ai.assisted.space/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('API Error Response:', errorText);
                throw new Error(`API Error (${response.status}): ${errorText}`);
            }

            console.log('API request successful');
            return {
                response,
                processedImage
            };
        } catch (error) {
            console.error('Error in makeApiCall:', error);
            throw error;
        }
    }

    /**
     * Converts a Blob object to a Base64-encoded string.
     *
     * @param {Blob} blob - The blob to convert.
     * @returns {Promise<string>} - A promise that resolves with the Base64 string.
     */
    async blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => {
                const base64 = reader.result.split(',')[1];
                resolve(base64);
            };
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }

    /**
     * Generates alt text for a given image input.
     * Uses a streaming API response to assemble the full alt text.
     *
     * @param {string|Blob|File} input - The image input.
     * @param {boolean} [tryDifferentApproach=false] - Whether to use an alternative approach for generating the alt text.
     * @returns {Promise<string>} - The generated alt text.
     * @throws {Error} Throws an error if generation fails after the maximum retries.
     */
    async generateAltText(input, tryDifferentApproach = false) {
        try {
            console.log("Starting alt text generation...");
            let attempts = 0;
            let altText = "";
            let error = null;

            while (attempts < this.maxRetries) {
                try {
                    console.log(`Attempt ${attempts + 1} of ${this.maxRetries}`);
                    const { response, processedImage } = await this.makeApiCall(input, tryDifferentApproach);
                    
                    // Add timeout protection
                    const timeout = new Promise((_, reject) => {
                        setTimeout(() => reject(new Error('Stream reading timeout after 30 seconds')), 30000);
                    });

                    const streamReader = async () => {
                        const reader = response.body.getReader();
                        const decoder = new TextDecoder();
                        let fullContent = "";
                        let lastChunkTime = Date.now();

                        console.log('Starting to read stream...');
                        try {
                            while (true) {
                                const { value, done } = await reader.read();
                                if (done) {
                                    console.log('Stream complete');
                                    break;
                                }

                                // Update last chunk time
                                lastChunkTime = Date.now();

                                const chunk = decoder.decode(value, { stream: true });
                                console.log('Received chunk:', chunk);
                                
                                // Process each line in the chunk
                                const lines = chunk.split('\n');
                                for (const line of lines) {
                                    if (line.trim() === '') continue;

                                    try {
                                        let jsonData;
                                        if (line.startsWith('data: ')) {
                                            jsonData = JSON.parse(line.slice(6));
                                        } else {
                                            jsonData = JSON.parse(line);
                                        }

                                        if (jsonData.done) {
                                            console.log('Received done signal from API');
                                            return fullContent;
                                        }

                                        if ((jsonData.type === 'delta' && jsonData.content) || jsonData.message?.content) {
                                            const content = jsonData.type === 'delta' ? jsonData.content : jsonData.message.content;
                                            console.log('Parsed content:', content);
                                            fullContent += content;
                                        }
                                    } catch (error) {
                                        console.warn("Error parsing line:", line, error);
                                        continue;
                                    }
                                }
                            }
                            return fullContent;
                        } finally {
                            reader.releaseLock();
                        }
                    };

                    // Race between the stream reader and timeout
                    const content = await Promise.race([
                        streamReader(),
                        timeout
                    ]);

                    if (!content) {
                        throw new Error('No content received from API');
                    }

                    altText = this.formatAltText(content.trim());
                    console.log('Generated alt text:', altText);
                    break;
                } catch (e) {
                    error = e;
                    console.error(`Attempt ${attempts + 1} failed:`, e);
                    attempts++;
                    if (attempts < this.maxRetries) {
                        console.log(`Retrying in ${attempts} seconds...`);
                        await new Promise(resolve => setTimeout(resolve, 1000 * attempts));
                    }
                }
            }

            if (!altText && error) {
                console.error('All attempts failed:', error);
                throw error;
            }

            return altText;
        } catch (error) {
            console.error('Error generating alt text:', error);
            throw error;
        }
    }

    /**
     * Formats the generated alt text by cleaning up unnecessary prefixes,
     * ensuring proper punctuation, and truncating if necessary.
     *
     * @param {string} text - The raw generated alt text.
     * @returns {string} - The formatted alt text.
     */
    formatAltText(text) {
        console.log('Formatting alt text:', text);
        // Remove any prefixes like "Alt text:" or "description:"
        text = text.replace(/^(alt text:|description:|image shows:)/i, '').trim();
        // Ensure proper sentence spacing
        text = text.replace(/([.!?])\s*([A-Z])/g, '$1 $2');
        // Remove extra spaces
        text = text.replace(/\s+/g, ' ');
        // Ensure proper punctuation at the end
        if (!text.endsWith('.') && !text.endsWith('!') && !text.endsWith('?')) {
            text += '.';
        }
        // Truncate if too long, preserving complete sentences
        if (text.length > 1000) {
            console.log('Text too long, truncating...');
            const sentences = text.match(/[^.!?]+[.!?]+/g) || [];
            text = '';
            for (const sentence of sentences) {
                if ((text + sentence).length <= 997) {
                    text += sentence;
                } else {
                    break;
                }
            }
            text = text.trim() + '...';
        }
        console.log('Formatted alt text:', text);
        return text;
    }
}

export default AltTextGenerator; 