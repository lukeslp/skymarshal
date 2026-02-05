#!/usr/bin/env python3

import requests
import base64
import json
from pathlib import Path
from typing import Optional, Dict, Union, Any, List, Tuple
import logging
from datetime import datetime
from PIL import Image
import numpy as np
import time
import pytesseract

# Set Tesseract path if it's not in PATH
# Uncomment and modify the appropriate line for your system:
# pytesseract.pytesseract.tesseract_cmd = r'/usr/local/bin/tesseract'  # macOS with Homebrew
# pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'        # Linux
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Windows

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Enable debug logging

def check_tesseract():
    """Check if tesseract is properly installed and accessible."""
    try:
        from pytesseract import get_tesseract_version
        version = get_tesseract_version()
        logger.info(f"Tesseract version: {version}")
        return True
    except Exception as e:
        logger.warning(f"Tesseract not accessible: {str(e)}")
        return False

class TestResult:
    def __init__(self, name: str, success: bool, message: str = "", tokens: int = 0):
        self.name = name
        self.success = success
        self.message = message
        self.tokens = tokens
        self.timestamp = datetime.now()

class APITester:
    def __init__(self, base_url: str = "https://actuallyusefulai.com/api/v1/prod"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.coze_token = 'pat_Uk4Z075Oo8RE5Po13rBUoEQNzr3dcKTNmBuf5Qtj1V6QZLiwAeZDaNzfNSLMIca8'
        self.results: List[TestResult] = []
    
    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """Handle API response and potential errors."""
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            return {"success": False, "error": str(e)}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            return {"success": False, "error": "Invalid JSON response"}

    def upload_to_coze(self, file_path: str) -> Dict[str, Any]:
        """Upload file directly to Coze API."""
        if not Path(file_path).exists():
            return {"success": False, "error": f"File not found: {file_path}"}
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (Path(file_path).name, f, 'image/jpeg')}
                headers = {'Authorization': f'Bearer {self.coze_token}'}
                
                response = requests.post(
                    'https://api.coze.com/v1/files/upload',
                    files=files,
                    headers=headers
                )
                
                response_data = response.json()
                if response_data.get('code') == 0:
                    file_id = response_data.get('data', {}).get('id')
                    return {"success": True, "file_id": file_id}
                else:
                    return {"success": False, "error": response_data.get('msg', 'Unknown error')}
                    
        except Exception as e:
            logger.error(f"Coze upload failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def chat_with_image(self, file_id: str, message: str, endpoint: str = "drummer") -> None:
        """Test chat endpoints with image."""
        try:
            data = {
                "message": message,
                "file_id": file_id,
                "user_id": "test_user"
            }
            
            response = self.session.post(
                f"{self.base_url}/chat/{endpoint}",
                json=data,
                stream=True
            )
            
            if response.status_code != 200:
                logger.error(f"Chat request failed with status {response.status_code}")
                print(json.dumps({
                    "success": False,
                    "error": f"Request failed with status {response.status_code}"
                }, indent=2))
                return

            print("Streaming response:")
            full_content = ""
            for line in response.iter_lines():
                if line:
                    try:
                        line_text = line.decode('utf-8')
                        if line_text.startswith('data: '):
                            data = json.loads(line_text[6:])  # Remove 'data: ' prefix
                            if data["type"] == "delta":
                                full_content += data["content"]
                                print(f"\rTokens: {data['tokens']}", end="", flush=True)
                            elif data["type"] == "complete":
                                print(f"\nFinal response ({data['tokens']} tokens):")
                                print(full_content)
                                print("-" * 80)
                    except Exception as e:
                        logger.error(f"Error processing stream line: {str(e)}")
                        continue
            
        except Exception as e:
            logger.error(f"Chat failed: {str(e)}")
            print(json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2))

    # def get_counter(self) -> Dict[str, Any]:
    #     """Test get image counter endpoint."""
    #     response = self.session.get(f"{self.base_url}/files/counter")
    #     return self._handle_response(response)

    # def test_ollama_tags(self) -> TestResult:
    #     """Test Ollama tags endpoint."""
    #     name = "Ollama Tags"
    #     try:
    #         response = self.session.get("https://drummer.assisted.space/api/tags")
    #         
    #         if response.status_code != 200:
    #             return TestResult(name, False, f"HTTP {response.status_code}")
    #             
    #         data = response.json()
    #         model_count = len(data.get('models', []))
    #         return TestResult(name, True, f"Found {model_count} models", model_count)
    #         
    #     except Exception as e:
    #         logger.error(f"Ollama tags failed: {str(e)}")
    #         return TestResult(name, False, str(e))
