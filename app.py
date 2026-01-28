"""
EstateIQ - Enhanced Real Estate AI Platform with Live API Data & Lead Capture
Integrates Realtor16 RapidAPI for live property listings
Combines property search, market analytics, intelligent conversation, and lead generation
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import sqlite3
import json
import os
import requests
from datetime import datetime, timedelta
from openai import OpenAI
from typing import List, Dict, Any
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app, origins="*")

# API Configuration
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', 'f04bc72b5bmshef6c6b981b712e9p1e1375jsn62757808867c')
RAPIDAPI_HOST = "realtor16.p.rapidapi.com"
RAPIDAPI_BASE_URL = f"https://{RAPIDAPI_HOST}"

# OpenAI configuration
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Cache configuration
CACHE_DURATION = 3600  # 1 hour in seconds
property_cache = {
    'data': None,
    'timestamp': None
}

# ===== REALTOR API INTEGRATION =====

def fetch_properties_from_api(location: str, limit: int = 20) -> List[Dict]:
    """Fetch properties from Realtor16 API"""
    try:
        url = f"{RAPIDAPI_BASE_URL}/search/forsale"
        
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST
        }
        
        params = {
            "location": location,
            "sort": "relevant",
            "limit": str(limit)
        }
        
        logger.info(f"Fetching properties from API for location: {location}")
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Transform API response to our format
        properties = []
        if 'properties' in data:
            for prop in data['properties']:
                transformed = transform_api_property(prop)
                if transformed:
                    properties.append(transformed)
        
        logger.info(f"Successfully fetched {len(properties)} properties from API")
        return properties
        
    except Exception as e:
        logger.error(f"Error fetching from API: {str(e)}")
        return []

def get_high_res_photo(photo_url: str) -> str:
    """Convert thumbnail image URL to higher resolution version"""
    if not photo_url:
        return ''
    # Replace size suffix: -s (small) with -m (medium) or -od (original/large)
    # Example: image-m3034688638s.jpg -> image-m3034688638od.jpg
    if photo_url.endswith('s.jpg'):
        return photo_url[:-5] + 'od.jpg'  # Replace 's.jpg' with 'od.jpg' for larger size
    return photo_url

def transform_api_property(api_prop: Dict) -> Dict:
    """Transform Realtor API property to EstateIQ format"""
    try:
        # Extract address information
        address_info = api_prop.get('location', {}).get('address', {})
        
        # Calculate AI score based on available data
        ai_score = calculate_ai_score(api_prop)
        
        # Estimate rental income (simple formula)
        price = api_prop.get('list_price', 0)
        rental_estimate = price * 0.006 if price else 0  # 0.6% of price per month
        
        # Calculate cap rate (simple estimate)
        annual_rent = rental_estimate * 12
        cap_rate = (annual_rent / price * 100) if price > 0 else 0
        
        transformed = {
            'id': api_prop.get('property_id', ''),
            'address': address_info.get('line', 'N/A'),
            'city': address_info.get('city', 'N/A'),
            'state': address_info.get('state_code', 'CA'),
            'zip_code': address_info.get('postal_code', ''),
            'price': price,
            'bedrooms': api_prop.get('description', {}).get('beds', 0),
            'bathrooms': api_prop.get('description', {}).get('baths_full', 0) + api_prop.get('description', {}).get('baths_half', 0) * 0.5,
            'square_feet': api_prop.get('description', {}).get('sqft', 0),
            'property_type': api_prop.get('description', {}).get('type', 'single_family'),
            'listing_date': api_prop.get('list_date', datetime.now().strftime('%Y-%m-%d')),
            'days_on_market': api_prop.get('days_on_market', 0),
            'ai_score': round(ai_score, 1),
            'trend': determine_trend(api_prop),
            'description': api_prop.get('description', {}).get('text', 'Beautiful property'),
            'amenities': extract_amenities(api_prop),
            'neighborhood_score': round(ai_score * 0.9, 1),
            'walkability_score': api_prop.get('walkability_score', 65),
            'school_rating': api_prop.get('school_rating', 7.5),
            'crime_rating': 'Low',
            'investment_potential': determine_investment_potential(ai_score),
            'rental_estimate': round(rental_estimate, 2),
            'cap_rate': round(cap_rate, 2),
            'created_at': datetime.now().isoformat(),
            'photo_url': get_high_res_photo(api_prop.get('primary_photo', {}).get('href', '')),
            'property_url': api_prop.get('permalink', '')
        }
        
        return transformed
        
    except Exception as e:
        logger.error(f"Error transforming property: {str(e)}")
        return None

def calculate_ai_score(prop: Dict) -> float:
    """Calculate AI score based on property attributes"""
    score = 7.0  # Base score
    
    # Price factor
    price = prop.get('list_price', 0)
    if 500000 <= price <= 2000000:
        score += 1.0
    elif price < 500000:
        score += 0.5
    
    # Size factor
    sqft = prop.get('description', {}).get('sqft', 0)
    if sqft >= 2000:
        score += 0.5
    
    # Beds/baths factor
    beds = prop.get('description', {}).get('beds', 0)
    baths = prop.get('description', {}).get('baths', 0)
    if beds >= 3 and baths >= 2:
        score += 0.5
    
    # Days on market (lower is better)
    days = prop.get('days_on_market', 0)
    if days < 30:
        score += 0.5
    elif days > 90:
        score -= 0.5
    
    return min(10.0, max(1.0, score))

def determine_trend(prop: Dict) -> str:
    """Determine price trend"""
    days = prop.get('days_on_market', 0)
    if days < 30:
        return "Rising"
    elif days > 90:
        return "Falling"
    return "Stable"

def determine_investment_potential(ai_score: float) -> str:
    """Determine investment potential based on AI score"""
    if ai_score >= 8.5:
        return "Excellent"
    elif ai_score >= 7.5:
        return "Good"
    elif ai_score >= 6.5:
        return "Fair"
    return "Poor"

def extract_amenities(prop: Dict) -> str:
    """Extract amenities from property data"""
    amenities = []
    
    desc = prop.get('description', {})
    if desc.get('garage'):
        amenities.append(f"{desc.get('garage')} car garage")
    if desc.get('pool'):
        amenities.append("Pool")
    if desc.get('fireplace'):
        amenities.append("Fireplace")
    
    return ", ".join(amenities) if amenities else "Standard amenities"

def get_cached_properties() -> List[Dict]:
    """Get properties from cache or fetch from API"""
    global property_cache
    
    # Check if cache is valid
    if property_cache['data'] and property_cache['timestamp']:
        age = time.time() - property_cache['timestamp']
        if age < CACHE_DURATION:
            logger.info("Returning cached properties")
            return property_cache['data']
    
    # Fetch fresh data from API
    logger.info("Cache expired or empty, fetching from API")
    properties = []
    
    # Fetch from both locations
    westlake_props = fetch_properties_from_api("Westlake Village, CA", limit=10)
    thousand_oaks_props = fetch_properties_from_api("Thousand Oaks, CA", limit=10)
    
    properties.extend(westlake_props)
    properties.extend(thousand_oaks_props)
    
    # Update cache
    property_cache['data'] = properties
    property_cache['timestamp'] = time.time()
    
    return properties

# ===== DATABASE INITIALIZATION =====

def init_db():
    """Initialize the EstateIQ database"""
    conn = sqlite3.connect('estateiq.db')
    cursor = conn.cursor()
    
    # Conversations table for ChatGPT-style memory
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_message TEXT NOT NULL,
            ai_response TEXT NOT NULL,
            context TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # User preferences table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            budget_min REAL,
            budget_max REAL,
            preferred_bedrooms INTEGER,
            preferred_bathrooms REAL,
            preferred_cities TEXT,
            property_types TEXT,
            investment_goals TEXT,
            risk_tolerance TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Leads table for email capture
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            session_id TEXT,
            source TEXT,
            properties_viewed INTEGER DEFAULT 0,
            ai_messages_sent INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

# ===== AI AGENT =====

class EstateIQAgent:
    """Advanced AI agent with ChatGPT-style capabilities for real estate"""
    
    def __init__(self):
        self.system_prompt = """
        You are EstateIQ, an intelligent real estate assistant with deep expertise in:
        - Property analysis and valuation
        - Market trends and investment strategies
        - Neighborhood analysis and demographics
        - Real estate financing and mortgages
        - Investment property calculations (ROI, cap rates, cash flow)
        - First-time homebuyer guidance
        - Commercial real estate basics
        
        Your personality:
        - Professional yet approachable
        - Data-driven but explains complex concepts simply
        - Enthusiastic about helping people build wealth through real estate
        - Always provides actionable insights
        - Asks clarifying questions when needed
        
        Focus on helping first-time homebuyers and families find their perfect home in Westlake Village and Thousand Oaks, CA.
        Always provide specific, actionable advice and ask follow-up questions to better understand user needs.
        """
    
    def get_conversation_context(self, session_id: str, limit: int = 5) -> List[Dict]:
        """Retrieve recent conversation history for context"""
        try:
            conn = sqlite3.connect('estateiq.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT user_message, ai_response FROM conversations 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (session_id, limit))
            
            history = cursor.fetchall()
            conn.close()
            
            return [{"user": msg[0], "assistant": msg[1]} for msg in reversed(history)]
        except Exception as e:
            logger.error(f"Error getting conversation context: {str(e)}")
            return []
    
    def save_conversation(self, session_id: str, user_message: str, ai_response: str, context: str = ""):
        """Save conversation to database for memory"""
        try:
            conn = sqlite3.connect('estateiq.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO conversations (session_id, user_message, ai_response, context)
                VALUES (?, ?, ?, ?)
            ''', (session_id, user_message, ai_response, context))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving conversation: {str(e)}")
    
    def generate_response(self, session_id: str, user_message: str) -> str:
        """Generate intelligent response using OpenAI with conversation context"""
        try:
            # Get conversation history for context
            history = self.get_conversation_context(session_id)
            
            # Build messages for OpenAI
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add conversation history
            for conv in history:
                messages.append({"role": "user", "content": conv["user"]})
                messages.append({"role": "assistant", "content": conv["assistant"]})
            
            # Add current message
            messages.append({"role": "user", "content": user_message})
            
            # Generate response using OpenAI
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content
            
            # Save conversation for future context
            self.save_conversation(session_id, user_message, ai_response)
            
            return ai_response
            
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return "I apologize, but I encountered an error. Could you please rephrase your question?"

# Initialize AI agent
agent = EstateIQAgent()

# ===== ROUTES =====

@app.route('/')
def serve_frontend():
    """Serve the frontend index.html"""
    try:
        return send_file('index.html')
    except:
        return jsonify({"message": "EstateIQ API is running. Frontend not found."}), 200

@app.route('/api/properties')
def get_properties():
    """Get all properties with optional filtering"""
    try:
        # Get properties from cache/API
        all_properties = get_cached_properties()
        
        # Get query parameters for filtering
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        bedrooms = request.args.get('bedrooms', type=int)
        city = request.args.get('city')
        
        # Filter properties
        filtered_properties = all_properties
        
        if min_price:
            filtered_properties = [p for p in filtered_properties if p.get('price', 0) >= min_price]
        if max_price:
            filtered_properties = [p for p in filtered_properties if p.get('price', 0) <= max_price]
        if bedrooms:
            filtered_properties = [p for p in filtered_properties if p.get('bedrooms', 0) == bedrooms]
        if city:
            filtered_properties = [p for p in filtered_properties if city.lower() in p.get('city', '').lower()]
        
        return jsonify({
            "success": True,
            "properties": filtered_properties
        })
        
    except Exception as e:
        logger.error(f"Error fetching properties: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/analytics')
@app.route('/api/market-analytics')
def get_analytics():
    """Get market analytics"""
    try:
        properties = get_cached_properties()
        
        if not properties:
            return jsonify({
                "success": False,
                "error": "No properties available"
            }), 404
        
        # Calculate analytics
        prices = [p.get('price', 0) for p in properties if p.get('price', 0) > 0]
        ai_scores = [p.get('ai_score', 0) for p in properties if p.get('ai_score', 0) > 0]
        
        analytics = {
            "market_overview": {
                "total_properties": len(properties),
                "average_price": round(sum(prices) / len(prices), 2) if prices else 0,
                "median_price": round(sorted(prices)[len(prices) // 2], 2) if prices else 0,
                "average_ai_score": round(sum(ai_scores) / len(ai_scores), 2) if ai_scores else 0,
                "average_days_on_market": round(sum(p.get('days_on_market', 0) for p in properties) / len(properties), 0) if properties else 0
            },
            "price_distribution": {
                "under_1m": len([p for p in properties if p.get('price', 0) < 1000000]),
                "1m_to_2m": len([p for p in properties if 1000000 <= p.get('price', 0) < 2000000]),
                "over_2m": len([p for p in properties if p.get('price', 0) >= 2000000])
            },
            "property_types": {
                "single_family": len([p for p in properties if 'single' in p.get('property_type', '').lower()]),
                "condo": len([p for p in properties if 'condo' in p.get('property_type', '').lower()]),
                "townhouse": len([p for p in properties if 'town' in p.get('property_type', '').lower()])
            }
        }
        
        return jsonify({
            "success": True,
            "analytics": analytics
        })
        
    except Exception as e:
        logger.error(f"Error fetching analytics: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages with AI assistant"""
    try:
        data = request.json
        user_message = data.get('message', '')
        session_id = data.get('session_id', 'default')
        
        if not user_message:
            return jsonify({"error": "Message is required"}), 400
        
        # Generate AI response
        ai_response = agent.generate_response(session_id, user_message)
        
        return jsonify({
            "response": ai_response,
            "session_id": session_id
        })
        
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        return jsonify({"error": "I apologize, but I encountered an error. Please try again."}), 500

