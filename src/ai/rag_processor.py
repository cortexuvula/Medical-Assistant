"""
RAG Processor for Medical Assistant
Handles RAG queries via N8N webhook
"""

import logging
import threading
import requests
import json
import os
import uuid
from typing import Optional, Callable
from datetime import datetime
from dotenv import load_dotenv

from managers.data_folder_manager import data_folder_manager

# Load environment variables
# Try loading from root .env first, then fall back to AppData .env
import pathlib
root_env = pathlib.Path(__file__).parent.parent.parent / '.env'
if root_env.exists():
    load_dotenv(dotenv_path=str(root_env))
else:
    load_dotenv(dotenv_path=str(data_folder_manager.env_file_path))


class RagProcessor:
    """Processes RAG queries via N8N webhook"""
    
    def __init__(self, app):
        """
        Initialize the RAG processor.
        
        Args:
            app: Reference to the main application
        """
        self.app = app
        self.is_processing = False
        
        # Get N8N webhook configuration from environment
        self.n8n_webhook_url = os.getenv("N8N_URL")
        self.n8n_auth_header = os.getenv("N8N_AUTHORIZATION_SECRET")
        
        if not self.n8n_webhook_url:
            logging.warning("N8N_URL not found in environment variables")
        if not self.n8n_auth_header:
            logging.warning("N8N_AUTHORIZATION_SECRET not found in environment variables")
            
    def process_message(self, user_message: str, callback: Optional[Callable] = None):
        """
        Process a RAG query from the user.
        
        Args:
            user_message: The user's query
            callback: Optional callback to call when processing is complete
        """
        if self.is_processing:
            logging.warning("RAG processor is already processing a message")
            return
            
        if not self.n8n_webhook_url:
            self._display_error("N8N webhook URL not configured. Please set N8N_URL in .env file.")
            if callback:
                callback()
            return
            
        # Run processing in a separate thread to avoid blocking UI
        thread = threading.Thread(
            target=self._process_message_async,
            args=(user_message, callback),
            daemon=True
        )
        thread.start()
        
    def _process_message_async(self, user_message: str, callback: Optional[Callable]):
        """Async processing of RAG query."""
        try:
            self.is_processing = True
            
            # Add user message to RAG tab
            self._add_message_to_rag_tab("User", user_message)
            
            # Make request to N8N webhook
            try:
                headers = {
                    "Content-Type": "application/json"
                }
                
                # Add authorization header if provided
                if self.n8n_auth_header:
                    # Remove quotes if present
                    auth_value = self.n8n_auth_header.strip("'\"")
                    headers["Authorization"] = auth_value
                
                # Prepare request payload with sessionId
                # Generate a session ID - you can make this persistent per user session if needed
                session_id = getattr(self, 'session_id', None)
                if not session_id:
                    self.session_id = str(uuid.uuid4())
                    session_id = self.session_id
                
                payload = {
                    "chatInput": user_message,
                    "sessionId": session_id
                }
                
                logging.info(f"Sending RAG query to N8N webhook: {self.n8n_webhook_url}")
                logging.info(f"Payload: {payload}")
                
                response = requests.post(
                    self.n8n_webhook_url,
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                
                response.raise_for_status()
                
                # Log raw response for debugging
                logging.info(f"Response status code: {response.status_code}")
                logging.info(f"Response headers: {response.headers}")
                response_text = response.text
                logging.info(f"Raw response: {response_text[:500]}...")  # Log first 500 chars
                
                # Parse response
                if not response_text or response_text.strip() == "":
                    logging.warning("Empty response from N8N webhook - the webhook may need to be configured to return data")
                    output = "The RAG system processed your request but didn't return any data. Please check the N8N workflow configuration to ensure it returns a response."
                else:
                    try:
                        response_data = response.json()
                        
                        # Handle the expected response format
                        # Example: [{"output": "response text"}]
                        if isinstance(response_data, list) and len(response_data) > 0:
                            output = response_data[0].get("output", "No response received from RAG system.")
                        elif isinstance(response_data, dict):
                            output = response_data.get("output", "No response received from RAG system.")
                        else:
                            output = "Unexpected response format from RAG system."
                    except json.JSONDecodeError:
                        # If it's not JSON, just use the text response
                        output = f"RAG Response: {response_text}"
                
                # Add response to RAG tab
                self._add_message_to_rag_tab("RAG Assistant", output)
                
            except requests.exceptions.Timeout:
                error_msg = "Request timed out. The RAG system took too long to respond."
                logging.error(error_msg)
                self._display_error(error_msg)
                
            except requests.exceptions.RequestException as e:
                error_msg = f"Error connecting to RAG system: {str(e)}"
                logging.error(error_msg)
                self._display_error(error_msg)
                
            except json.JSONDecodeError as e:
                error_msg = f"Error parsing RAG response: {str(e)}"
                logging.error(error_msg)
                self._display_error(error_msg)
                
        except Exception as e:
            error_msg = f"Unexpected error in RAG processor: {str(e)}"
            logging.error(error_msg)
            self._display_error(error_msg)
            
        finally:
            self.is_processing = False
            if callback:
                self.app.after(0, callback)
                
    def _add_message_to_rag_tab(self, sender: str, message: str):
        """Add a message to the RAG tab."""
        if not hasattr(self.app, 'rag_text'):
            return
            
        def update_ui():
            # Add timestamp
            timestamp = datetime.now().strftime("%I:%M %p")
            
            # Get current position
            self.app.rag_text.mark_set("insert_start", "end")
            
            # Insert sender name with timestamp
            self.app.rag_text.insert("end", f"{sender} ({timestamp}):\n", "sender")
            
            # If this is from the RAG Assistant, render markdown
            if sender == "RAG Assistant":
                self._render_markdown(message)
            else:
                # Insert plain message for user messages
                self.app.rag_text.insert("end", f"{message}\n\n", "message")
            
            # Add separator
            self.app.rag_text.insert("end", "-" * 50 + "\n\n")
            
            # Configure tags for styling
            self.app.rag_text.tag_config("sender", font=("Arial", 10, "bold"))
            self.app.rag_text.tag_config("message", font=("Arial", 10))
            
            # Scroll to bottom
            self.app.rag_text.see("end")
            
        # Update UI in main thread
        self.app.after(0, update_ui)
        
    def _render_markdown(self, markdown_text: str):
        """Render markdown text with basic formatting in the text widget."""
        import re
        
        lines = markdown_text.split('\n')
        
        for line in lines:
            # Headers
            if line.startswith('### '):
                self.app.rag_text.insert("end", line[4:] + "\n", "h3")
            elif line.startswith('## '):
                self.app.rag_text.insert("end", line[3:] + "\n", "h2")
            elif line.startswith('# '):
                self.app.rag_text.insert("end", line[2:] + "\n", "h1")
            
            # Bold text
            elif '**' in line:
                parts = re.split(r'\*\*(.*?)\*\*', line)
                for i, part in enumerate(parts):
                    if i % 2 == 0:
                        self.app.rag_text.insert("end", part)
                    else:
                        self.app.rag_text.insert("end", part, "bold")
                self.app.rag_text.insert("end", "\n")
            
            # Bullet points
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                indent = len(line) - len(line.lstrip())
                bullet_text = line.strip()[2:]
                self.app.rag_text.insert("end", " " * indent + "• " + bullet_text + "\n", "bullet")
            
            # Numbered lists
            elif re.match(r'^\s*\d+\.\s', line):
                self.app.rag_text.insert("end", line + "\n", "numbered")
            
            # Code blocks (simple)
            elif line.strip().startswith('```'):
                self.app.rag_text.insert("end", line + "\n", "code")
            
            # Regular text
            else:
                self.app.rag_text.insert("end", line + "\n", "message")
        
        # Add an extra newline at the end
        self.app.rag_text.insert("end", "\n")
        
        # Configure markdown tags
        self.app.rag_text.tag_config("h1", font=("Arial", 16, "bold"), spacing3=5)
        self.app.rag_text.tag_config("h2", font=("Arial", 14, "bold"), spacing3=4)
        self.app.rag_text.tag_config("h3", font=("Arial", 12, "bold"), spacing3=3)
        self.app.rag_text.tag_config("bold", font=("Arial", 10, "bold"))
        self.app.rag_text.tag_config("bullet", lmargin1=20, lmargin2=30)
        self.app.rag_text.tag_config("numbered", lmargin1=20, lmargin2=30)
        self.app.rag_text.tag_config("code", font=("Courier", 10), background="#f0f0f0", relief="solid", borderwidth=1)
        
    def _display_error(self, error_message: str):
        """Display an error message in the RAG tab."""
        self._add_message_to_rag_tab("System Error", error_message)
        
    def clear_history(self):
        """Clear the RAG conversation history."""
        if hasattr(self.app, 'rag_text'):
            def clear_ui():
                self.app.rag_text.delete("1.0", "end")
                # Re-add welcome message
                self.app.rag_text.insert("1.0", "Welcome to the RAG Document Search!\n\n")
                self.app.rag_text.insert("end", "This interface allows you to search your document database:\n")
                self.app.rag_text.insert("end", "• Query documents stored in your RAG database\n")
                self.app.rag_text.insert("end", "• Get relevant information from your knowledge base\n")
                self.app.rag_text.insert("end", "• Search through previously uploaded documents\n\n")
                self.app.rag_text.insert("end", "Type your question in the AI Assistant chat box below to search your documents!\n")
                self.app.rag_text.insert("end", "="*50 + "\n\n")
                
                # Configure initial styling
                self.app.rag_text.tag_config("welcome", foreground="gray", font=("Arial", 10, "italic"))
                self.app.rag_text.tag_add("welcome", "1.0", "9.end")
                
            self.app.after(0, clear_ui)