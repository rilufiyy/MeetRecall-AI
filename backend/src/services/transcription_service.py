import abc
import asyncio
import logging
from pathlib import Path

import assemblyai as aai
import torch
from transformers import pipeline
from pyannote.audio import Pipeline
from huggingface_hub import login
import shutil
import os


from src.core.config import settings
from src.models.schemas import TranscriptionResult, SpeakerSegment

logger = logging.getLogger(__name__)


# Base Provider

class TranscriptionProvider(abc.ABC):
    @abc.abstractmethod
    async def transcribe(self, audio_path: Path, model: str = None) -> TranscriptionResult:
        pass


# Local Whisper Provider

class LocalWhisperProvider(TranscriptionProvider):
    _pipeline = None

    def __init__(self):
        self.model_id = "openai/whisper-small"
        self.device = 0 if torch.cuda.is_available() else -1
        self._initialize_pipeline()

    def _initialize_pipeline(self):
        if LocalWhisperProvider._pipeline is not None:
            return

        logger.info(f"Initializing Whisper model {self.model_id} on device {self.device}")

        try:
            LocalWhisperProvider._pipeline = pipeline(
                "automatic-speech-recognition",
                model=self.model_id,
                chunk_length_s=30,
                device=self.device,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            )
        except Exception as e:
            logger.warning(f"Failed to load Whisper model from cache: {e}")
            
            cache_dir = Path("/root/.cache/huggingface/hub/models--openai--whisper-small")
            if cache_dir.exists():
                logger.warning(f"Deleting corrupted cache at {cache_dir}")
                try:
                    shutil.rmtree(cache_dir, ignore_errors=True)
                except Exception as del_err:
                    logger.error(f"Failed to delete cache dir: {del_err}")

            logger.info("Retrying with force_download=True...")
            try:
                LocalWhisperProvider._pipeline = pipeline(
                    "automatic-speech-recognition",
                    model=self.model_id,
                    chunk_length_s=30,
                    device=self.device,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    model_kwargs={"force_download": True}
                )
            except Exception as e2:
                logger.error(f"Critical error loading Whisper model: {e2}")
                raise e2

    async def transcribe(self, audio_path: Path, model: str = None) -> TranscriptionResult:
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        loop = asyncio.get_running_loop()

        result = await loop.run_in_executor(
            None,
            lambda: LocalWhisperProvider._pipeline(
                str(audio_path),
                return_timestamps=True,
                generate_kwargs={"task": "transcribe"}
            )
        )

        text = result.get("text", "")
        chunks = result.get("chunks", [])

        segments = []
        for chunk in chunks:
            start, end = chunk.get("timestamp", (0.0, 0.0))
            segments.append(
                SpeakerSegment(
                    start_time=float(start or 0.0),
                    end_time=float(end or 0.0),
                    speaker="Unknown",
                    text=chunk["text"].strip()
                )
            )

        if not segments and text:
            segments.append(
                SpeakerSegment(
                    start_time=0.0,
                    end_time=0.0,
                    speaker="Unknown",
                    text=text
                )
            )

        return TranscriptionResult(
            transcript_text=text,
            model_name="Whisper-Small (Local)",
            language="en",
            duration=segments[-1].end_time if segments else 0.0,
            segments=segments
        )


# Pyannote Diarization

class PyannoteDiarization:
    _pipeline = None

    def __init__(self):
        self.model_id = "pyannote/speaker-diarization-3.1"
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.enabled = bool(settings.HUGGINGFACE_TOKEN)

    def _initialize_pipeline(self):
        if PyannoteDiarization._pipeline is not None:
            return

        if not self.enabled:
            logger.warning("HUGGINGFACE_TOKEN missing. Diarization disabled.")
            return

        try:
            login(token=settings.HUGGINGFACE_TOKEN)
            
            # Try loading normally first
            PyannoteDiarization._pipeline = Pipeline.from_pretrained(
                self.model_id
            ).to(self.device)
            
            logger.info("Pyannote loaded successfully.")
            
        except Exception as e:
            logger.warning(f"Failed to load Pyannote: {e}")
            
            cache_dir = Path("/root/.cache/huggingface/hub/models--pyannote--speaker-diarization-3.1")
            if cache_dir.exists():
                logger.warning(f"Deleting corrupted Pyannote cache at {cache_dir}")
                try:
                    shutil.rmtree(cache_dir, ignore_errors=True)
                except Exception as del_err:
                    logger.error(f"Failed to delete Pyannote cache: {del_err}")
            
            try:
                logger.info("Retrying Pyannote load after cache clear...")
                PyannoteDiarization._pipeline = Pipeline.from_pretrained(
                    self.model_id
                ).to(self.device)
            except Exception as e2:
                logger.error(f"Critical error loading Pyannote: {e2}")
                PyannoteDiarization._pipeline = None

    def diarize(self, audio_path: Path):
        self._initialize_pipeline()

        if PyannoteDiarization._pipeline is None:
            return None

        import uuid
        import ffmpeg

        temp_wav = audio_path.with_suffix(f".diarize_{uuid.uuid4()}.wav")

        try:
            (
                ffmpeg
                .input(str(audio_path))
                .output(str(temp_wav), ac=1, ar=16000)
                .overwrite_output()
                .run(quiet=True)
            )
            return PyannoteDiarization._pipeline(str(temp_wav))
        except Exception as e:
            logger.error(f"Diarization failed: {e}")
            return None
        finally:
            if temp_wav.exists():
                temp_wav.unlink()