# 
#     def test_ollama_ps(self) -> TestResult:
#         """Test Ollama ps endpoint."""
#         name = "Ollama PS"
#         try:
#             response = self.session.get("https://drummer.assisted.space/api/ps")
#             
#             if response.status_code != 200:
#                 return TestResult(name, False, f"HTTP {response.status_code}")
#                 
#             return TestResult(name, True, str(response.json()))
#             
#         except Exception as e:
#             logger.error(f"Ollama ps failed: {str(e)}")
#             return TestResult(name, False, str(e))

    # def test_ollama_version(self) -> TestResult:
    #     """Test Ollama version endpoint."""
    #     name = "Ollama Version"
    #     try:
    #         response = self.session.get("https://drummer.assisted.space/api/version")
    #         
    #         if response.status_code != 200:
    #             return TestResult(name, False, f"HTTP {response.status_code}")
    #             
    #         return TestResult(name, True, str(response.json()))
    #         
    #     except Exception as e:
    #         logger.error(f"Ollama version failed: {str(e)}")
    #         return TestResult(name, False, str(e))

    # def test_ollama_chat(self, model: str = "llama3.2:3b") -> TestResult:
    #     """Test Ollama chat endpoint."""
    #     name = f"Ollama Chat ({model})"
    #     try:
    #         data = {
    #             "model": model,
    #             "messages": [{"role": "user", "content": "Hello, how are you?"}],
    #             "stream": True
    #         }
    #         
    #         response = self.session.post(
    #             "https://drummer.assisted.space/api/chat",
    #             json=data,
    #             stream=True
    #         )
    #         
    #         return self._handle_chat_stream(name, response)
    #     except Exception as e:
    #         return TestResult(name, False, str(e))
