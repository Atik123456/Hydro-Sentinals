import os
import random
import logging
import atexit
from datetime import datetime, timezone
from flask import Flask, jsonify, request, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from google import genai

# Load environment variables
load_dotenv()

# Configure Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

client = genai.Client(api_key=GEMINI_API_KEY)
chatbot_model_id = 'models/gemini-2.5-flash'  # Use 2.5 Flash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///aqua_v3.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class WaterReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False)
    ph = db.Column(db.Float, nullable=False)
    tds = db.Column(db.Float, nullable=False)
    turbidity = db.Column(db.Float, nullable=False)
    temperature = db.Column(db.Float, nullable=False)
    humidity = db.Column(db.Float, nullable=True)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    air_quality = db.Column(db.Float, nullable=True)
    rain = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        try:
            ts = self.timestamp.isoformat() + 'Z' if self.timestamp else "N/A"
            return {
                'device_id': self.device_id,
                'ph': round(float(self.ph if self.ph is not None else 7.0), 2),
                'tds': round(float(self.tds if self.tds is not None else 0.0), 2),
                'turbidity': round(float(self.turbidity if self.turbidity is not None else 0.0), 2),
                'temperature': round(float(self.temperature if self.temperature is not None else 20.0), 2),
                'humidity': round(float(self.humidity if self.humidity is not None else 0.0), 1),
                'air_quality': round(float(self.air_quality if self.air_quality is not None else 0.0), 2),
                'rain': self.rain or "Unknown",
                'lat': float(self.lat if self.lat is not None else 40.7128),
                'lng': float(self.lng or -74.0060),
                'timestamp': ts
            }
        except Exception as e:
            logger.error(f"Error in to_dict: {e}")
            return {'error': 'serialization error'}

@app.route('/')
def index(): 
    return render_template('dashboard.html')

@app.route('/api/current')
def current():
    try:
        r = WaterReading.query.order_by(WaterReading.timestamp.desc()).first()
        return jsonify(r.to_dict()) if r else (jsonify({'error': 'no data'}), 404)
    except Exception as e:
        logger.error(f"Error in /api/current: {e}")
        return jsonify({'error': str(e)}), 500

def sync_to_thingspeak(data):
    """Helper to sync sensor data to ThingSpeak channel."""
    try:
        ts_key = os.getenv('THINGSPEAK_API_KEY')
        if not ts_key:
            return
            
        import requests
        url = "https://api.thingspeak.com/update"
        params = {
            "api_key": ts_key,
            "field1": data.get('ph'),
            "field2": data.get('tds'),
            "field3": data.get('temp'),
            "field4": data.get('turbidity'),
            "field5": data.get('humidity'),
            "field6": data.get('mq135') or data.get('air_quality')
        }
        res = requests.post(url, params=params, timeout=5)
        if res.status_code == 200:
            logger.info(f"ThingSpeak sync successful, entry ID: {res.text}")
        else:
            logger.warning(f"ThingSpeak sync failed: {res.status_code}")
    except Exception as e:
        logger.error(f"Error syncing to ThingSpeak: {e}")

