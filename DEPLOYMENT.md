# E-Commerce Application Deployment Guide (Render)

This document outlines the deployment strategy for the E-Commerce application using [Render](https://render.com/).

## 1. What Needs to be Deployed
The application consists of three main components plus the local FAISS knowledge store:
1. **PostgreSQL Database:** The central database storing all products, categories, users, and orders.
2. **FastAPI Backend & Agentic RAG:** The Python web server providing the REST endpoints and the Agentic RAG knowledge assistant.
3. **FAISS Vector Index:** Vectorized representations of approved product manuals (`backend/knowledge_docs/`) loaded in-memory or persisted in the backend.
4. **ReactJS Frontend:** The user interface built with Vite and React.

---

## 2. PostgreSQL Database Connection
Render provides a managed PostgreSQL service.
- **Creation:** Create a new "PostgreSQL" instance in the Render dashboard.
- **Configuration:** Render will automatically generate a secure `Internal Database URL` (used by the backend) and an `External Database URL`.
- **Action:** Copy the `Internal Database URL` (e.g., `postgres://user:password@hostname:5432/dbname`). You will need this for the backend configuration.

---

## 3. FastAPI Backend Deployment
The backend acts as a Render "Web Service".

- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port 10000`
- **Root Directory:** `backend` 
- **Environment Variables Required:**
  - `DATABASE_URL`: Set this to the Internal Database URL provided by Render's PostgreSQL database.
  - `SECRET_KEY`: A secure random string for JWT authentication.
  - `GROQ_API_KEY`: API key for Groq inference (model: llama-3.3-70b-versatile).
  - `GROQ_MODEL` (Optional): Target Groq model name (defaults to `llama-3.3-70b-versatile`).
  - `GEMINI_API_KEY` (Optional): Alternative fallback generative AI API key.
- **Backend URL:** Render will generate a public URL for your backend (e.g., `https://ecommerce-backend-xyz.onrender.com`). Save this URL.

---

## 4. ReactJS Frontend Deployment
The frontend is deployed as a Render "Static Site", which serves highly optimized HTML/JS/CSS files.

- **Build Command:** `npm install && npm run build`
- **Publish Directory:** `dist`
- **Root Directory:** `frontend`
- **Environment Variables Required:**
  - `VITE_API_URL` (or updating your `api.js` directly): Set this to the **Backend URL** generated in the previous step (e.g., `https://ecommerce-backend-xyz.onrender.com/api`).
- **Frontend URL:** Render will generate a public URL for your frontend (e.g., `https://ecommerce-frontend-xyz.onrender.com`). This is the link you give to your customers.

---

## 5. Required Environment / Configuration Values
| Component | Variable Name | Example Value | Purpose |
|-----------|--------------|---------------|---------|
| **Backend** | `DATABASE_URL` | `postgres://user:pass@host/db` | Allows FastAPI to connect to PostgreSQL. |
| **Backend** | `SECRET_KEY` | `supersecretkey123` | Used to sign and verify JWT tokens. |
| **Backend** | `GROQ_API_KEY` | `gsk_...` | Enables Groq LLM inference (llama-3.3-70b-versatile) for the assistant. |
| **Backend** | `GROQ_MODEL` | `llama-3.3-70b-versatile` | (Optional) Configurable Groq model name. |
| **Backend** | `GEMINI_API_KEY` | `AIzaSy...` | (Optional) Alternative fallback generative AI API key. |
| **Frontend**| `VITE_API_URL` | `https://ecommerce-backend-xyz.onrender.com/api` | Points the React application to backend APIs. |

---

## 6. Frontend URL and Backend URL
- **Frontend URL (Customer Facing):** This is where shoppers and admins will go in their browser. It communicates with the backend behind the scenes.
- **Backend URL (API Server):** This URL is hidden from normal users. The frontend uses it to fetch and update data.

---

## 7. How to Start and Restart the Application
- **Initial Start:** Once you connect your GitHub repository to Render and configure the settings above, Render will automatically build and start the application.
- **Restarting/Updating:** 
  - Render has auto-deploy enabled by default. Every time you push new code to your `main` branch, Render will automatically rebuild and restart the affected services.
  - You can manually trigger a restart by clicking **"Manual Deploy"** -> **"Clear build cache & deploy"** inside the specific service on your Render dashboard.

---

## 8. How to Check Whether the Deployed Application is Working
Follow these steps to run a final End-to-End test on the live URLs:
1. **Database Check:** Ensure the backend deployment logs don't show connection errors.
2. **Backend Health Check:** Visit the backend URL directly (e.g., `https://ecommerce-backend-xyz.onrender.com/health`). It should return a successful JSON message.
3. **Frontend Test:** 
   - Open your public Frontend URL.
   - Register a new customer account.
   - Browse the store and verify products are loading from the database.
   - Add an item to the cart and complete a checkout.
   - Test the Product Knowledge Assistant: Ask a question about a product and ensure it responds with grounded answers from the indexed manuals.
   - If no errors pop up and the order appears in your history, the deployment is fully operational.
