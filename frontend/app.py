import streamlit as st
import time
from streamlit_option_menu import option_menu
from utils.api_client import api_client
from utils.transcript_formatter import (
    extract_speaker_names,
    format_transcript_as_dialog,
    assign_user_labels
)

# PAGE CONFIG
st.set_page_config(
    page_title="MeetRecall AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .reportview-container {
        background: #0e1117;
    }
    .main .block-container {
        padding-top: 2rem;
    }
    h1, h2, h3 {
        color: #f0f2f6;
    }
    # Chat bubble styles
    .user-bubble {
        background-color: #2b313e;
        color: #ffffff;
        padding: 10px 15px;
        border-radius: 15px 15px 0 15px;
        max-width: 70%;
        display: inline-block;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    .agent-bubble {
        background-color: #444654;
        color: #ffffff;
        padding: 10px 15px;
        border-radius: 15px 15px 15px 0;
        max-width: 70%;
        display: inline-block;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    .stCard {
        background-color: #262730;
        padding: 20px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# SESSION STATE INIT
if "current_meeting_id" not in st.session_state:
    st.session_state.current_meeting_id = ""

if "meeting_data" not in st.session_state:
    st.session_state.meeting_data = None

if "messages" not in st.session_state:
    st.session_state.messages = []

# SIDEBAR NAVIGATION
with st.sidebar:
    selected = option_menu(
        "MeetRecall AI",
        ["Upload", "Meeting Analysis", "AI Chat"],
        icons=["cloud-upload", "file-text", "chat-dots"],
        menu_icon="cast",
        default_index=0,
    )

# UPLOAD PAGE
if selected == "Upload":
    st.title("Upload Meeting Video")
    st.caption("Powered by AssemblyAI & OpenAI")

    transcription_model = st.selectbox(
        "Choose Transcription Model",
        [
            "AssemblyAI (Universal-3-Pro)",
            "AssemblyAI (Universal-2)",
            "OpenAI (Whisper / GPT-4o Transcribe)"
        ],
        key="transcription_model_select"
    )
    st.caption(f"Selected Provider: {transcription_model}")

    uploaded_file = st.file_uploader(
        "Upload meeting recording (Audio/Video)",
        type=["mp4", "mkv", "mov", "avi", "mp3", "wav", "m4a"]
    )

    if st.button("Start Processing", type="primary"):
        if not uploaded_file:
            st.error("Please upload a file.")
        else:
            with st.spinner("Uploading file..."):
                result = api_client.upload_video(
                    uploaded_file,
                    transcription_model=transcription_model
                )

            if not result or "error" in result:
                st.error(result.get("error", "Upload failed"))
            else:
                st.session_state.current_meeting_id = result["meeting_id"]
                st.session_state.meeting_data = None  # Reset meeting data
                st.success("Upload successful. Redirecting to analysis page...")
                time.sleep(1)
                st.switch_page("pages/1_Meeting_Analysis.py") if "pages" in dir(st) else st.rerun()

# MEETING ANALYSIS PAGE
elif selected == "Meeting Analysis":
    st.title("Meeting Analysis")

    meeting_id = st.text_input(
        "Meeting ID",
        value=st.session_state.current_meeting_id
    )

    # Auto-refresh mechanism with loading indicator
    if meeting_id:
        # Initialize auto-refresh state
        if "auto_refresh_enabled" not in st.session_state:
            st.session_state.auto_refresh_enabled = False
        if "last_fetch_time" not in st.session_state:
            st.session_state.last_fetch_time = 0

        # Fetch data immediately if not in session or if manually triggered
        current_time = time.time()
        should_fetch = (
            st.session_state.meeting_data is None or
            (current_time - st.session_state.last_fetch_time) > 10  # Auto-refresh every 10 seconds
        )

        if should_fetch:
            data = api_client.get_analytics(meeting_id)
            st.session_state.last_fetch_time = current_time

            if not data:
                st.warning("Meeting not found. Please check the Meeting ID.")
                st.session_state.meeting_data = None
            elif "error" in data:
                error_msg = data["error"]
                # Check if it's a 409 Conflict (processing)
                if "409" in error_msg or "Conflict" in error_msg:
                    # Show clean loading UI
                    st.markdown("### Processing Meeting")
                    st.markdown("---")

                    # Progress bar
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    # Animated progress
                    for i in range(100):
                        progress_bar.progress(i + 1)
                        if i < 30:
                            status_text.text("Transcribing audio...")
                        elif i < 70:
                            status_text.text("Analyzing content...")
                        else:
                            status_text.text("Generating insights...")
                        time.sleep(0.05)

                    st.info("Processing in progress. Page will auto-refresh in 10 seconds...")

                    # Enable auto-refresh
                    st.session_state.auto_refresh_enabled = True
                    time.sleep(5)
                    st.rerun()
                else:
                    st.error(f"Error: {error_msg}")
                    st.session_state.meeting_data = None
            else:
                st.session_state.meeting_data = data
                st.session_state.auto_refresh_enabled = False

    # Display meeting data
    data = st.session_state.meeting_data
    if data:
        meta = data.get("metadata", {})
        analytics = data.get("analytics", {})
        transcript_text = data.get("transcript_text", "")
        segments = data.get("transcript_segments", [])

        # Status badge
        status = meta.get("status", "unknown").upper()

        # Only show results if COMPLETED
        if status != "COMPLETED":
            st.markdown("### Processing Meeting")
            st.markdown("---")
            st.info("Your meeting is being processed. This page will auto-refresh until complete.")
            time.sleep(5)
            st.rerun()

        # Show success message
        st.success("Analysis Complete!")
        st.markdown(
            f"""
            **File:** `{meta.get("filename", "-")}`
            **Duration:** `{meta.get("duration", 0):.1f}s`
            **Status:** `{status}`
            """
        )

        # Show analytics
        col1, col2, col3 = st.columns(3)
        col1.metric("Speakers", len(analytics.get("speaker_percentage", {})))
        col2.metric("Topics", len(analytics.get("topics", [])))
        col3.metric("Action Items", len(analytics.get("action_items", [])))

        st.divider()

        tab1, tab2, tab3, tab4 = st.tabs(
            ["Summary", "Action Items", "Topics & Keywords", "Transcript"]
        )

        with tab1:
            st.subheader("Executive Summary")
            st.info(analytics.get("summary", "No summary available."))

        with tab2:
            st.subheader("Action Items")
            action_items = analytics.get("action_items", [])
            if action_items:
                for idx, item in enumerate(action_items):
                    st.checkbox(
                        item.get("text", ""),
                        key=f"action_{idx}_{item.get('text', '')[:20]}"
                    )
            else:
                st.caption("No action items found.")

        with tab3:
            st.subheader("Topics")
            topics = analytics.get("topics", [])
            if topics:
                for t in topics:
                    st.markdown(f"- **{t.get('name')}**")
            else:
                st.caption("No topics found.")

            st.subheader("Keywords")
            keywords = analytics.get("keywords", [])
            if keywords:
                st.write(", ".join(keywords))
            else:
                st.caption("No keywords found.")

        with tab4:
            st.subheader("Transcript")

            # Extract speaker names from transcript
            speaker_mapping = extract_speaker_names(transcript_text)

            # Format transcript as dialog
            if segments:
                # Assign user labels to unnamed speakers
                updated_segments = assign_user_labels(segments, speaker_mapping)
                formatted_transcript = format_transcript_as_dialog(updated_segments, speaker_mapping)

                st.text_area(
                    "Dialog Format",
                    formatted_transcript,
                    height=500,
                    help="Transcript with speaker identification and timestamps"
                )
            else:
                # Fallback to plain text
                st.text_area("Full Transcript", transcript_text, height=500)

# AI CHAT PAGE (RAG)
elif selected == "AI Chat":
    st.title("Chat with Your Meeting")

    meeting_id = st.text_input(
        "Meeting ID",
        value=st.session_state.current_meeting_id
    )

    # Render chat history with custom bubbles
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(
                    f'''
                    <div style="display: flex; justify-content: flex-end; margin-bottom: 10px;">
                        <div class="user-bubble">{msg["content"]}</div>
                    </div>
                    ''', 
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f'''
                    <div style="display: flex; justify-content: flex-start; margin-bottom: 10px;">
                        <div class="agent-bubble">{msg["content"]}</div>
                    </div>
                    ''', 
                    unsafe_allow_html=True
                )

    # User input
    if prompt := st.chat_input("Ask about the meeting..."):
        if not meeting_id:
            st.warning("Please enter a Meeting ID.")
        else:
            # Append execution logic
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Re-render to show new user message immediately
            with chat_container:
                st.markdown(
                    f'''
                    <div style="display: flex; justify-content: flex-end; margin-bottom: 10px;">
                        <div class="user-bubble">{prompt}</div>
                    </div>
                    ''', 
                    unsafe_allow_html=True
                )

            with st.spinner("Thinking..."):
                response = api_client.chat_with_meeting(meeting_id, prompt)

            answer = response.get("answer", "No response.")
            st.session_state.messages.append({"role": "assistant", "content": answer})
            
            # Re-render to show new assistant message
            with chat_container:
                 st.markdown(
                    f'''
                    <div style="display: flex; justify-content: flex-start; margin-bottom: 10px;">
                        <div class="agent-bubble">{answer}</div>
                    </div>
                    ''', 
                    unsafe_allow_html=True
                )
            
            # Force rerender to keep history in sync on next interactions
            st.rerun()