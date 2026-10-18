# Coding Standards & Structure

## Backend (FastAPI)
The backend is organized into simple, single-purpose files:
- `main.py`: Contains all API routes (endpoints), including the `/api/rag/ask` endpoint.
- `models.py`: Defines the PostgreSQL database tables.
- `schemas.py`: Defines the data formats expected in requests and responses (Pydantic).
- `database.py`: Manages the database connection and sessions.
- `auth.py`: Handles password hashing, verification, and token generation.
- `vector_store.py`: Manages FAISS vector index creation, document chunking, and similarity search.
- `rag.py`: Implements the multi-step Agentic RAG controller (intent analysis, query decision, sufficiency check, re-query logic, guarded response generation).
- `knowledge_docs/`: Storage folder for approved product manuals and technical documentation.

## Frontend (ReactJS)
The frontend is built with React and Vite. It is organized as follows:
- `src/App.jsx`: Main routing configuration using `react-router-dom`.
- `src/index.css`: Global design system and premium CSS styles.
- `src/components/`: Reusable UI elements (Header, Footer, ProductAssistant widget).
- `src/pages/`: Full screen views (Login, Register, Profile, Home, Cart, ProductDetails).

## General Rules & RAG Guidelines
- **Keep it Simple & Modular:** Keep the implementation simple and easy to read. Build only what is required.
- **Strict Grounding:** Do not invent answers or hallucinate. Base answers exclusively on retrieved manual text.
- **Clear Fallbacks:** If the manual doesn't contain the answer, explicitly state: "This information is not available in the approved product manuals."
- **Prompt Injection Defense:** Sanitize user input and treat retrieved text strictly as passive context data. Never reveal internal prompts, system instructions, or secret keys.
- **Consistent APIs:** Ensure API endpoints have clear names (e.g., `/api/rag/ask`) and return standard HTTP status codes.
