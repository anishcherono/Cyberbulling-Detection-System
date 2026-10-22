# Cyberbullying Detection System - Nish Institution

A web application built with **Python (Flask)** and **Hugging Face Transformers (BERT)** for detecting cyberbullying in student messages and managing incident reports at Nish Institution.

## Features
- **AI Message Detection**: Checks student messages and replies for cyberbullying using a pre-trained BERT model (`Davephoenix/bert-bullying-detector`).
- **Student, Lecturer & Admin Portals**:
  - Students can register, send messages, post in discussions, and report abusive messages.
  - Lecturers can post course announcements and monitor discussions.
  - Admins can review flagged messages, warn/restrict/ban accounts, and print user/incident reports.
- **Database Support**: Uses **MySQL** when available and automatically falls back to a local **SQLite** database (`cyberbullying.db`) if MySQL is not running.
- **M-Pesa Donations**: Supports Safaricom Daraja STK Push donations (with sandbox test fallback).

---

## How to Run the Project

### 1. Clone the repository
```bash
git clone https://github.com/anishcherono/Cyberbulling-Detection-System.git
cd Cyberbulling-Detection-System
```

### 2. Start the application
```bash
python app.py
```

When you run `python app.py`, it automatically creates the `.venv` virtual environment (if not already created), installs the packages in `requirements.txt`, sets up the database tables, and opens the portal at `http://127.0.0.1:5000/`.

---

## Login Details

### Default Admin Account
- **URL**: `http://127.0.0.1:5000/admin/login`
- **Email**: `admin@nish.edu`
- **Password**: `admin123`

### Student Registration
- **URL**: `http://127.0.0.1:5000/student-login`
- Use an email ending with `@students.nish.edu` and one of these student IDs:
  - `STU-2026-0001`
  - `STU-2026-0002`
  - `STU-2026-0003`
  - `STU-2026-0004`
  - `STU-2026-0005`

### Lecturer Registration
- **URL**: `http://127.0.0.1:5000/lecturer-login`
- Use an email ending with `@lecturers.nish.edu`.

---

## Running Tests
```bash
python -m unittest discover -s . -p "test_*.py"
```

## Author
**Anish Cherono**
