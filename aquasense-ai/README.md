# AquaSense AI

**AquaSense AI** is a complete, production-ready IoT + Web platform designed for real-time water quality monitoring. It supports the mission of providing safe drinking water through smart sensing, AI-driven insights, and an intuitive user dashboard.

## Features

- **Real-time Monitoring**: Tracks pH, TDS (Total Dissolved Solids), Turbidity, Temperature, **Air Quality (MQ135)**, and **Rain Status**.
- **Glassmorphism UI**: A stunning, modern dashboard with animated backgrounds, interactive charts, and real-time sensor cards.
- **AI Chatbot**: Context-aware assistant to help users understand their water quality.
- **Alert Engine**: Multi-level thresholds (Safe, Warning, Critical) with real-time notifications for all sensors.
- **IoT Integration**: Ready-to-use Arduino/ESP32 sketch for seamless data transmission.
- **Automation**: Automatic data retrieval every minute and monthly data cleanup.
- **Reports**: Weekly email subscription system for automated quality reporting.
- **WQI Calculation**: Integrated Water Quality Index for a quick health overview.

## Technology Stack

- **Backend**: Python Flask, SQLAlchemy, APScheduler
- **Database**: SQLite (Production-ready for scale-up to PostgreSQL)
- **Frontend**: Vanilla HTML5, CSS3 (Glassmorphism), JavaScript (ES6+)
- **Charts**: Chart.js
- **Environment**: Python-dotenv for configuration

## Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd aquasense-ai
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   - Rename `.env.template` to `.env`
   - Update `SECRET_KEY` and SMTP settings for email reports.

4. **Run the Application**:
   ```bash
   python app.py
   ```
   The dashboard will be available at `http://127.0.0.1:5000`.

## API Documentation

- `GET /api/current`: Get the latest water quality reading (including Air & Rain).
- `POST /api/data`: Endpoint for IoT devices to send real-time sensor data.
- `GET /api/history/<days>`: Get readings for the past X days.
- `GET /api/alerts/active`: Retrieve all currently active alerts.
- `POST /api/alerts/acknowledge`: Acknowledge an alert by ID.
- `POST /api/chatbot`: Interact with the AI assistant.
- `POST /api/subscribe`: Subscribe an email for weekly reports.
- `GET /api/stats`: Get dashboard statistics (24h averages).

## Market Context

- **Jal Jeevan Mission**: Designed to support large-scale rural water monitoring.
- **Scalable**: Supports multi-device tracking with unique `device_id`.
- **Global Impact**: Water quality monitoring is a projected $8.5B market by 2030.

## License

This project is licensed under the MIT License.
