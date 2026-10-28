# Cyberbullying Detection System - Nish Institution

A web application built with **Python (Flask)** and **Hugging Face Transformers (BERT)** for detecting cyberbullying in student messages and managing incident reports at Nish Institution.

## Features
- **AI Message Detection**: Checks student messages and replies for cyberbullying using a pre-trained BERT model (`Davephoenix/bert-bullying-detector`).
- **Student, Lecturer & Admin Portals**:
  - Students can register, send messages, post in discussions, and report abusive messages.
  - Lecturers can post course announcements and monitor discussions.
  - Admins can review flagged messages, warn/restrict/ban accounts, and print user/incident reports.
- **Database Support**: Uses a lightweight **SQLite** database (`cyberbullying.db`) that is created automatically on startup.
- **M-Pesa Donations**: Safaricom Daraja STK Push donations.

---

## How to Run the Project

### 1. Clone the repository
```bash
git clone https://github.com/anishcherono/Cyberbulling-Detection-System.git
cd Cyberbulling-Detection-System
```

### 2. Install dependencies and start the application
```bash
pip install -r requirements.txt
python app.py
```

When you run `python app.py`, it automatically sets up the SQLite database (`cyberbullying.db`), creates the default admin account, and opens the portal at `http://127.0.0.1:5000/`.

---

## Login Details

### 1. Administrator Account (`@admin.nish.edu`)
- **URL**: `http://127.0.0.1:5000/admin/login`
- **Email**: `admin@admin.nish.edu`
- **Password**: `admin123`

### 2. Lecturer Accounts (`@lecturers.nish.edu`) — 4 Lecturers
- **URL**: `http://127.0.0.1:5000/lecturer-login`
- **Password (all lecturers)**: `lecturer123`
- **Emails**:
  - `kelvin.kiprop@lecturers.nish.edu` (`LEC-2026-0001` - Dr. Kelvin Kiprop)
  - `grace.wanjiku@lecturers.nish.edu` (`LEC-2026-0002` - Prof. Grace Wanjiku)
  - `samuel.omondi@lecturers.nish.edu` (`LEC-2026-0003` - Dr. Samuel Omondi)
  - `amina.hassan@lecturers.nish.edu` (`LEC-2026-0004` - Dr. Amina Hassan)

### 3. Student Accounts (`@students.nish.edu`) — 10 Students
- **URL**: `http://127.0.0.1:5000/student-login`
- **Password (all students)**: `student123`
- **Emails**:
  - `anish.cherono@students.nish.edu` (`STU-2026-0001`)
  - `brian.otieno@students.nish.edu` (`STU-2026-0002`)
  - `cynthia.chebet@students.nish.edu` (`STU-2026-0003`)
  - `david.mwangi@students.nish.edu` (`STU-2026-0004` - Warning Issued)
  - `esther.mutua@students.nish.edu` (`STU-2026-0005`)
  - `felix.kamau@students.nish.edu` (`STU-2026-0006` - Temporarily Restricted)
  - `gloria.achieng@students.nish.edu` (`STU-2026-0007`)
  - `hassan.abdi@students.nish.edu` (`STU-2026-0008`)
  - `irene.njoroge@students.nish.edu` (`STU-2026-0009`)
  - `kevin.kipchumba@students.nish.edu` (`STU-2026-0010` - Banned)

---

## Author
**Anish Cherono**
