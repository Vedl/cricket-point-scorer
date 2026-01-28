# Cricket Point Scorer 🏏

An advanced, aesthetic web application to calculate Fantasy Cricket points based on Cricbuzz scorecards. Features a role-based scoring system that ensures fairness between Batsmen, Bowlers, and All-rounders.

![Frontend Preview](https://via.placeholder.com/800x400?text=App+Preview) 
*(Add a screenshot of your app here!)*

## ✨ Features

- **Role-Based Scoring**: Intelligent point calculation that adapts rules based on player roles (e.g., Bowlers are exempt from low strike-rate penalties).
- **Aesthetic UI**: A stunning Dark Mode interface built with React, Tailwind CSS, and Glassmorphism effects.
- **Fairness Logic**:
    - **Cumulative Bonuses**: Run bonuses (30, 50, 100) stack for high rewards.
    - **Power Hitting Rewards**: Special bonuses for Strike Rates > 200 and > 250.
    - **Deflated Scoring**: Calibrated so >100 points is very hard (Test/IPL level difficulty).
- **Live Scraping**: Fetches real-time data directly from Cricbuzz URLs.

## 🛠️ Tech Stack

- **Backend**: Python, FastAPI, BeautifulSoup4
- **Frontend**: React, Vite, Tailwind CSS, Lucide Icons

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- Node.js & npm

### Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/YOUR_USERNAME/cricket-point-scorer.git
    cd cricket-point-scorer
    ```

2.  **Setup Backend**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Setup Frontend**
    ```bash
    cd frontend
    npm install
    ```

### Running the App

1.  **Start Backend** (from root)
    ```bash
    python backend/app.py
    ```
2.  **Start Frontend** (from `frontend/` directory)
    ```bash
    npm run dev
    ```
3.  Open `http://localhost:5173` and paste a match URL!

## 📝 License

MIT