@app.route('/api/data', methods=['POST'])
def receive_data():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # API Key Validation
        api_key = data.get('api_key')
        if not api_key or api_key != os.getenv('API_KEY'):
            logger.warning(f"Unauthorized data submission attempt with key: {api_key}")
            return jsonify({'error': 'Unauthorized'}), 401
        
        new_reading = WaterReading(
            device_id=data.get('device_id', 'ESP32_DEV'),
            ph=data.get('ph', 7.0),
            tds=data.get('tds', 0.0),
            turbidity=data.get('turbidity', 0.0),
            temperature=data.get('temp', 0.0),
            humidity=data.get('humidity', 0.0),
            air_quality=data.get('mq135', 0.0),
            rain=data.get('rain', 'No Data'),
            lat=data.get('lat', 40.7128),
            lng=data.get('lng', -74.0060)
        )
        db.session.add(new_reading)
        db.session.commit()
        
        # Sync to ThingSpeak
        sync_to_thingspeak(data)
        
        return jsonify({'status': 'success', 'message': 'Data received'}), 201
    except Exception as e:
        logger.error(f"Error in /api/data: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/map/data')
def map_data():
    all_r = WaterReading.query.order_by(WaterReading.timestamp.desc()).limit(50).all()
    devs = {}
    for r in all_r:
        if r.device_id not in devs: 
            devs[r.device_id] = r.to_dict()
    return jsonify(list(devs.values()))

@app.route('/api/thingspeak/latest')
def thingspeak_latest():
    """Proxy endpoint to fetch the latest entry from ThingSpeak."""
    try:
        channel_id = os.getenv('THINGSPEAK_CHANNEL_ID')
        read_key = os.getenv('THINGSPEAK_READ_KEY')
        
        if not channel_id or channel_id == 'YOUR_CHANNEL_ID_HERE':
            return jsonify({'error': 'ThingSpeak Channel ID not configured'}), 400
            
        import requests
        url = f"https://api.thingspeak.com/channels/{channel_id}/feeds/last.json?api_key={read_key}"
        res = requests.get(url, timeout=5)
        
        if res.status_code == 200:
            data = res.json()
            # Map ThingSpeak fields back to our sensor format
            mapped_data = {
                'ph': data.get('field1'),
                'tds': data.get('field2'),
                'temperature': data.get('field3'),
                'turbidity': data.get('field4'),
                'humidity': data.get('field5'),
                'air_quality': data.get('field6'),
                'timestamp': data.get('created_at'),
                'entry_id': data.get('entry_id')
            }
            return jsonify(mapped_data)
        else:
            return jsonify({'error': f'ThingSpeak error: {res.status_code}'}), res.status_code
    except Exception as e:
        logger.error(f"Error fetching from ThingSpeak: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/history/1')
def history():
    readings = WaterReading.query.order_by(WaterReading.timestamp.desc()).limit(20).all()
    return jsonify([r.to_dict() for r in readings[::-1]])

@app.route('/api/chatbot', methods=['POST'])
def chat():
    try:
        user_message = request.json.get('message', '').lower()
        logger.info(f"Chatbot request received: {user_message}")
        if not user_message:
            return jsonify({'response': 'I didn\'t catch that. How can I help?'})

        # Get context of latest reading
        last_reading = WaterReading.query.order_by(WaterReading.timestamp.desc()).first()
        context = ""
        if last_reading:
            reading_dict = last_reading.to_dict()
            context = f" Current water status: pH {reading_dict['ph']}, TDS {reading_dict['tds']} ppm, Temp {reading_dict['temperature']}°C. Air Quality index: {reading_dict['air_quality']}. Rain status: {reading_dict['rain']}."

        prompt = f"You are AquaBot, an AI assistant for the AquaSense AI water monitoring platform. Answer the user's question concisely based on the following context if relevant: {context}\nUser: {user_message}\nAquaBot:"
        
        response = client.models.generate_content(
            model=chatbot_model_id,
            contents=prompt
        )
        logger.info(f"Chatbot response generated: {response.text[:50]}...")
        return jsonify({'response': response.text})
    except Exception as e:
        logger.error(f"Chatbot error: {e}")
        return jsonify({'response': 'Sorry, I am having trouble thinking right now. Please try again later.'})

def generate_mock_data():
    with app.app_context():
        locations = [
            {'id': 'HQ', 'lat': 40.7128, 'lng': -74.0060},
            {'id': 'MID', 'lat': 40.7580, 'lng': -73.9855},
            {'id': 'SITE_C', 'lat': 40.7282, 'lng': -73.9942}
        ]
        loc = random.choice(locations)
        
        # Try to get data from Gemini for a realistic simulation
        try:
            last_reading = WaterReading.query.filter_by(device_id=loc['id']).order_by(WaterReading.timestamp.desc()).first()
            context = "First reading."
            if last_reading:
                rd = last_reading.to_dict()
                context = f"Last state: pH {rd['ph']}, TDS {rd['tds']}, Temp {rd['temperature']}, Turbidity {rd['turbidity']}, Humidity {rd['humidity']}, Air {rd['air_quality']}, Rain {rd['rain']}."

            prompt = (
                f"You are a Water Quality Sensor Simulator. Given the context: {context}\n"
                "Generate the next realistic reading for a Smart City environment. "
                "Return ONLY a JSON object with: ph, tds, turbidity, temp, humidity, mq135 (air quality), rain (string: 'No Rain', 'Light', 'Moderate', 'Heavy').\n"
                "Constraints: pH (0-14), TDS (50-1000), Turbidity (0-10), Temp (10-40), Humidity (0-100), AQ (0-1000).\n"
                "Format: {\"ph\": 7.2, \"tds\": 450, \"turbidity\": 1.2, \"temp\": 22.5, \"humidity\": 45, \"mq135\": 120, \"rain\": \"No Rain\"}"
            )
            
            response = client.models.generate_content(
                model=chatbot_model_id,
                contents=prompt
            )
            
            import json
            import re
            # Extract JSON from response text (to handle potential markdown backticks)
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if not match: raise ValueError("No JSON found in response")
            
            ai_data = json.loads(match.group())
            
            new_reading = WaterReading(
                device_id=loc['id'], 
                ph=float(ai_data.get('ph', 7.0)), 
                tds=float(ai_data.get('tds', 300)), 
                turbidity=float(ai_data.get('turbidity', 1.0)), 
                temperature=float(ai_data.get('temp', 20.0)),
                humidity=float(ai_data.get('humidity', 50.0)),
                air_quality=float(ai_data.get('mq135', 100.0)),
                rain=ai_data.get('rain', 'No Rain'),
                lat=loc['lat'], 
                lng=loc['lng']
            )
            logger.info(f"AI-generated data created for {loc['id']}")
            
            # Sync to ThingSpeak
            sync_to_thingspeak(ai_data)
            
        except Exception as e:
            logger.warning(f"AI data generation failed, falling back to random: {e}")
            new_reading = WaterReading(
                device_id=loc['id'], 
                ph=random.uniform(6.5, 8.5), 
                tds=random.uniform(200, 800), 
                turbidity=random.uniform(0.5, 5.0), 
                temperature=random.uniform(15.0, 30.0),
                humidity=random.uniform(30, 70),
                air_quality=random.uniform(100, 600),
                rain=random.choice(["No Rain", "Light", "Moderate", "Heavy"]),
                lat=loc['lat'], 
                lng=loc['lng']
            )
            logger.info(f"Mock data (random) generated for {loc['id']}")
            
            # Sync to ThingSpeak (Random data fallback)
            sync_to_thingspeak({
                'ph': new_reading.ph,
                'tds': new_reading.tds,
                'temp': new_reading.temperature,
                'turbidity': new_reading.turbidity,
                'humidity': new_reading.humidity,
                'mq135': new_reading.air_quality
            })

        db.session.add(new_reading)
        db.session.commit()

def init_database():
    with app.app_context():
        db.create_all()
        if not WaterReading.query.first():
            generate_mock_data()
            logger.info("Initial mock data created")

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(
    func=generate_mock_data, 
    trigger=IntervalTrigger(seconds=30),
    id='mock_data_generation',
    replace_existing=True
)
scheduler.start()

# Shutdown scheduler on exit
atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    try:
        init_database()
        port = int(os.getenv('PORT', 5000))
        logger.info(f"Starting AquaSense AI on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"Fatal error starting app: {e}")
        if "Address already in use" in str(e) or "EADDRINUSE" in str(e):
            logger.info("Port 5000 busy, trying 5001...")
            app.run(host='0.0.0.0', port=5001, debug=False)
