/**
 * Ollama Image Chat Generation Snippets
 * 
 * These snippets demonstrate how to interact with a local Ollama instance
 * to generate chat responses that include image analysis.
 * 
 * Base URL: http://127.0.0.1:11434/api/generate
 * Example Model: coolhand/impossible_alt:13b
 */

// Example of a basic request body structure for Ollama
const exampleRequestBody = {
    model: "coolhand/impossible_alt:13b",  // or your chosen model
    messages: [
        {
            role: "user",
            content: "base64_encoded_image_here"  // The image content
        }
    ],
    stream: false  // Set to true if you want streaming responses
};

/**
 * Example function showing how to make a basic call to Ollama with an image
 * @param {string} base64Image - Base64 encoded image data
 * @param {string} systemPrompt - System prompt to guide the model
 * @param {string} userPrompt - User prompt for specific instructions
 * @returns {Promise<Response>} - The API response
 */
async function makeOllamaImageCall(base64Image, systemPrompt, userPrompt) {
    const requestBody = {
        model: "coolhand/impossible_alt:13b",
        prompt: `${systemPrompt}\n\n${userPrompt}`,
        messages: [{ role: "user", content: base64Image }],
        stream: false
    };

    const response = await fetch('http://127.0.0.1:11434/api/generate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody)
    });

    if (!response.ok) {
        throw new Error(`API Error (${response.status}): ${await response.text()}`);
    }

    return response;
}

/**
 * Example of how to process a streaming response from Ollama
 * @param {Response} response - The streaming response from Ollama
 * @returns {Promise<string>} - The accumulated response content
 */
async function processStreamingResponse(response) {
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
                let jsonData = line.startsWith('data: ') ? 
                    JSON.parse(line.slice(6)) : 
                    JSON.parse(line);

                if ((jsonData.type === 'delta' && jsonData.content) || 
                    jsonData.message?.content) {
                    fullContent += jsonData.type === 'delta' ? 
                        jsonData.content : 
                        jsonData.message.content;
                }
            } catch (error) {
                console.warn("Error parsing line:", line, error);
            }
        }
    }

    return fullContent.trim();
}

/**
 * Usage Example:
 * 
 * const systemPrompt = `You're an AI assistant analyzing images...`;
 * const userPrompt = `Describe this image in detail...`;
 * 
 * // With base64 image:
 * const response = await makeOllamaImageCall(base64Image, systemPrompt, userPrompt);
 * const result = await processStreamingResponse(response);
 * 
 * Note: Ollama must be running locally on port 11434
 */

export {
    makeOllamaImageCall,
    processStreamingResponse
}; 