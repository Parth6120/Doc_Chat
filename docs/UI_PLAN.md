# Production-Grade Modular UI — Implementation Plan

## Overview

Add a production-grade Next.js frontend to the Multi-Doc-Chat backend while keeping the two layers fully decoupled. The backend can be replaced or extended without touching the frontend, and the frontend can be swapped entirely without touching a single backend file.

---

## Modularity Contract

The entire separation is enforced by one rule:

> **The frontend only communicates with the backend through `frontend/lib/api.ts`.
> Zero backend URLs or fetch calls exist anywhere else in the frontend.**

If the UI is ever replaced:
1. Delete the `frontend/` folder.
2. Create `frontend-v2/` with a new `lib/api.ts` targeting the same REST contract.
3. Backend remains untouched.

---

## Phase 1 — Backend Additions (Minimal)

Only 3 files change. No existing logic is modified — only additions.

### 1.1 `main.py` — CORS Middleware

Add `CORSMiddleware` to allow the Next.js dev server and production domain to call the API.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # extend for production
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 1.2 `multi_doc_chat/src/generation/rag_chain.py` — Add `stream()` Method

Alongside the existing `generate()` method, add an async generator `stream()` that:
1. Retrieves docs from Pinecone (same as `generate`).
2. Loads chat history (same as `generate`).
3. Calls `llm.astream(messages)` and `yield`s each token chunk as it arrives.
4. After the full response is assembled, saves the exchange to MongoDB.
5. Yields a final sentinel `{"done": True, "sources": [...]}`.

```python
async def stream(self, query: str, session_id: str, user_id: str):
    # retrieve + build messages (same as generate)
    ...
    full_answer = ""
    async for chunk in self.llm.astream(messages):
        token = chunk.content
        full_answer += token
        yield {"token": token}
    await self.history_manager.save_exchange(session_id, query, full_answer)
    yield {"done": True, "sources": sources}
```

### 1.3 `routes/chat_router.py` — Add `POST /chat/stream` (SSE Endpoint)

Uses `fastapi.responses.StreamingResponse` with `text/event-stream` content type.

Each event:
```
data: {"token": "Hello"}\n\n
data: {"token": " world"}\n\n
data: {"done": true, "sources": ["doc.pdf"]}\n\n
```

This is the primary production chat endpoint. `POST /chat/query` remains as a non-streaming fallback.

---

## Phase 2 — Frontend (Next.js 15)

Located at `frontend/` — an independent project with its own `package.json`.

### Tech Stack

| Concern        | Choice                          | Reason                                              |
|----------------|---------------------------------|-----------------------------------------------------|
| Framework      | Next.js 15 (App Router)         | Production standard, SSR capable, file-based routing |
| Language       | TypeScript                      | Type safety across the API boundary                 |
| Styling        | Tailwind CSS + shadcn/ui        | Pre-built accessible components, fast to build with |
| State          | Zustand                         | Lightweight, no boilerplate, works well with streaming |
| Markdown       | react-markdown + remark-gfm     | Renders LLM markdown output correctly               |
| HTTP / SSE     | Native `fetch` + `ReadableStream` | No extra library needed for SSE token streaming   |

### Folder Structure

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout — providers, fonts, global CSS
│   ├── page.tsx                # Redirect to /chat
│   └── chat/
│       └── page.tsx            # Main page — Sidebar + ChatWindow side by side
│
├── components/
│   ├── layout/
│   │   └── Sidebar.tsx         # Session list, new-session button, doc uploader
│   ├── chat/
│   │   ├── ChatWindow.tsx      # Scrollable message list, auto-scrolls to bottom
│   │   ├── MessageBubble.tsx   # Human / AI bubble with react-markdown rendering
│   │   ├── QueryInput.tsx      # Textarea + send button, disabled while streaming
│   │   └── SourceBadge.tsx     # Pill showing source document filename
│   └── documents/
│       └── DocumentUploader.tsx # Drag-and-drop, file-type guard, upload progress
│
├── lib/
│   └── api.ts                  # *** THE MODULARITY BOUNDARY ***
│                               # Every backend call lives here.
│                               # Fully typed inputs and outputs.
│
├── hooks/
│   ├── useChat.ts              # Calls api.streamChat(), writes tokens to store
│   ├── useSessions.ts          # Session CRUD (create, list, delete)
│   └── useDocuments.ts         # Document upload flow
│
├── store/
│   └── chatStore.ts            # Zustand: activeSession, messages[], isStreaming
│
├── types/
│   └── index.ts                # Message, Session, Source, ChatRequest, etc.
│
├── next.config.ts              # API proxy rewrite (avoids CORS issues in dev)
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

### API Client Contract (`frontend/lib/api.ts`)

```typescript
// The backend base URL — only reference in the entire frontend
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Sessions
createSession(userId: string): Promise<{ session_id: string }>
listSessions(userId: string): Promise<Session[]>
deleteSession(sessionId: string): Promise<void>

// Documents
ingestDocument(file: File, userId: string): Promise<{ chunks_vectorized: number }>

// Chat — non-streaming fallback
queryChat(req: ChatRequest): Promise<ChatResponse>

// Chat — streaming (primary)
streamChat(
  req: ChatRequest,
  onToken: (token: string) => void,
  onDone: (sources: string[]) => void
): Promise<void>
```

Swapping the backend: change `NEXT_PUBLIC_API_URL` in `.env.local`. Zero code changes needed.

---

## Data Flow — Streaming Chat

```
User types → QueryInput (sends on Enter / button click)
  → useChat hook
      → api.streamChat()
          → POST /chat/stream (SSE)
              ← { token: "Hello" }  → appended to message in Zustand store
              ← { token: " world" } → re-renders ChatWindow in real time
              ← { done: true, sources: [...] } → SourceBadges shown, isStreaming = false
```

---

## File Change Summary

| File | Action |
|------|--------|
| `main.py` | Add `CORSMiddleware` |
| `routes/chat_router.py` | Add `POST /chat/stream` SSE endpoint |
| `multi_doc_chat/src/generation/rag_chain.py` | Add `stream()` async generator |
| `frontend/` | Create entire Next.js project |
| `frontend/lib/api.ts` | Typed API client (modularity boundary) |
| `frontend/store/chatStore.ts` | Zustand store |
| `frontend/hooks/useChat.ts` | Streaming chat hook |
| `frontend/hooks/useSessions.ts` | Session management hook |
| `frontend/hooks/useDocuments.ts` | Document upload hook |
| `frontend/components/**` | All UI components |

---

## Verification Checklist

- [ ] `uvicorn main:app --reload` starts without errors
- [ ] `cd frontend && npm run dev` starts without errors
- [ ] Upload a PDF → confirm `chunks_vectorized` returned and shown in UI
- [ ] Create a session → session appears in sidebar
- [ ] Send a query → tokens stream into the chat bubble in real time
- [ ] Refresh the page → chat history is preserved (loaded from MongoDB)
- [ ] Delete a session → disappears from sidebar, messages cleared
- [ ] Change `NEXT_PUBLIC_API_URL` → frontend adapts with zero code changes
- [ ] No backend URL string appears anywhere outside `frontend/lib/api.ts`
