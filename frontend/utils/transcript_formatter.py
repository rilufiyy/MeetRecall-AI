import re
from typing import List, Dict

def extract_speaker_names(transcript_text: str) -> Dict[str, str]:
    """
    Extract speaker names from transcript text using pattern matching.
    Returns a mapping of generic speaker labels to actual names.
    """
    speaker_mapping = {}

    # Common patterns for name mentions
    # "Hi, this is John", "My name is Sarah", "I'm David", etc.
    patterns = [
        r"(?:Hi|Hello|Hey),?\s+(?:this is|I'm|I am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"(?:My name is|I'm|I am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"Thanks?,?\s+([A-Z][a-z]+)",
        r"([A-Z][a-z]+),?\s+(?:you|do you|can you)",
    ]

    names_found = []
    for pattern in patterns:
        matches = re.findall(pattern, transcript_text)
        names_found.extend(matches)

    # Remove duplicates while preserving order
    unique_names = []
    seen = set()
    for name in names_found:
        name = name.strip()
        if name and name not in seen and len(name.split()) <= 2:  
            seen.add(name)
            unique_names.append(name)

    # Map to speaker labels (limited to first 10 unique names found)
    for i, name in enumerate(unique_names[:10], start=1):
        speaker_mapping[f"Speaker {chr(64 + i)}"] = name  
        speaker_mapping[f"Speaker {i}"] = name  

    return speaker_mapping


def format_transcript_as_dialog(segments: List[Dict], speaker_mapping: Dict[str, str] = None) -> str:
    """
    Format transcript segments as a dialog with speaker names and timestamps.

    Args:
        segments: List of transcript segments with speaker, text, start_time, end_time
        speaker_mapping: Optional mapping of generic speaker labels to actual names

    Returns:
        Formatted transcript string
    """
    if not segments:
        return "No transcript available."

    if speaker_mapping is None:
        speaker_mapping = {}

    formatted_lines = []
    current_speaker = None
    current_text_parts = []
    current_start = None

    for segment in segments:
        speaker = segment.get("speaker", "Unknown")
        text = segment.get("text", "").strip()
        start_time = segment.get("start_time", 0)
        end_time = segment.get("end_time", 0)

        if not text:
            continue

        # Get actual name if available, otherwise use generic label
        display_speaker = segment.get("display_speaker")
        if not display_speaker:
            display_speaker = speaker_mapping.get(speaker, speaker)

        # If speaker changes, flush previous speaker's text
        if current_speaker != display_speaker:
            if current_speaker and current_text_parts:
                combined_text = " ".join(current_text_parts)
                timestamp = format_timestamp(current_start)
                formatted_lines.append(f"[{timestamp}] {current_speaker}:\n{combined_text}")

            current_speaker = display_speaker
            current_text_parts = [text]
            current_start = start_time
        else:
            current_text_parts.append(text)

    # Flush last speaker's text
    if current_speaker and current_text_parts:
        combined_text = " ".join(current_text_parts)
        timestamp = format_timestamp(current_start)
        formatted_lines.append(f"[{timestamp}] {current_speaker}:\n{combined_text}")

    return "\n\n".join(formatted_lines)


def format_timestamp(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def assign_user_labels(segments: List[Dict], speaker_mapping: Dict[str, str] = None) -> List[Dict]:
    """
    Assign user_1, user_2, etc. labels to speakers that don't have names.

    Args:
        segments: List of transcript segments
        speaker_mapping: Known speaker name mappings

    Returns:
        Updated segments with user labels
    """
    if speaker_mapping is None:
        speaker_mapping = {}

    # Find all unique speakers
    speakers_seen = set()
    for segment in segments:
        speaker = segment.get("speaker", "Unknown")
        speakers_seen.add(speaker)

    # Assign user labels to unmapped speakers
    user_counter = 1
    final_mapping = speaker_mapping.copy()

    for speaker in sorted(speakers_seen):
        if speaker not in final_mapping and speaker != "Unknown":
            final_mapping[speaker] = f"Speaker_{user_counter:02d}"
            user_counter += 1

    # Update segments with final mapping
    updated_segments = []
    for segment in segments:
        updated_segment = segment.copy()
        speaker = segment.get("speaker", "Unknown")
        updated_segment["display_speaker"] = final_mapping.get(speaker, speaker)
        updated_segments.append(updated_segment)

    return updated_segments
