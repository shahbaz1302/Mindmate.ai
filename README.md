# 🧠 Mindmate.ai — Digital Wellness Companion & Mental Health Assistant

[![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-Flask-green.svg)](https://flask.palletsprojects.com/)
[![AI Engine](https://img.shields.io/badge/AI-Google%20Gemini%202.5%20Flash-orange.svg)](https://ai.google.dev/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](#license)

**Mindmate.ai** is an intelligent, compassionate digital wellness companion designed to provide a safe, non-judgmental space for users to track their emotional well-being, engage in voice/text conversations, complete personalized mental health assessments, and receive actionable wellness advice.

Powered by **Google Gemini 2.5 Flash**, Mindmate delivers contextual responses with full conversation memory while strictly adhering to ethical AI wellness boundaries.

---

## 🔗 Project URL & Access

- **Live Deployed Application**: [https://mindmateai.pythonanywhere.com](https://mindmateai.pythonanywhere.com)

---

## ✨ Key Features

- **🔐 Multi-User Authentication & Data Isolation**:
  - Secure registration and login with Werkzeug password hashing (`scrypt`).
  - Isolated per-user JSON data storage ensuring chat history, test results, and emotion logs remain private.
  - Automatic session management and 30-minute idle session refresh.

- **😊 Real-time Emotion Detection**:
  - Automatically analyzes user inputs to classify primary emotions (_Sadness, Anxiety, Stress, Joy, Calm, Frustration, Anger, Loneliness, Grief, Fear, Neutral, Hope, Overwhelmed_) along with confidence scores.

- **💬 AI Companion with Contextual Memory**:
  - Retains history of previous conversations (last 10 chats / 20 messages) to provide continuous, non-repetitive, empathetic support.
  - Multi-language support including English and Hinglish options.
  - Built-in strict safety guardrails preventing clinical diagnosis or off-topic diversions.

- **🧪 Dynamic & Personalized Mental Health Assessments**:
  - Dynamically generates 5 personalized questions (open-ended and MCQ) tailored to the user's current emotional state and chat history.
  - AI-driven risk assessment (_Low / Moderate / High_), key insights, strengths, and areas for attention.
  - Instant PDF export of assessment reports using `jsPDF`.

- **💡 Smart Wellness & Activity Suggestions**:
  - Delivers gentle, actionable, one-step wellness activities in real-time based on the user's detected emotional state.

- **📝 Instant Chat Summarization**:
  - Generates comprehensive summaries of user conversations to track emotional trends, discussed topics, and positive takeaways over time.

- **🎙️ Voice Input & Speech Synthesis**:
  - Integrated browser Web Speech API for voice-to-text input and natural text-to-speech AI response playback.

- **🎨 Modern Interactive UI/UX**:
  - Animated liquid canvas backgrounds, dark/light theme toggles, glassmorphic cards, responsive sidebars, and smooth micro-animations.

---

## 🛠️ Tech Stack & Technologies

### **Backend Framework & Core**

- **Python 3.8+**: Application logic & server runtime.
- **Flask**: Lightweight web framework managing routes, sessions, context hooks (`g`), and JSON API responses.
- **Werkzeug Security**: Hashed password management (`generate_password_hash`, `check_password_hash`).

### **Artificial Intelligence & NLP**

- **Google Generative AI SDK (`google-generativeai`)**: Interaction with Google Gemini API.
- **Gemini 2.5 Flash Model (`gemini-2.5-flash`)**: High-speed model for emotion detection, chat completion, question generation, and test analysis.

### **Frontend & User Interface**

- **HTML5 & Vanilla CSS3**: Custom CSS variables, Glassmorphism design system, CSS 3D transforms, and keyframe animations.
- **Vanilla JavaScript (ES6+)**: Async fetch requests, Web Speech API integration, DOM manipulation, canvas graphics.
- **External CDN Libraries**:
  - `jsPDF` (v2.5.1): Client-side PDF generation for test reports.
  - Boxicons & Google Fonts (`Inter`, `Poppins`).

### **Data Storage**

- **JSON File-Based Storage**:
  - `users.json`: Credentials, user registry, and creation timestamps.
  - `user_data/user_<id>.json`: Isolated user profiles, chat history logs, current emotion state, test result history, and preferences.

---

## 📁 Project Structure

```
Mindmate_2.4/
├── app.py                  # Main Flask backend application & Gemini API integration
├── users.json              # Central user authentication store (hashed passwords)
├── user_data/              # Isolated per-user data directory
│   ├── user_1.json         # Per-user profile, chat context history, and test logs
│   ├── user_2.json
│   └── ...
├── static/                 # Static web assets
│   ├── style.css           # Global custom stylesheet
│   └── js/                 # Client-side scripts
├── templates/              # Jinja2 HTML View Templates
│   ├── login.html          # Auth page with sliding Login/Register card
│   ├── index.html          # Main landing dashboard with emotion input & canvas visuals
│   ├── chat.html           # Real-time AI chat interface with sidebar, voice & activity tools
│   ├── test.html           # Dynamic mental health assessment & PDF generator page
│   ├── test2.html          # Secondary assessment view template
│   └── help.html           # User guide, FAQ, and team credits page
└── README.md               # Project documentation
```

---

## 🚀 Getting Started & Setup Guide

### 1. Prerequisites

Ensure you have **Python 3.8 or higher** installed on your system.

### 2. Clone or Navigate to the Project Directory

```bash
cd Mindmate_2.4
```

### 3. Install Required Dependencies

Install Flask and the Google Generative AI SDK:

```bash
pip install flask werkzeug google-generativeai
```

### 4. Configure Google Gemini API Key

By default, `app.py` includes a fallback API key for testing, but you can set your own key via an environment variable:

**On Windows (PowerShell):**

```powershell
$env:GEMINI_API_KEY="your_actual_gemini_api_key_here"
```

**On Windows (CMD):**

```cmd
set GEMINI_API_KEY=your_actual_gemini_api_key_here
```

**On Linux / macOS:**

```bash
export GEMINI_API_KEY="your_actual_gemini_api_key_here"
```

### 5. Run the Application

Start the Flask development server:

```bash
python app.py
```

### 6. Access the Application

Open your web browser and navigate to:

```
http://127.0.0.1:5000
```

---

## 📡 API Endpoints Overview

| Method | Endpoint              | Description                                              | Auth Required |
| :----- | :-------------------- | :------------------------------------------------------- | :-----------: |
| `GET`  | `/`                   | Renders the Login / Register view                        |      ❌       |
| `POST` | `/login`              | Authenticates user & initializes session                 |      ❌       |
| `POST` | `/register`           | Registers a new user account                             |      ❌       |
| `GET`  | `/logout`             | Clears user session and redirects to login               |      ❌       |
| `GET`  | `/index`              | Renders the main dashboard page                          |      ✅       |
| `POST` | `/search`             | Detects emotion from query & returns initial AI response |      ✅       |
| `GET`  | `/chat`               | Renders the main chat window                             |      ✅       |
| `POST` | `/chat_response`      | Sends user message & receives Gemini contextual response |      ✅       |
| `GET`  | `/get_initial_reply`  | Fetches initial/welcome message for chat session         |      ✅       |
| `POST` | `/summarize_chat`     | Generates AI summary of current chat history             |      ✅       |
| `POST` | `/suggest_activity`   | Provides personalized wellness activity recommendation   |      ✅       |
| `GET`  | `/test`               | Renders the Mental Health Test page                      |      ✅       |
| `GET`  | `/generate_questions` | Dynamically generates 5 personalized test questions      |      ✅       |
| `POST` | `/submit_test`        | Analyzes submitted test answers & saves report           |      ✅       |
| `GET`  | `/help`               | Renders user guide & team credits                        |      ✅       |
| `GET`  | `/health`             | System health check and user statistics                  |      ❌       |

---

## ⚡ Development Team & Credits

| Name                  | Role & Responsibility             |
| :-------------------- | :-------------------------------- |
| **Shivansh Sharma**   | Backend Architecture & Team Lead  |
| **Mohd Shahbaz Khan** | Frontend Developer & UI/UX Design |
| **Yuvraj Singh**      | Data Handling & Storage Isolation |
| **Mansi Gupta**       | Testing, QA & Supporter           |

---

## ⚠️ Disclaimer

**Mindmate.ai** is an AI-assisted digital wellness companion designed for self-reflection and emotional support. It is **not** a substitute for professional medical care, diagnosis, or clinical therapy. If you or someone you know is experiencing a mental health crisis, please consult a licensed mental health professional or contact local crisis emergency helplines.

---

© 2025 **Mindmate.ai**. All rights reserved.