# 
#     def test_drummer_direct(self, model: str = "deepseek-r1:1.5b") -> TestResult:
#         """Test direct drummer endpoint."""
#         name = f"Direct Drummer ({model})"
#         try:
#             data = {
#                 "model": model,
#                 "messages": [{"role": "user", "content": "Hello, how are you?"}],
#                 "stream": True
#             }
#             
#             response = self.session.post(
#                 "https://drummer.assisted.space/api/chat",
#                 json=data,
#                 stream=True
#             )
#             
#             return self._handle_chat_stream(name, response)
#         except Exception as e:
#             return TestResult(name, False, str(e))
# 
#     def test_mistral_chat(self) -> TestResult:
#         """Test Mistral chat endpoint."""
#         name = "Mistral Chat"
#         try:
#             data = {
#                 "message": "Hello, how are you?",
#                 "bot_id": "pixtral-12b-2409",
#                 "conversation_id": None,
#                 "messages": [{
#                     "role": "user",
#                     "content": "Hello, how are you?"
#                 }]
#             }
#             
#             logger.debug(f"Sending request to Mistral: {json.dumps(data, indent=2)}")
#             
#             response = self.session.post(
#                 f"{self.base_url}/chat/mistral",
#                 json=data,
#                 stream=True,
#                 headers={
#                     "Content-Type": "application/json",
#                     "Accept": "text/event-stream"
#                 }
#             )
#             
#             if response.status_code != 200:
#                 return TestResult(name, False, f"HTTP {response.status_code}")
# 
#             try:
#                 full_content = ""
#                 tokens = 0
#                 for line in response.iter_lines():
#                     if line:
#                         line_text = line.decode('utf-8')
#                         if line_text.startswith('data: '):
#                             content = line_text.replace('data: data: ', 'data: ')[6:]
#                             if content.strip() == '[DONE]':
#                                 continue
#                                 
#                             data = json.loads(content)
#                             if data.get('choices') and data['choices'][0].get('delta'):
#                                 delta = data['choices'][0]['delta']
#                                 if delta.get('content'):
#                                     full_content += delta['content']
#                                     if data.get('usage') and data['usage'].get('total_tokens'):
#                                         tokens = data['usage']['total_tokens']
#                                     print(f"\rTokens: {tokens}", end="", flush=True)
# 
#                 print(f"\nFinal response ({tokens} tokens):")
#                 print(full_content)
#                 print("-" * 80)
#                 return TestResult(name, True, full_content, tokens)
# 
#             except Exception as e:
#                 logger.error(f"Error processing Mistral stream: {str(e)}")
#                 return TestResult(name, False, str(e))
#                 
#         except Exception as e:
#             logger.error(f"Mistral chat failed: {str(e)}")
#             return TestResult(name, False, str(e))
# 
#     def test_perplexity_chat(self) -> TestResult:
#         """Test Perplexity chat endpoint."""
#         name = "Perplexity Chat"
#         try:
#             data = {
#                 "model": "llama-3.1-sonar-small-128k-online",
#                 "messages": [{"role": "user", "content": "Hello, how are you?"}],
#                 "temperature": 0.2,
#                 "top_p": 0.9
#             }
#             
#             response = self.session.post(
#                 f"{self.base_url}/chat/perplexity",
#                 json=data,
#                 stream=True
#             )
#             
#             return self._handle_chat_stream(name, response)
#         except Exception as e:
#             return TestResult(name, False, str(e))

    def _handle_chat_stream(self, name: str, response: requests.Response) -> TestResult:
        """Handle streaming chat response and return test result."""
        if response.status_code != 200:
            return TestResult(name, False, f"HTTP {response.status_code}")

        try:
            full_content = ""
            tokens = 0
            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith('data: '):
                        data = json.loads(line_text[6:])
                        if data.get("type") == "delta":
                            full_content += data.get("content", "")
                            tokens = data.get("tokens", 0)
                            print(f"\rTokens: {tokens}", end="", flush=True)
                        elif data.get("type") == "complete":
                            print(f"\nFinal response ({tokens} tokens):")
                            print(full_content)
                            print("-" * 80)
                            return TestResult(name, True, full_content, tokens)

            return TestResult(name, True, full_content, tokens)
        except Exception as e:
            return TestResult(name, False, str(e))

    def test_file_upload(self, file_path: str) -> TestResult:
        """Test regular file upload endpoint."""
        name = "File Upload"
        try:
            if not Path(file_path).exists():
                return TestResult(name, False, f"File not found: {file_path}")
            
            with open(file_path, 'rb') as f:
                files = {'file': ('image.jpg', f, 'image/jpeg')}
                response = self.session.post(
                    f"{self.base_url}/files/upload",
                    files=files
                )
            return TestResult(name, response.status_code == 200, str(response.json()))
        except Exception as e:
            return TestResult(name, False, str(e))

    def test_clear_files(self) -> TestResult:
        """Test clear all files endpoint."""
        name = "Clear Files (Nuke)"
        try:
            response = self.session.post(f"{self.base_url}/files/nuke")
            return TestResult(name, response.status_code == 200, str(response.json()))
        except Exception as e:
            return TestResult(name, False, str(e))

    def test_url_to_base64(self, url: str = "https://actuallyusefulai.com/assets/luke/luke_cover.png") -> TestResult:
        """Test URL to base64 conversion endpoint."""
        name = "URL to Base64"
        try:
            response = self.session.post(
                f"{self.base_url}/files/url-to-base64",
                json={"url": url, "type": "image"}
            )
            return TestResult(name, response.status_code == 200, str(response.json()))
        except Exception as e:
            return TestResult(name, False, str(e))

    def test_ocr_url(self, url: str = "https://actuallyusefulai.com/assets/luke/luke_cover.png") -> TestResult:
        """Test OCR with URL endpoint."""
        name = "OCR (URL)"
        if not check_tesseract():
            return TestResult(name, False, "Tesseract not available - skipping test")
        try:
            response = self.session.post(
                f"{self.base_url}/files/ocr",
                json={"url": url, "type": "image"}
            )
            return TestResult(name, response.status_code == 200, str(response.json()))
        except Exception as e:
            return TestResult(name, False, str(e))

    def test_ocr_base64(self, image_path: str) -> TestResult:
        """Test OCR with base64 endpoint."""
        name = "OCR (Base64)"
        if not check_tesseract():
            return TestResult(name, False, "Tesseract not available - skipping test")
        try:
            with open(image_path, 'rb') as f:
                base64_data = base64.b64encode(f.read()).decode('utf-8')
            
            response = self.session.post(
                f"{self.base_url}/files/ocr",
                json={"base64": f"data:image/jpeg;base64,{base64_data}"}
            )
            return TestResult(name, response.status_code == 200, str(response.json()))
        except Exception as e:
            return TestResult(name, False, str(e))

    def test_ocr_file(self, file_path: str) -> TestResult:
        """Test OCR with file upload endpoint."""
        name = "OCR (File)"
        if not check_tesseract():
            return TestResult(name, False, "Tesseract not available - skipping test")
        try:
            if not Path(file_path).exists():
                return TestResult(name, False, f"File not found: {file_path}")
            
            with open(file_path, 'rb') as f:
                files = {'image': ('image.jpg', f, 'image/jpeg')}
                response = self.session.post(
                    f"{self.base_url}/files/ocr",
                    files=files
                )
            return TestResult(name, response.status_code == 200, str(response.json()))
        except Exception as e:
            return TestResult(name, False, str(e))

