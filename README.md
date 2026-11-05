# Nish Institution - Cyberbullying Detection & Prevention System

A web application developed for final year project to detect and moderate cyberbullying messages across student communication channels and campus discussion forums.

## Overview
- **Message Filtering**: Uses a pre-trained BERT text classification model (`Davephoenix/bert-bullying-detector`) to detect harassment, insults, and toxic messages.
- **Role-Based Portals**:
  - **Student Portal**: Send direct messages, view discussions, report incidents, and receive notifications.
  - **Lecturer Portal**: Broadcast announcements and review student interactions.
  - **Admin Dashboard**: Review AI-flagged alerts, manage account restrictions, and generate printable reports.
- **Tech Stack**: Python (Flask), MySQL, HTML/CSS, Hugging Face Transformers.

---

## Setup & Installation

### 1. Requirements
- Python 3.10+
- MySQL Server (running locally on port 3306)

### 2. Configure Environment (`.env`)
Create or edit your `.env` file with your MySQL credentials:
```env
DATABASE_URL=mysql://root:your_password@localhost:3306/Cyberbulling_system
FLASK_SECRET_KEY=your_secret_key
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Application
```bash
python app.py
```
The server will start at `http://127.0.0.1:5000/`.

---

## Demo Accounts

For demonstration and testing purposes:

| Role | Email | Password |
| :--- | :--- | :--- |
| **Administrator** | `admin@admin.nish.edu` | `admin123` |
| **Lecturer** | `kelvin.kiprop@lecturers.nish.edu` | `lecturer123` |
| **Student** | `anish.cherono@students.nish.edu` | `student123` |

*New student and lecturer accounts can also be created via the registration pages.*

---

## Author
**Anish Cherono**  
Nish Institution