@app.route('/api/capture-lead', methods=['POST'])
def capture_lead():
    """Capture lead email and track activity"""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        session_id = data.get('session_id', '')
        source = data.get('source', 'unknown')  # 'property_limit', 'ai_limit', 'manual'
        
        if not email or '@' not in email:
            return jsonify({"success": False, "error": "Valid email is required"}), 400
        
        conn = sqlite3.connect('estateiq.db')
        cursor = conn.cursor()
        
        # Try to insert or update lead
        cursor.execute('''
            INSERT INTO leads (email, session_id, source, last_activity)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(email) DO UPDATE SET
                last_activity = CURRENT_TIMESTAMP,
                session_id = excluded.session_id
        ''', (email, session_id, source))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Lead captured: {email} from {source}")
        
        return jsonify({
            "success": True,
            "message": "Email captured successfully",
            "email": email
        })
        
    except Exception as e:
        logger.error(f"Error capturing lead: {str(e)}")
        return jsonify({"success": False, "error": "Failed to save email"}), 500

@app.route('/api/track-activity', methods=['POST'])
def track_activity():
    """Track user activity (properties viewed, AI messages sent)"""
    try:
        data = request.json
        session_id = data.get('session_id', '')
        activity_type = data.get('type', '')  # 'property_view', 'ai_message'
        
        if not session_id:
            return jsonify({"success": False, "error": "Session ID required"}), 400
        
        conn = sqlite3.connect('estateiq.db')
        cursor = conn.cursor()
        
        # Update activity count for this session's lead
        if activity_type == 'property_view':
            cursor.execute('''
                UPDATE leads 
                SET properties_viewed = properties_viewed + 1,
                    last_activity = CURRENT_TIMESTAMP
                WHERE session_id = ?
            ''', (session_id,))
        elif activity_type == 'ai_message':
            cursor.execute('''
                UPDATE leads 
                SET ai_messages_sent = ai_messages_sent + 1,
                    last_activity = CURRENT_TIMESTAMP
                WHERE session_id = ?
            ''', (session_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True})
        
    except Exception as e:
        logger.error(f"Error tracking activity: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/refresh-properties', methods=['POST'])
def refresh_properties():
    """Manually refresh property cache"""
    try:
        global property_cache
        property_cache['data'] = None
        property_cache['timestamp'] = None
        
        properties = get_cached_properties()
        
        return jsonify({
            "success": True,
            "message": f"Refreshed {len(properties)} properties",
            "count": len(properties)
        })
        
    except Exception as e:
        logger.error(f"Error refreshing properties: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

# ===== INITIALIZATION =====

# Initialize database on module load
try:
    init_db()
    logger.info("EstateIQ initialized successfully with Realtor16 API integration and lead capture")
except Exception as e:
    logger.error(f"Error initializing EstateIQ: {str(e)}")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
