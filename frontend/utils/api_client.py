import requests
import os

class APIClient:
    def __init__(self):
        self.base_url = os.getenv("BACKEND_URL", "http://localhost:8001/api/v1")

    def upload_video(self, file_obj, transcription_model="AssemblyAI (Universal-3-Pro)"):
        """
        Uploads a video file to the backend with selected transcription model.
        Returns: { 'meeting_id': '...', 'status': 'processing' }
        """
        url = f"{self.base_url}/upload"
        # Determine MIME type based on extension
        filename = file_obj.name
        mime_type = "video/mp4" # Default fallback
        if filename.lower().endswith(".mp3"):
            mime_type = "audio/mpeg"
        elif filename.lower().endswith(".wav"):
           mime_type = "audio/wav"
        elif filename.lower().endswith(".m4a"):
           mime_type = "audio/mp4"

        files = {"file": (filename, file_obj, mime_type)}

        # Map friendly name to backend provider and model
        provider = "assemblyai"
        model = "universal-3-pro"  # Default

        if "OpenAI" in transcription_model:
            provider = "openai"
            model = "whisper-1"
        elif "Universal-2" in transcription_model:
            provider = "assemblyai"
            model = "universal-2"
        elif "Universal-3-Pro" in transcription_model:
            provider = "assemblyai"
            model = "universal-3-pro"

        data = {"provider": provider, "model": model}
        
        try:
            response = requests.post(url, files=files, data=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    def get_analytics(self, meeting_id):
        """
        Fetches the meeting analysis (Summary, Actions, Transcript, etc.)
        Returns:
            - dict with meeting data if completed
            - {"error": "409 Conflict"} if still processing
            - None if not found
        """
        url = f"{self.base_url}/analysis/{meeting_id}"
        try:
            response = requests.get(url)
            if response.status_code == 404:
                return None
            elif response.status_code == 409:
                return {"error": "409 Conflict: Meeting still processing"}
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

    def chat_with_meeting(self, meeting_id, query):
        """
        Sends a RAG query to the backend.
        """
        url = f"{self.base_url}/ask/{meeting_id}"
        data = {"query": query}
        try:
            response = requests.post(url, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}

api_client = APIClient()
