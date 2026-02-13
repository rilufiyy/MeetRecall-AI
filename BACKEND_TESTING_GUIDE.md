# Backend Testing Guide - FastAPI

Complete guide for testing the MeetRecall AI Transcription backend API using Swagger UI.

---

## Access Swagger UI

```
http://localhost:8001/docs
```

---

## 1. Health Check - Verify Backend Ready

**Endpoint:** `GET /health`

**Steps:**
1. Expand endpoint `GET /health`
2. Click **"Try it out"**
3. Click **"Execute"**

**Expected Response (200 OK):**
```json
{
  "status": "healthy"
}
```

---

## 2. Upload File - Start Processing

**Endpoint:** `POST /api/v1/upload`

**Steps:**
1. Expand endpoint `POST /api/v1/upload`
2. Click **"Try it out"**
3. **Upload file:**
   - Click "Browse" on `file` parameter
   - Select: `[REC] Key Meeting - Engineering (Public Stream).mp3`
4. **Select provider:**
   - Dropdown `provider`: choose `assemblyai` or `openai`
5. Click **"Execute"**

**Expected Response (202 Accepted):**
```json
{
  "message": "Upload successful. Processing started.",
  "meeting_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "status": "PROCESSING",
  "provider": "assemblyai"
}
```

**IMPORTANT:** Copy the `meeting_id` for next steps

---

## 3. Check Status - Monitor Processing

**Endpoint:** `GET /api/v1/analysis/{meeting_id}`

**Steps:**
1. Expand endpoint `GET /api/v1/analysis/{meeting_id}`
2. Click **"Try it out"**
3. **Paste meeting_id** from step 2
4. Click **"Execute"**

**Possible Responses:**

**A. Still Processing (409 Conflict):**
```json
{
  "detail": "Analysis not ready yet. Current status: PROCESSING"
}
```
- Wait 30-60 seconds
- Execute again (retry)

**B. Completed (200 OK):**
```json
{
  "id": "meeting-id",
  "metadata": {
    "filename": "meeting.mp3",
    "duration": 1234.5,
    "status": "COMPLETED",
    "provider": "assemblyai"
  },
  "transcript_text": "Full transcript...",
  "transcript_segments": [...],
  "analytics": {
    "summary": "Meeting summary...",
    "action_items": [...],
    "key_questions": [...],
    "topics": [...],
    "keywords": [...],
    "speaker_percentage": {...}
  }
}
```

---

## 4. Get Transcript Only

**Endpoint:** `GET /api/v1/transcript/{meeting_id}`

**Steps:**
1. Expand endpoint `GET /api/v1/transcript/{meeting_id}`
2. Click **"Try it out"**
3. **Paste meeting_id**
4. Click **"Execute"**

**Expected Response (200 OK):**
```json
{
  "meeting_id": "meeting-id",
  "transcript": "Full transcript text",
  "segments": [
    {
      "start_time": 0.0,
      "end_time": 5.5,
      "speaker": "Speaker A",
      "text": "Hello everyone..."
    }
  ]
}
```

---

## 5. List All Meetings

**Endpoint:** `GET /api/v1/meetings`

**Steps:**
1. Expand endpoint `GET /api/v1/meetings`
2. Click **"Try it out"**
3. Click **"Execute"**

**Expected Response (200 OK):**
```json
[
  {
    "id": "meeting-1",
    "metadata": {...},
    "analytics": {...}
  },
  {
    "id": "meeting-2",
    "metadata": {...},
    "analytics": {...}
  }
]
```

Sorted by newest first.

---

## 6. AI Chat (RAG) - Ask Questions About Meeting

**Endpoint:** `POST /api/v1/ask/{meeting_id}`

**Steps:**
1. Expand endpoint `POST /api/v1/ask/{meeting_id}`
2. Click **"Try it out"**
3. **Paste meeting_id**
4. **Edit Request body:**
   ```json
   {
     "query": "What are the main action items from this meeting?"
   }
   ```
5. Click **"Execute"**

**Expected Response (200 OK):**
```json
{
  "answer": "Based on the meeting transcript, the main action items are: 1) Create development and quality key reviews..."
}
```

---

## 7. Test Different Queries

Try these example queries:

**Query 1: Speaker Analysis**
```json
{"query": "Who spoke the most in this meeting?"}
```

**Query 2: Topics**
```json
{"query": "What topics were discussed?"}
```

**Query 3: Decisions**
```json
{"query": "Summarize the key decisions made"}
```

**Query 4: Next Steps**
```json
{"query": "What are the next steps?"}
```

**Query 5: Concerns**
```json
{"query": "Were there any disagreements or concerns raised?"}
```

---

## Complete Testing Flow

```
1. Health Check (/health)
   |
   v OK

2. Upload File (/upload)
   |
   v Get meeting_id

3. Check Status (/analysis/{id})
   |
   v 409 Conflict -> Wait 30s
   |
   v Execute again
   |
   v 409 Conflict -> Wait 30s
   |
   v Execute again
   |
   v 200 OK -> COMPLETED

4. Get Full Analysis (/analysis/{id})
   |
   v View summary, action items, topics

5. Get Transcript (/transcript/{id})
   |
   v View dialog format

6. Ask Questions (/ask/{id})
   |
   v Test various queries

7. List All Meetings (/meetings)
   |
   v View all uploaded meetings
```

---

## Monitor Backend Logs

**Terminal Command:**
```bash
docker logs -f meetrecall-backend
```

**Expected Log Sequence:**
```
INFO: Starting AssemblyAI transcription for /app/uploads/xxxxx.mp3
INFO: AssemblyAI transcription completed successfully
INFO: Starting analytics generation...
INFO: Analytics generation completed
INFO: Indexing 45 chunks for meeting xxxxx
INFO: Indexing complete for xxxxx
INFO: Meeting processing completed with status: COMPLETED
```

---

## Testing Scenarios

### Scenario 1: AssemblyAI Provider
1. Upload with `provider=assemblyai`
2. Wait approximately 2-4 minutes
3. Verify speaker labels: "Speaker A", "Speaker B"
4. Check speaker_percentage exists

### Scenario 2: OpenAI Provider
1. Upload with `provider=openai`
2. Wait approximately 1-3 minutes
3. Verify speaker labels: "Unknown" (no diarization)
4. Check transcript accuracy

### Scenario 3: Compare Results
1. Upload same file twice (once AssemblyAI, once OpenAI)
2. Compare analytics quality
3. Compare processing time
4. Compare transcript accuracy

---

## Troubleshooting

**Error 500 Internal Server Error:**
```bash
# Check logs
docker logs meetrecall-backend --tail 50
```

**Error 404 Not Found:**
- Meeting ID is incorrect
- Meeting not uploaded yet

**Error 409 Conflict:**
- NORMAL - Meeting still processing
- Wait and try again

**Error 401/403:**
- API keys invalid
- Check backend/.env file
- Verify OpenAI and AssemblyAI API keys

---

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /health | Health check |
| POST | /api/v1/upload | Upload audio/video file |
| GET | /api/v1/analysis/{id} | Get full analysis |
| GET | /api/v1/transcript/{id} | Get transcript only |
| GET | /api/v1/meetings | List all meetings |
| POST | /api/v1/ask/{id} | Ask questions (RAG) |

---

## Database Connection (DBeaver)

If you want to inspect the database directly:

- Host: localhost
- Port: 5434
- Database: meetrecall_db
- Username: meetrecall
- Password: meetrecall_pass

**Tables:**
- `meetings` - Meeting metadata
- `analytics` - Analysis results
- `transcript_chunks` - RAG embeddings

---

Last Updated: February 2026
