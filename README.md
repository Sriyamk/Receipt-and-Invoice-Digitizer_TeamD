# Receipt & Invoice Digitizer

An AI-powered web application that digitizes, stores, and analyzes receipts and invoices using OCR technology. Built with Flask and PaddleOCR, with a built-in AI chatbot assistant for querying your expense data.

---

##  Features

- **AI-Powered OCR** — Automatically extracts vendor, invoice ID, amount, and date from uploaded receipt images/PDFs using PaddleOCR
- **User Authentication** — Register, login, forgot/reset password, and Google OAuth sign-in
- **AI Chatbot** — Ask questions about your receipts and expenses via a floating chat widget
- **Admin Dashboard** — View and manage all users and their uploaded bills
- **Multi-language Support** — UI available in English, Hindi (हिंदी), Telugu (తెలుగు), Tamil (தமிழ்), Kannada (ಕನ್ನಡ), and Malayalam (മലയാളം)
- **Dark / Light Theme** — Persistent theme toggle across all pages
- **Bill History** — View, search, and manage your digitized receipts
- **Secure Storage** — All data stored in SQLite with hashed passwords

---

##  Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask |
| OCR Engine | PaddleOCR |
| AI Chatbot | Ollama (local LLM server) |
| Database | SQLite (`users.db`) |
| Frontend | HTML5, CSS3, Vanilla JS |
| Auth | Session-based + Google OAuth 2.0 |
| i18n | i18next (client-side) |
| Email | SMTP (password reset) |

---

##  Project Structure

```
receipt-digitizer/
├── .gitignore
├── Final_Presentation.pdf
│
├── backend/
│   ├── app.py                    # Main Flask application & API routes
│   ├── ocr.py                    # PaddleOCR integration & receipt parsing
│   ├── generate_translations.py  # i18n translation file generator
│   ├── chat_intents.json         # Chatbot intent data
│   ├── start.sh                  # Server startup script
│   ├── requirements.txt          # Python dependencies
│   ├── users.db                  # SQLite database (auto-created)
│   ├── .env                      # Environment variables (not committed)
│   └── uploads/                  # User-uploaded receipt files (not committed)
│
└── frontend/
    ├── static/
    │   ├── back_drop/            # UI assets (icons, background images)
    │   └── i18n/                 # Language JSON files (en, hi, te, ta, kn, ml)
    │
    └── templates/                # Jinja2 HTML templates
        ├── landing.html
        ├── login_page.html
        ├── register_page.html
        ├── home.html
        ├── bill_digitizer.html
        ├── chatbot.html
        ├── admin_dashboard.html
        ├── admin_user_receipts.html
        ├── forgotpassword.html
        └── reset_password.html
```

---

##  Getting Started

### Prerequisites

- Python 3.8+
- pip
- (Recommended) A virtual environment
- [Ollama](https://ollama.com) — for the AI chatbot (installed system-wide, not via pip)

### 1. Clone the repository

```bash
git clone https://github.com/Sriyamk/Receipt-and-Invoice-Digitizer_TeamD.git
cd Receipt-and-Invoice-Digitizer_TeamD
```

### 2. Create and activate a virtual environment

```bash
python -m venv paddle_env
# On macOS/Linux:
source paddle_env/bin/activate
# On Windows:
paddle_env\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up Ollama (AI Chatbot)

Ollama runs as a local server and is installed separately — not via pip.

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh
```

Then pull your model and start the server:

```bash
ollama pull mistral
ollama serve              # starts Ollama at http://localhost:11434
```

> Make sure Ollama is running before starting the Flask app, otherwise the chatbot will not respond.

### 5. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values (see [Environment Variables](#environment-variables) below).

### 6. Run the app

```bash
bash start.sh
# or directly:
python app.py
```

The app will be available at `http://localhost:5000`

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` and configure:

```env
# Flask
SECRET_KEY=your-secret-key-here
FLASK_ENV=development

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com

# Email (for password reset)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

---

##  API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/login` | User login |
| POST | `/api/register` | User registration |
| POST | `/api/logout` | Logout |
| POST | `/api/google-login` | Google OAuth login |
| POST | `/api/forgot-password` | Send password reset email |
| POST | `/api/reset-password` | Reset password |
| POST | `/api/upload` | Upload and digitize a receipt |
| POST | `/api/chat` | Chat with the AI assistant |
| GET | `/api/receipts` | Get user's receipts |

---

## 🌍 Adding a New Language

1. Add the language code to `generate_translations.py`
2. Run `python generate_translations.py` to generate the JSON file
3. Add the language button to `login_page.html`'s language menu

---

##  Security Notes

- Passwords are hashed before storage — never stored in plain text
- The `uploads/` folder and `users.db` are excluded from version control
- Keep your `.env` file private — never commit it
- Google Client ID is public-facing (safe to commit), but keep your client secret in `.env`

---

## 📄 License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

##  Team D

This project was built as part of the **Infosys Springboard** program.

| Name | GitHub |
|---|---|
| Sriya Muthukumar | [@Sriyamk](https://github.com/Sriyamk) |
| Shaik Mastan | [@skmdmastan07](https://github.com/skmdmastan07) |
| Thrishala Koduru | [@Thrishala2006](https://github.com/Thrishala2006) |
| Atul Chandra | [@Droid-47](https://github.com/Droid-47) |
| Rithwik Pachipala | [@Rithwik-18](https://github.com/Rithwik-18) |


---

##  Acknowledgements

- [Infosys Springboard](https://infyspringboard.onwingspan.com) — for the learning platform and project opportunity
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) — open-source OCR engine
- [Ollama](https://ollama.com) — local LLM server powering the AI chatbot (Mistral)
- [i18next](https://www.i18next.com) — internationalization framework

---

© 2026 Team D — Infosys Springboard






