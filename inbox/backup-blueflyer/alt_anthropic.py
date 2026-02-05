// Alt Text Generator Configuration for Anthropic
ALT_TEXT_CONFIG = {
    "model": "claude-3-opus@20240229",
    // Replace YOUR_ANTHROPIC_API_KEY with your actual API key
    "apiKey": "YOUR_ANTHROPIC_API_KEY",
    "systemPrompt": """You're an Alt Text Specialist, dedicated to creating precise and accessible alt text for digital images, especially memes. Your primary goal is to ensure visually impaired individuals can engage with imagery by providing concise, accurate, and ethically-minded descriptions.

Create Alt Text:
- Depict essential visuals and visible text accurately.
- Avoid adding social-emotional context or narrative interpretations unless specifically requested.
- Refrain from speculating on artists' intentions.
- Avoid prepending with "Alt text:" for direct usability.
- Maintain clarity and consistency for all descriptions, including direct image links.
- Character limit: All descriptions must be under 1000 characters.

DO NOT add any commentary or other text before or after the alt text. Output ONLY the alt text description.""",
    "userPrompt": """Describe this image with precise, factual details about the visual elements and any visible text. Focus on:
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

Provide ONLY the description, no additional text."""
};

// Image Processing Configuration remains unchanged
const IMAGE_CONFIG = {
    maxWidth: 2048,
    maxHeight: 2048,
    maxFileSize: 975000, // ~975KB to leave room for overhead
    quality: 0.85,
    fallbackQuality: 0.7,
    format: 'image/jpeg'
};

// Alt Text Generator Class adapted for Anthropic Chat API
class AltTextGenerator {
    constructor() {
        console.log('[AltTextGenerator] Initializing with model:', ALT_TEXT_CONFIG["model"]);
        this.currentModel = ALT_TEXT_CONFIG["model"];
        this.maxRetries = 2;
    }

