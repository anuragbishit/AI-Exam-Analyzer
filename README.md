# 🧠 AI Exam Analyzer

<p align="center">
  <img src="assets/logo.svg" alt="AI Exam Analyzer Logo" width="130"/>
</p>

<h3 align="center">AI-Powered Online Examination & Performance Analysis Platform</h3>

<p align="center">
  Create Exams • Generate AI Questions • Analyze Performance • Improve Learning
</p>

<p align="center">

![Python](https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge\&logo=python\&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Web%20Framework-000000?style=for-the-badge\&logo=flask\&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge\&logo=sqlite\&logoColor=white)
![Gemini](https://img.shields.io/badge/Google%20Gemini-AI-4285F4?style=for-the-badge\&logo=google\&logoColor=white)

</p>

---

## 📌 About

**AI Exam Analyzer** is an intelligent web-based examination platform built with **Python Flask, SQLite, Google Gemini AI and Plotly**.

It allows students to create and attempt exams, generate questions using AI, analyze their results, identify weak topics and track their learning performance.

---

## ✨ Features

* 🤖 **AI Question Generation** — Generate MCQs using Google Gemini AI.
* 📝 **Manual Exams** — Create customized examinations.
* 🔐 **User Authentication** — Registration, login and session management.
* 📊 **Performance Dashboard** — View scores and examination history.
* 📈 **Interactive Analytics** — Visualize examination performance.
* 🎯 **Weak Topic Detection** — Identify topics requiring improvement.
* 💡 **Recommendations** — Get learning recommendations based on performance.
* 🧾 **Exam History** — Track previous examination attempts.

---

## 🏗️ How It Works

```text
                         ┌───────────────┐
                         │    Student    │
                         └───────┬───────┘
                                 │
                                 ▼
                      ┌───────────────────┐
                      │   Register/Login   │
                      └─────────┬─────────┘
                                │
                                ▼
                      ┌───────────────────┐
                      │     Dashboard     │
                      └─────────┬─────────┘
                                │
                         ┌──────┴──────┐
                         │             │
                         ▼             ▼
                 ┌──────────────┐  ┌──────────────┐
                 │  Manual Exam │  │    AI Exam   │
                 └──────┬───────┘  └──────┬───────┘
                        │                 │
                        │                 ▼
                        │        ┌────────────────┐
                        │        │   Gemini AI    │
                        │        │ Question Gen.  │
                        │        └───────┬────────┘
                        │                │
                        └────────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │  Attempt Exam │
                         └───────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │ Submit Answers│
                         └───────┬───────┘
                                 │
                                 ▼
                      ┌────────────────────┐
                      │ Result Calculation │
                      └─────────┬──────────┘
                                │
                                ▼
                      ┌────────────────────┐
                      │ Performance        │
                      │ Analysis           │
                      └─────────┬──────────┘
                                │
                         ┌──────┴──────┐
                         │             │
                         ▼             ▼
                  ┌────────────┐ ┌────────────────┐
                  │Weak Topics │ │ Recommendations│
                  └─────┬──────┘ └───────┬────────┘
                        │                │
                        └────────┬───────┘
                                 │
                                 ▼
                       ┌──────────────────┐
                       │ Track Progress   │
                       └──────────────────┘
```

---

## 🛠️ Tech Stack

| Technology       | Purpose                   |
| ---------------- | ------------------------- |
| 🐍 Python        | Backend programming       |
| 🌐 Flask         | Web framework             |
| 🗄️ SQLite       | Database                  |
| 🤖 Google Gemini | AI question generation    |
| 📊 Plotly        | Data visualization        |
| 🎨 HTML/CSS      | Frontend                  |
| ⚡ JavaScript     | Client-side functionality |
| 🧩 Jinja2        | HTML templating           |

---

## 📂 Project Structure

```text
AI-Exam-Analyzer/
│
├── app.py
├── database.db
├── requirements.txt
│
├── static/
│   ├── css/
│   ├── js/
│   └── images/
│
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── signup.html
│   ├── dashboard.html
│   ├── exam_setup.html
│   └── exam.html
│
└── assets/
    └── logo.svg
```

---

## 🧩 Core Modules

### 🔐 Authentication

Handles user registration, login, logout and session management.

### 🤖 AI Exam Generator

Uses **Google Gemini AI** to generate topic-based multiple-choice questions.

### 📝 Exam Engine

Manages exam creation, question presentation, answer submission and scoring.

### 📊 Performance Analyzer

Processes examination results and generates meaningful performance insights.

### 🎯 Weak Topic Analyzer

Identifies topics where the student has comparatively lower performance.

### 📈 Analytics Dashboard

Displays scores, examination history and performance information through visual analytics.

---

## 🎯 Project Highlights

```text
AI-Powered Question Generation
          +
Online Examination
          +
Performance Analytics
          +
Weak Topic Detection
          +
Personalized Recommendations
          ↓
    Intelligent Learning
```

The goal is to transform a traditional **exam → score** system into an:

**Exam → Analysis → Recommendation → Improvement** workflow.

---

## 🔒 Security

**Never commit your Gemini API key to GitHub.**

Use environment variables for sensitive credentials and add them to `.gitignore`.

```gitignore
.env
venv/
__pycache__/
*.pyc
```

If an API key has already been exposed publicly, revoke it and generate a new one.

---

## 🔮 Future Improvements

* Admin dashboard
* Leaderboard
* Timer-based examinations
* PDF result reports
* AI answer explanations
* AI-generated study plans
* Advanced analytics
* Cloud deployment

---

## 👨‍💻 Author

### Anurag Kumar Singh

**B.Tech Computer Science Engineering**

Built with ❤️ using **Python, Flask, SQLite and Google Gemini AI**.

---

<p align="center">

⭐ **If you like this project, consider giving it a star!**

### AI Exam Analyzer

**Learn • Practice • Analyze • Improve**

</p>