# Whisper + Diarization Provider
class WhisperSmallWithDiarizationProvider(TranscriptionProvider):
    def __init__(self):
        self.whisper_provider = LocalWhisperProvider()
        self.diarizer = PyannoteDiarization()

    async def transcribe(self, audio_path: Path, model: str = None) -> TranscriptionResult:

        whisper_result = await self.whisper_provider.transcribe(audio_path, model)

        loop = asyncio.get_running_loop()
        diarization = await loop.run_in_executor(
            None,
            lambda: self.diarizer.diarize(audio_path)
        )

        if not diarization:
            whisper_result.model_name = "Whisper-Small + Pyannote (Failed)"
            return whisper_result

        if hasattr(diarization, "speaker_diarization"):
            diarization = diarization.speaker_diarization
        elif hasattr(diarization, "annotation"):
            diarization = diarization.annotation

        try:
            diar_segments = list(diarization.itertracks(yield_label=True))
        except Exception:
            return whisper_result

        new_segments = []

        for w_seg in whisper_result.segments:
            best_speaker = "Unknown"
            max_overlap = 0.0

            for turn, _, speaker in diar_segments:
                overlap = min(w_seg.end_time, turn.end) - max(w_seg.start_time, turn.start)
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_speaker = f"Speaker {speaker}"

            new_segments.append(
                SpeakerSegment(
                    start_time=w_seg.start_time,
                    end_time=w_seg.end_time,
                    speaker=best_speaker,
                    text=w_seg.text
                )
            )

        return TranscriptionResult(
            transcript_text=whisper_result.transcript_text,
            model_name="Whisper-Small + Pyannote 3.1",
            language=whisper_result.language,
            duration=whisper_result.duration,
            segments=new_segments
        )


# AssemblyAI Provider
class AssemblyAIProvider(TranscriptionProvider):

    def __init__(self):
        if not settings.ASSEMBLY_API_KEY:
            logger.warning("ASSEMBLY_API_KEY missing. AssemblyAI disabled.")
            self.transcriber = None
        else:
            aai.settings.api_key = settings.ASSEMBLY_API_KEY
            self.transcriber = aai.Transcriber()

    async def transcribe(self, audio_path: Path, model: str = "universal-3-pro") -> TranscriptionResult:

        if not self.transcriber:
            raise ValueError("AssemblyAI API Key missing.")

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        loop = asyncio.get_running_loop()

        config = aai.TranscriptionConfig(
            speech_models=["universal-3-pro"],
            speaker_labels=True,
            language_detection=True,
            punctuate=True,
            format_text=True,
            entity_detection=True
        )

        transcript = await loop.run_in_executor(
            None,
            lambda: self.transcriber.transcribe(str(audio_path), config)
        )

        if transcript.status == aai.TranscriptStatus.error:
            raise RuntimeError(transcript.error)

        segments = []
        if transcript.utterances:
            for utt in transcript.utterances:
                segments.append(
                    SpeakerSegment(
                        start_time=utt.start / 1000.0,
                        end_time=utt.end / 1000.0,
                        speaker=f"Speaker {utt.speaker}",
                        text=utt.text
                    )
                )
        else:
            segments.append(
                SpeakerSegment(
                    start_time=0.0,
                    end_time=transcript.audio_duration or 0.0,
                    speaker="Unknown",
                    text=transcript.text
                )
            )

        return TranscriptionResult(
            transcript_text=transcript.text,
            model_name=f"AssemblyAI ({model})",
            language=getattr(transcript, "language_code", "en"),
            duration=transcript.audio_duration or 0.0,
            segments=segments
        )


# Orchestrator

class TranscriptionOrchestrator:
    def __init__(self):
        self.providers = {
            "local_whisper": LocalWhisperProvider,
            "whisper_diarization": WhisperSmallWithDiarizationProvider,
            "assemblyai": AssemblyAIProvider,
        }

    async def transcribe(self, audio_path: Path, provider_name: str = "local_whisper", model: str = None) -> TranscriptionResult:

        provider_class = self.providers.get(provider_name.lower())

        if not provider_class:
            provider_class = LocalWhisperProvider

        provider = provider_class()
        return await provider.transcribe(audio_path, model)


transcription_service = TranscriptionOrchestrator()