    async resizeImage(input, maxDimension = IMAGE_CONFIG.maxWidth) {
        console.log('[resizeImage] Starting image resize operation');
        console.log('[resizeImage] Input type:', typeof input, input instanceof File ? 'File' : input instanceof Blob ? 'Blob' : 'Other');
        
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.crossOrigin = 'anonymous';

            img.onload = async () => {
                try {
                    console.log('[resizeImage] Original dimensions:', { width: img.width, height: img.height });
                    
                    const canvas = document.createElement('canvas');
                    let width = img.width;
                    let height = img.height;
                    
                    if (width > height && width > maxDimension) {
                        height = Math.round((height * maxDimension) / width);
                        width = maxDimension;
                    } else if (height > maxDimension) {
                        width = Math.round((width * maxDimension) / height);
                        height = maxDimension;
                    }
                    
                    console.log('[resizeImage] Resized dimensions:', { width, height });
                    
                    canvas.width = width;
                    canvas.height = height;
                    
                    const ctx = canvas.getContext('2d');
                    ctx.clearRect(0, 0, width, height);
                    ctx.fillStyle = '#FFFFFF';
                    ctx.fillRect(0, 0, width, height);
                    
                    ctx.imageSmoothingEnabled = true;
                    ctx.imageSmoothingQuality = 'high';
                    ctx.drawImage(img, 0, 0, width, height);

                    let blob = await new Promise(resolve => {
                        canvas.toBlob(resolve, IMAGE_CONFIG.format, IMAGE_CONFIG.quality);
                    });
                    
                    console.log('[resizeImage] Initial blob size:', blob.size);
                    
                    if (blob.size > IMAGE_CONFIG.maxFileSize) {
                        console.log('[resizeImage] Blob too large, reducing quality');
                        blob = await new Promise(resolve => {
                            canvas.toBlob(resolve, IMAGE_CONFIG.format, IMAGE_CONFIG.fallbackQuality);
                        });
                        
                        if (blob.size > IMAGE_CONFIG.maxFileSize) {
                            console.log('[resizeImage] Still too large, scaling down dimensions');
                            const scale = Math.sqrt(IMAGE_CONFIG.maxFileSize / blob.size);
                            width = Math.round(width * scale);
                            height = Math.round(height * scale);
                            console.log('[resizeImage] New scaled dimensions:', { width, height });
                            
                            canvas.width = width;
                            canvas.height = height;
                            ctx.clearRect(0, 0, width, height);
                            ctx.fillStyle = '#FFFFFF';
                            ctx.fillRect(0, 0, width, height);
                            ctx.imageSmoothingEnabled = true;
                            ctx.imageSmoothingQuality = 'high';
                            ctx.drawImage(img, 0, 0, width, height);
                            blob = await new Promise(resolve => {
                                canvas.toBlob(resolve, IMAGE_CONFIG.format, IMAGE_CONFIG.fallbackQuality);
                            });
                            console.log('[resizeImage] Final blob size after scaling:', blob.size);
                        }
                    }

                    const reader = new FileReader();
                    reader.onloadend = () => {
                        const base64 = reader.result.split('base64,')[1];
                        console.log('[resizeImage] Successfully converted to base64');
                        resolve({
                            base64,
                            width,
                            height,
                            size: blob.size,
                            blob
                        });
                    };
                    reader.onerror = (error) => {
                        console.error('[resizeImage] Error reading blob:', error);
                        reject(error);
                    };
                    reader.readAsDataURL(blob);
                } catch (error) {
                    console.error('[resizeImage] Error processing image:', error);
                    reject(error);
                }
            };

            img.onerror = (error) => {
                console.error('[resizeImage] Error loading image:', error);
                reject(new Error('Failed to load image'));
            };

            if (input instanceof File) {
                console.log('[resizeImage] Processing File input');
                const reader = new FileReader();
                reader.onload = (e) => {
                    img.src = e.target.result;
                };
                reader.onerror = () => {
                    console.error('[resizeImage] Error reading File');
                    reject(new Error('Failed to read file'));
                };
                reader.readAsDataURL(input);
            } else if (typeof input === 'string') {
                console.log('[resizeImage] Processing URL string input');
                const url = input.includes('cdn.bsky.app') ? `${input}?t=${Date.now()}` : input;
                img.src = url;
            } else {
                console.error('[resizeImage] Invalid input type');
                reject(new Error('Invalid input: must be File or URL string'));
            }
        });
    }

    async makeApiCall(imageInput, tryDifferentApproach = false) {
        console.log('[makeApiCall] Starting API call', { tryDifferentApproach });
        
        try {
            let processedImage;
            if (typeof imageInput === 'string') {
                console.log('[makeApiCall] Processing string input');
                if (imageInput.includes('cdn.bsky.app')) {
                    console.log('[makeApiCall] Processing Bluesky CDN image');
                    processedImage = await this.resizeImage(imageInput);
                } else if (imageInput.match(/^[A-Za-z0-9+/=]+$/)) {
                    console.log('[makeApiCall] Processing base64 string');
                    processedImage = await this.resizeImage(`data:image/jpeg;base64,${imageInput}`);
                } else if (imageInput.startsWith('data:')) {
                    console.log('[makeApiCall] Processing data URL');
                    processedImage = await this.resizeImage(imageInput);
                } else {
                    console.log('[makeApiCall] Processing external URL');
                    const response = await fetch(imageInput);
                    const blob = await response.blob();
                    processedImage = await this.resizeImage(URL.createObjectURL(blob));
                }
            } else if (imageInput instanceof Blob || imageInput instanceof File) {
                console.log('[makeApiCall] Processing Blob/File input');
                processedImage = await this.resizeImage(imageInput);
            } else {
                throw new Error('Invalid image input type');
            }

            console.log('[makeApiCall] Image processed successfully', {
                width: processedImage.width,
                height: processedImage.height,
                size: processedImage.size
            });

            const prompt = `System: ${ALT_TEXT_CONFIG.systemPrompt}\n\nHuman: ${ALT_TEXT_CONFIG.userPrompt}\n\nImage Data (Base64): ${processedImage.base64}\nImage Metadata: width=${processedImage.width}, height=${processedImage.height}, size=${processedImage.size}\n\nAssistant:`;

            const requestBody = {
                prompt: prompt,
                model: this.currentModel,
                max_tokens_to_sample: 256,
                stream: true,
                stop_sequences: ["\nHuman:"]
            };

            requestBody.messages[requestBody.messages.length - 1].images = [processedImage.base64];
            requestBody.messages[requestBody.messages.length - 1].imageMetadata = {
                width: processedImage.width,
                height: processedImage.height,
                size: processedImage.size,
                mimeType: 'image/jpeg'
            };

            console.log('[makeApiCall] Making API request to Anthropic');

            const response = await fetch('https://api.anthropic.com/v1/complete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'Authorization': `Bearer ${ALT_TEXT_CONFIG.apiKey}`
                },
                body: JSON.stringify(requestBody)
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('[makeApiCall] API Error Response:', errorText);
                throw new Error(`API Error (${response.status}): ${errorText}`);
            }

            console.log('[makeApiCall] API request successful');
            return {
                response,
                processedImage
            };
        } catch (error) {
            console.error('[makeApiCall] Error:', error);
            throw error;
        }
    }

    async blobToBase64(blob) {
        console.log('[blobToBase64] Converting blob to base64');
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => {
                console.log('[blobToBase64] Conversion successful');
                const base64 = reader.result.split(',')[1];
                resolve(base64);
            };
            reader.onerror = (error) => {
                console.error('[blobToBase64] Conversion failed:', error);
                reject(error);
            };
            reader.readAsDataURL(blob);
        });
    }

    async generateAltText(input, tryDifferentApproach = false) {
        console.log('[generateAltText] Starting alt text generation', { tryDifferentApproach });
        let attempts = 0;
        let altText = "";
        let error = null;

        while (attempts < this.maxRetries) {
            try {
                console.log(`[generateAltText] Attempt ${attempts + 1} of ${this.maxRetries}`);
                const { response } = await this.makeApiCall(input, tryDifferentApproach);
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let fullContent = "";

                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value, { stream: true });
                    console.log('[generateAltText] Received chunk:', chunk.length, 'bytes');
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
                            if ((jsonData.type === 'delta' && jsonData.completion) || jsonData.completion) {
                                fullContent += jsonData.completion;
                                console.log('[generateAltText] Accumulated content length:', fullContent.length);
                            }
                        } catch (lineError) {
                            console.warn('[generateAltText] Error parsing line:', line, lineError);
                            continue;
                        }
                    }
                }

                altText = this.formatAltText(fullContent.trim());
                console.log('[generateAltText] Generated alt text:', altText);
                if (altText) break;
            } catch (e) {
                error = e;
                attempts++;
                console.error(`[generateAltText] Attempt ${attempts} failed:`, e);
                await new Promise(resolve => setTimeout(resolve, 1000 * attempts));
            }
        }

        if (!altText && error) {
            console.error('[generateAltText] Failed after all retries:', error);
            throw error;
        }

        return altText;
    }

    formatAltText(text) {
        console.log('[formatAltText] Starting text formatting');
        console.log('[formatAltText] Original text:', text);
        
        text = text.replace(/^(alt text:|description:|image shows:)/i, '').trim();
        text = text.replace(/([.!?])\s*([A-Z])/g, '$1 $2');
        text = text.replace(/\s+/g, ' ');
        
        if (!text.endsWith('.') && !text.endsWith('!') && !text.endsWith('?')) {
            text += '.';
        }
        
        if (text.length > 1000) {
            console.log('[formatAltText] Text exceeds 1000 characters, truncating');
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
        
        console.log('[formatAltText] Final formatted text:', text);
        return text;
    }
}

export default AltTextGenerator; 