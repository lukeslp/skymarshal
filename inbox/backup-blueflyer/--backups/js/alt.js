// Alt Text Generator Configuration
const ALT_TEXT_CONFIG = {
    model: "coolhand/impossible_alt:13b",
    API_BASE_URL: "https://actuallyusefulai.com/api/v1/prod",
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

// Alt Text Generator Class
class AltTextGenerator {
    constructor() {
        this.currentModel = ALT_TEXT_CONFIG.model;
        this.API_BASE_URL = ALT_TEXT_CONFIG.API_BASE_URL;
    }

    async resizeImage(input, maxDimension = 2048) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            
            img.onload = () => {
                try {
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

                    canvas.width = width;
                    canvas.height = height;
                    
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0, width, height);
                    
                    const base64 = canvas.toDataURL('image/jpeg', 0.9);
                    resolve(base64.split('base64,')[1]);
                } catch (error) {
                    reject(error);
                }
            };
            
            img.onerror = (error) => {
                reject(new Error('Failed to load image'));
            };

            // Handle both File objects and URLs
            if (input instanceof File) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    img.src = e.target.result;
                };
                reader.onerror = () => {
                    reject(new Error('Failed to read file'));
                };
                reader.readAsDataURL(input);
            } else if (typeof input === 'string') {
                // For URLs, add cache buster if it's a Bluesky CDN URL
                const url = input.includes('cdn.bsky.app') ? 
                    `${input}?t=${Date.now()}` : 
                    input.replace('via.placeholder.com', 'placehold.co');
                img.src = url;
            } else {
                reject(new Error('Invalid input: must be File or URL string'));
            }
        });
    }

    async makeApiCall(imageInput, tryDifferentApproach = false) {
        const requestBody = {
            model: this.currentModel,
            prompt: tryDifferentApproach ? 
                `${ALT_TEXT_CONFIG.systemPrompt}\n\n${ALT_TEXT_CONFIG.userPrompt}\n\nPlease try a different approach for this description, focusing on different aspects or details of the image.` :
                `${ALT_TEXT_CONFIG.systemPrompt}\n\n${ALT_TEXT_CONFIG.userPrompt}`,
            stream: false
        };

        // Handle different types of image input
        if (typeof imageInput === 'string') {
            if (imageInput.includes('cdn.bsky.app')) {
                // For Bluesky CDN URLs, send directly
                requestBody.messages = [{ role: "user", content: imageInput }];
            } else if (imageInput.match(/^[A-Za-z0-9+/=]+$/)) {
                // For base64 content without data URL prefix
                requestBody.messages = [{ role: "user", content: imageInput }];
            } else if (imageInput.startsWith('data:')) {
                // For complete data URLs, extract base64 part
                requestBody.messages = [{ role: "user", content: imageInput.split(',')[1] }];
            } else {
                // For other URLs, try to fetch and convert
                const response = await fetch(imageInput);
                const blob = await response.blob();
                const base64 = await this.blobToBase64(blob);
                requestBody.messages = [{ role: "user", content: base64 }];
            }
        } else if (imageInput instanceof Blob || imageInput instanceof File) {
            // For Blob/File objects
            const base64 = await this.blobToBase64(imageInput);
            requestBody.messages = [{ role: "user", content: base64 }];
        } else {
            throw new Error('Invalid image input type');
        }

        const response = await fetch('http://127.0.0.1:11434/api/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API Error (${response.status}): ${errorText}`);
        }

        return response;
    }

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

    async generateAltText(input, tryDifferentApproach = false) {
        try {
            console.log("Processing image...");
            const response = await this.makeApiCall(input, tryDifferentApproach);
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullContent = "";

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
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

                        if ((jsonData.type === 'delta' && jsonData.content) || jsonData.message?.content) {
                            if (jsonData.type === 'delta') {
                                fullContent += jsonData.content;
                            } else {
                                fullContent += jsonData.message.content;
                            }
                        }
                    } catch (error) {
                        console.warn("Error parsing line:", line, error);
                        continue;
                    }
                }
            }

            return fullContent.trim();
        } catch (error) {
            console.error('Error generating alt text:', error);
            throw error;
        }
    }
}

export default AltTextGenerator; 