def create_test_image(path: str = "test.jpg", size: tuple = (100, 100)) -> str:
    """Create a test image with some text for OCR testing."""
    from PIL import Image, ImageDraw, ImageFont
    
    # Create a white background
    img = Image.new('RGB', size, color='white')
    draw = ImageDraw.Draw(img)
    
    # Add some text
    text = "Hello, World!"
    draw.text((10, 10), text, fill='black')
    
    # Save the image
    img.save(path)
    return path

# def print_summary(results: List[TestResult]):
#     """Print a summary of all test results."""
#     print("\n=== Test Summary ===\n")
#     
#     total = len(results)
#     successful = sum(1 for r in results if r.success)
#     
#     print(f"Total Tests: {total}")
#     print(f"Successful: {successful}")
#     print(f"Failed: {total - successful}")
#     print("\nDetailed Results:")
#     
#     for result in results:
#         status = "✓" if result.success else "✗"
#         print(f"{status} {result.name}")
#         if not result.success:
#             print(f"  Error: {result.message}")
#         if result.tokens:
#             print(f"  Tokens: {result.tokens}")
#         print()
# 
# def main():
#     # Initialize the API tester
#     tester = APITester()
#     
#     print("\n=== Running API Tests ===\n")
#     
#     # Test Ollama endpoints
#     print("Testing Ollama Endpoints...")
#     tester.results.append(tester.test_ollama_tags())
#     time.sleep(1)
#     tester.results.append(tester.test_ollama_ps())
#     time.sleep(1)
#     tester.results.append(tester.test_ollama_version())
#     time.sleep(1)
#     tester.results.append(tester.test_ollama_chat())
#     time.sleep(1)
#     
#     # Test standard chat endpoints
#     print("\nTesting Chat Endpoints...")
#     tester.results.append(tester.test_drummer_direct())
#     time.sleep(1)
#     tester.results.append(tester.test_mistral_chat())
#     time.sleep(1)
#     tester.results.append(tester.test_perplexity_chat())
#     time.sleep(1)
#     
#     # Test file operations
#     print("\nTesting File Operations...")
#     
#     # Create test image first since we'll need it for multiple tests
#     test_image = create_test_image()
#     
#     print("Testing File Upload...")
#     tester.results.append(tester.test_file_upload(test_image))
#     time.sleep(1)
#     
#     print("\nTesting Get Image Counter...")
#     counter_result = tester.get_counter()
#     tester.results.append(TestResult(
#         "Image Counter", 
#         counter_result.get("success", False),
#         str(counter_result.get("count", "Error"))
#     ))
#     print(json.dumps(counter_result, indent=2))
#     
#     print("\nTesting Clear Files...")
#     tester.results.append(tester.test_clear_files())
#     time.sleep(1)
#     
#     print("\nTesting URL to Base64...")
#     tester.results.append(tester.test_url_to_base64())
#     time.sleep(1)
#     
#     print("\nTesting OCR Endpoints...")
#     tester.results.append(tester.test_ocr_url())
#     time.sleep(1)
#     tester.results.append(tester.test_ocr_base64(test_image))
#     time.sleep(1)
#     tester.results.append(tester.test_ocr_file(test_image))
#     time.sleep(1)
    
    # Coze upload and alt text tests
    print("\nTesting Coze Upload...")
    upload_result = tester.upload_to_coze(test_image)
    tester.results.append(TestResult(
        "Coze Upload",
        upload_result.get("success", False),
        upload_result.get("file_id", str(upload_result.get("error", "Unknown error")))
    ))
    print(json.dumps(upload_result, indent=2))
    
    if upload_result.get("success"):
        file_id = upload_result["file_id"]
        print("\nTesting Alt Text Generation...")
        tester.results.append(tester.test_alt_text(file_id))
        time.sleep(1)
        
        # Add back image chat tests
        print("\nTesting Image Chat Endpoints...")
        endpoints = ["drummer", "", "completions"]
        for endpoint in endpoints:
            name = f"Image Chat ({endpoint or 'default'})"
            print(f"\nTesting {name}...")
            
            try:
                tester.chat_with_image(
                    file_id=file_id,
                    message="Please describe this image",
                    endpoint=endpoint
                )
                tester.results.append(TestResult(name, True))
            except Exception as e:
                tester.results.append(TestResult(name, False, str(e)))
            
            time.sleep(1)
    
    # Add back summary
    print_summary(tester.results)

if __name__ == "__main__":
    main() 