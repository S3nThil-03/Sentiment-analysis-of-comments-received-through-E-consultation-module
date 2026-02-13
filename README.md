# Sentiment-analysis-of-comments-received-through-E-consultation-module
# MyGov Comments Dashboard (Real-Time)

## 📸 Dashboard Preview

Real-time analytics dashboard visualizing multilingual public feedback and sentiment insights.

![MyGov Comments Dashboard](dashboard-preview.png)

---

**MyGov Comments Dashboard** is a real-time analytics application that fetches public comments from MyGov discussion pages, performs multilingual language detection and sentiment analysis, and visualizes insights through an interactive dashboard.

The system updates every 5 seconds and enables filtering, searching, and exporting clean CSV reports using a modern **React + Flask** architecture.

---

## 🚀 Features

* Fetches public comments from MyGov discussion pages (Site 1 & Site 2)
* Real-time refresh every **5 seconds**
* Multilingual **language detection**
* Sentiment classification:

  * Positive
  * Negative
  * Neutral
  * Unknown
* Interactive charts & word cloud visualization
* Live comment feed
* Advanced filter & search
* Export comments as CSV
* Stores processed data for fallback & audit

---

## 🧠 Tech Stack

### Backend

* Python
* Flask
* BeautifulSoup
* Requests
* LangDetect

### Frontend

* React (Create React App)
* Recharts
* PapaParse

### Optional AI Enhancement

* Google Gemini (`google-generativeai`)

---

## 📁 Project Structure

```
hackthon/
│
├── backend/
│   └── app.py
│
├── dashboard/
│   ├── src/
│   ├── public/outputs/
│   └── package.json
│
├── outputs/
├── requirements.txt
└── run_scraper.py
```

---

## ⚙️ Prerequisites

* Python **3.10+**
* Node.js **18+**
* npm

---

## ▶️ Run the Project

### Backend

```powershell
python backend\app.py
```

Runs at: http://localhost:5000

### Frontend

```powershell
cd dashboard
npm start
```

Runs at: http://localhost:3000

---

## 📊 Output Files

* Processed sentiment data stored as CSV
* Used for fallback & audit purposes

---

## 📝 Notes

* Real-time updates every 5 seconds
* Supports multilingual sentiment detection
* Designed for analytics, research, and civic insights
