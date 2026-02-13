import abc
import asyncio
import logging
from typing import Optional
from pathlib import Path
import assemblyai as aai
from openai import OpenAI
from src.core.config import settings
from src.models.schemas import TranscriptionResult, SpeakerSegment

logger = logging.getLogger(__name__)

class TranscriptionProvider(abc.ABC):
    @abc.abstractmethod
    async def transcribe(self, audio_path: Path, model: str = None) -> TranscriptionResult:
        pass

class OpenAIProvider(TranscriptionProvider):
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model_name = "whisper-1"

    async def transcribe(self, audio_path: Path, model: str = None) -> TranscriptionResult:
        logger.info(f"Starting OpenAI Whisper transcription for {audio_path}")
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        try:
            # Run blocking I/O in executor
            loop = asyncio.get_event_loop()
            transcript = await loop.run_in_executor(
                None,
                lambda: self._transcribe_sync(audio_path)
            )
            
            segments = []
            if hasattr(transcript, 'segments') and transcript.segments:
                for seg in transcript.segments:
                    segments.append(SpeakerSegment(
                        start_time=seg.start,
                        end_time=seg.end,
                        speaker="Unknown", # OpenAI Whisper base doesn't support diarization natively in this endpoint
                        text=seg.text
                    ))
            
            if not segments and transcript.text:
                 segments.append(SpeakerSegment(
                     start_time=0.0,
                     end_time=transcript.duration,
                     speaker="Unknown",
                     text=transcript.text
                 ))
            
            return TranscriptionResult(
                transcript_text=transcript.text,
                model_name="OpenAI (Whisper-1)", # Updated to match UI label
                language=transcript.language,
                duration=transcript.duration,
                segments=segments
            )

        except Exception as e:
            logger.error(f"OpenAI Transcription failed: {e}")
            raise

    def _transcribe_sync(self, audio_path: Path):
        with open(audio_path, "rb") as audio_file:
            return self.client.audio.transcriptions.create(
                model=self.model_name,
                file=audio_file,
                response_format="verbose_json"
            )

class AssemblyAIProvider(TranscriptionProvider):
    def __init__(self):
        if not settings.ASSEMBLY_API_KEY:
             logger.warning("ASSEMBLY_API_KEY missing. AssemblyAI provider disabled.")
             self.transcriber = None
        else:
             aai.settings.api_key = settings.ASSEMBLY_API_KEY
             self.transcriber = aai.Transcriber()

    async def transcribe(self, audio_path: Path, model: str = "universal-3-pro") -> TranscriptionResult:
        if not self.transcriber:
             raise ValueError("AssemblyAI API Key missing.")

        logger.info(f"Starting AssemblyAI transcription for {audio_path} with model {model}")
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        try:
            # Use specific model instead of fallback array
            if model == "universal-2":
                speech_models = ["universal-2"]
            else:  # Default to universal-3-pro
                speech_models = ["universal-3-pro"]

            config = aai.TranscriptionConfig(
                speech_models=speech_models,
                speaker_labels=True,
                language_detection=True,
                punctuate=True,
                format_text=True
            )
            
            # Run blocking I/O in executor
            loop = asyncio.get_event_loop()
            transcript = await loop.run_in_executor(
                None,
                lambda: self.transcriber.transcribe(str(audio_path), config)
            )

            if transcript.status == aai.TranscriptStatus.error:
                raise Exception(f"AssemblyAI failed: {transcript.error}")

            segments = []
            if transcript.utterances:
                for utt in transcript.utterances:
                    segments.append(SpeakerSegment(
                        start_time=utt.start / 1000.0,
                        end_time=utt.end / 1000.0,
                        speaker=f"Speaker {utt.speaker}",
                        text=utt.text
                    ))
            else:
                 segments.append(SpeakerSegment(
                     start_time=0.0,
                     end_time=transcript.audio_duration if transcript.audio_duration else 0.0,
                     speaker="Unknown",
                     text=transcript.text
                 ))

            language_code = getattr(transcript, 'json_response', {}).get('language_code', 'en')

            # Format model name for display
            if model == "universal-2":
                model_display = "AssemblyAI (Universal-2)"
            else:
                model_display = "AssemblyAI (Universal-3-Pro)"

            return TranscriptionResult(
                transcript_text=transcript.text,
                model_name=model_display,
                language=language_code,
                duration=transcript.audio_duration if transcript.audio_duration else 0.0,
                segments=segments
            )

        except Exception as e:
            logger.error(f"AssemblyAI Transcription failed: {e}")
            raise

class TranscriptionOrchestrator:
    def __init__(self):
        self.providers = {
            "openai": OpenAIProvider,
            "assemblyai": AssemblyAIProvider
        }

    async def transcribe(self, audio_path: Path, provider_name: str = "assemblyai", model: str = "universal-3-pro") -> TranscriptionResult:
        # Auto-detect or fallback
        if provider_name == "assemblyai" and not settings.ASSEMBLY_API_KEY:
            logger.warning("AssemblyAI key missing. Falling back to OpenAI Whisper.")
            provider_name = "openai"

        provider_class = self.providers.get(provider_name.lower())
        if not provider_class:
            logger.warning(f"Unknown provider '{provider_name}'. Defaulting to AssemblyAI (or fallback).")
            if settings.ASSEMBLY_API_KEY:
                provider_class = AssemblyAIProvider
            else:
                provider_class = OpenAIProvider

        # Instantiate and transcribe
        try:
            provider = provider_class()
            return await provider.transcribe(audio_path, model)
        except Exception as e:
            logger.error(f"Transcription with {provider_name} failed: {e}")
            raise e

transcription_service = TranscriptionOrchestrator()
