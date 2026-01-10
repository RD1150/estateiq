"""
EstateIQ - Enhanced Real Estate AI Platform with ChatGPT-style capabilities
Combines property search, market analytics, and intelligent conversation
Updated to serve frontend from root directory for Render deployment
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import sqlite3
import json
import os
import requests
from datetime import datetime, timedelta
import openai
from typing import List, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app - serve static files from root directory
app = Flask(__name__)
CORS(app, origins="*")

# OpenAI configuration for ChatGPT-style AI
openai.api_key = os.getenv('OPENAI_API_KEY', 'your-key-here')
openai.api_base = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')

# Database initialization
def init_db():
    """Initialize the EstateIQ database with enhanced schema"""
    conn = sqlite3.connect('estateiq.db')
    cursor = conn.cursor()
    
    # Properties table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            zip_code TEXT,
            price REAL NOT NULL,
            bedrooms INTEGER,
            bathrooms REAL,
            square_feet INTEGER,
            property_type TEXT,
            listing_date DATE,
            days_on_market INTEGER,
            ai_score REAL,
            trend TEXT,
            description TEXT,
            amenities TEXT,
            neighborhood_score REAL,
            walkability_score INTEGER,
            school_rating REAL,
            crime_rating TEXT,
            investment_potential TEXT,
            rental_estimate REAL,
            cap_rate REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
    
    conn.commit()
    conn.close()

# Enhanced AI Agent Class
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
        
        Always provide specific, actionable advice and ask follow-up questions to better understand user needs.
        """
    
    def get_conversation_context(self, session_id: str, limit: int = 5) -> List[Dict]:
        """Retrieve recent conversation history for context"""
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
    
    def save_conversation(self, session_id: str, user_message: str, ai_response: str, context: str = ""):
        """Save conversation to database for memory"""
        conn = sqlite3.connect('estateiq.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO conversations (session_id, user_message, ai_response, context)
            VALUES (?, ?, ?, ?)
        ''', (session_id, user_message, ai_response, context))
        
        conn.commit()
        conn.close()
    
    def analyze_user_intent(self, message: str) -> Dict[str, Any]:
        """Analyze user message to determine intent and extract parameters"""
        intents = {
            'property_search': ['find', 'search', 'show me', 'looking for', 'want to buy'],
            'market_analysis': ['market', 'trends', 'analysis', 'neighborhood', 'area'],
            'investment_advice': ['invest', 'ROI', 'cap rate', 'rental', 'cash flow'],
            'general_question': ['what', 'how', 'why', 'explain', 'tell me about']
        }
        
        message_lower = message.lower()
        detected_intent = 'general_question'  # default
        
        for intent, keywords in intents.items():
            if any(keyword in message_lower for keyword in keywords):
                detected_intent = intent
                break
        
        # Extract parameters (budget, bedrooms, location, etc.)
        parameters = self.extract_parameters(message)
        
        return {
            'intent': detected_intent,
            'parameters': parameters,
            'original_message': message
        }
    
    def extract_parameters(self, message: str) -> Dict[str, Any]:
        """Extract specific parameters from user message"""
        import re
        
        parameters = {}
        message_lower = message.lower()
        
        # Extract budget
        budget_patterns = [
            r'\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:k|thousand)',
            r'\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
            r'under\s+\$?(\d+)',
            r'below\s+\$?(\d+)',
            r'up\s+to\s+\$?(\d+)'
        ]
        
        for pattern in budget_patterns:
            match = re.search(pattern, message_lower)
            if match:
                amount = match.group(1).replace(',', '')
                if 'k' in match.group(0) or 'thousand' in match.group(0):
                    amount = str(int(float(amount)) * 1000)
                parameters['budget'] = float(amount)
                break
        
        # Extract bedrooms
        bedroom_match = re.search(r'(\d+)\s*(?:bed|bedroom)', message_lower)
        if bedroom_match:
            parameters['bedrooms'] = int(bedroom_match.group(1))
        
        # Extract bathrooms
        bathroom_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:bath|bathroom)', message_lower)
        if bathroom_match:
            parameters['bathrooms'] = float(bathroom_match.group(1))
        
        # Extract location
        location_patterns = [
            r'in\s+([a-zA-Z\s]+?)(?:\s|$|,)',
            r'near\s+([a-zA-Z\s]+?)(?:\s|$|,)',
            r'around\s+([a-zA-Z\s]+?)(?:\s|$|,)'
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, message_lower)
            if match:
                location = match.group(1).strip()
                if len(location) > 2:  # Avoid single letters
                    parameters['location'] = location.title()
                break
        
        return parameters
    
    def generate_response(self, session_id: str, user_message: str) -> str:
        """Generate intelligent response using OpenAI with conversation context"""
        try:
            # Get conversation history for context
            history = self.get_conversation_context(session_id)
            
            # Analyze user intent
            intent_analysis = self.analyze_user_intent(user_message)
            
            # Build messages for OpenAI
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add conversation history
            for conv in history:
                messages.append({"role": "user", "content": conv["user"]})
                messages.append({"role": "assistant", "content": conv["assistant"]})
            
            # Add current message with intent context
            context_message = f"""
            User message: {user_message}
            
            Detected intent: {intent_analysis['intent']}
            Extracted parameters: {json.dumps(intent_analysis['parameters'], indent=2)}
            
            Please provide a helpful response based on the intent and parameters.
            If this is a property search, provide specific guidance on what to look for.
            If this is investment advice, include relevant calculations and considerations.
            Always ask follow-up questions to better understand their needs.
            """
            
            messages.append({"role": "user", "content": context_message})
            
            # Generate response using OpenAI
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            
            ai_response = response.choices[0].message.content
            
            # Save conversation for future context
            self.save_conversation(session_id, user_message, ai_response, json.dumps(intent_analysis))
            
            return ai_response
            
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            return f"I'm having trouble processing that right now. Could you rephrase your question? (Error: {str(e)})"

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
        conn = sqlite3.connect('estateiq.db')
        cursor = conn.cursor()
        
        # Get query parameters
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        bedrooms = request.args.get('bedrooms', type=int)
        city = request.args.get('city')
        
        # Build query
        query = "SELECT * FROM properties WHERE 1=1"
        params = []
        
        if min_price:
            query += " AND price >= ?"
            params.append(min_price)
        if max_price:
            query += " AND price <= ?"
            params.append(max_price)
        if bedrooms:
            query += " AND bedrooms = ?"
            params.append(bedrooms)
        if city:
            query += " AND city LIKE ?"
            params.append(f"%{city}%")
        
        cursor.execute(query, params)
        properties = cursor.fetchall()
        conn.close()
        
        # Convert to dict
        columns = [
            'id', 'address', 'city', 'state', 'zip_code', 'price', 'bedrooms', 
            'bathrooms', 'square_feet', 'property_type', 'listing_date', 
            'days_on_market', 'ai_score', 'trend', 'description', 'amenities',
            'neighborhood_score', 'walkability_score', 'school_rating', 
            'crime_rating', 'investment_potential', 'rental_estimate', 'cap_rate',
            'created_at'
        ]
        
        result = []
        for prop in properties:
            result.append(dict(zip(columns, prop)))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error fetching properties: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Enhanced ChatGPT-style AI chat endpoint"""
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
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/analytics')
def get_analytics():
    """Get market analytics and insights"""
    try:
        conn = sqlite3.connect('estateiq.db')
        cursor = conn.cursor()
        
        # Get aggregate statistics
        cursor.execute('''
            SELECT 
                AVG(price) as avg_price,
                COUNT(*) as total_properties,
                AVG(ai_score) as avg_ai_score,
                SUM(CASE WHEN trend = 'Rising' THEN 1 ELSE 0 END) as rising_count,
                SUM(CASE WHEN trend = 'Stable' THEN 1 ELSE 0 END) as stable_count,
                SUM(CASE WHEN trend = 'Declining' THEN 1 ELSE 0 END) as declining_count
            FROM properties
        ''')
        
        stats = cursor.fetchone()
        
        # Get city breakdown
        cursor.execute('''
            SELECT city, COUNT(*) as count, AVG(price) as avg_price, AVG(ai_score) as avg_score
            FROM properties
            GROUP BY city
        ''')
        
        cities = cursor.fetchall()
        conn.close()
        
        return jsonify({
            "overview": {
                "average_price": round(stats[0], 2) if stats[0] else 0,
                "total_properties": stats[1],
                "average_ai_score": round(stats[2], 1) if stats[2] else 0,
                "market_sentiment": {
                    "rising": stats[3],
                    "stable": stats[4],
                    "declining": stats[5]
                }
            },
            "cities": [
                {
                    "city": city[0],
                    "property_count": city[1],
                    "average_price": round(city[2], 2),
                    "average_score": round(city[3], 1)
                }
                for city in cities
            ]
        })
        
    except Exception as e:
        logger.error(f"Error fetching analytics: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Sample data population
def populate_sample_data():
    """Populate database with sample Westlake Village and Thousand Oaks properties"""
    conn = sqlite3.connect('estateiq.db')
    cursor = conn.cursor()
    
    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM properties")
    if cursor.fetchone()[0] > 0:
        conn.close()
        logger.info("Sample data already exists")
        return
    
    sample_properties = [
        {
            'address': '1245 Lakeview Canyon Road',
            'city': 'Westlake Village',
            'state': 'CA',
            'zip_code': '91361',
            'price': 2850000,
            'bedrooms': 5,
            'bathrooms': 4.5,
            'square_feet': 4200,
            'property_type': 'Single Family',
            'listing_date': '2024-06-15',
            'days_on_market': 18,
            'ai_score': 9.2,
            'trend': 'Rising',
            'description': 'Stunning Mediterranean estate with panoramic lake views, infinity pool, and wine cellar. Gated community with resort-style amenities.',
            'amenities': 'Infinity pool, wine cellar, home theater, 3-car garage, smart home, outdoor kitchen',
            'neighborhood_score': 9.5,
            'walkability_score': 72,
            'school_rating': 9.3,
            'crime_rating': 'Very Low',
            'investment_potential': 'Excellent',
            'rental_estimate': 12500,
            'cap_rate': 5.3
        },
        {
            'address': '3890 Via Pacifica',
            'city': 'Westlake Village',
            'state': 'CA',
            'zip_code': '91362',
            'price': 1650000,
            'bedrooms': 4,
            'bathrooms': 3.0,
            'square_feet': 3100,
            'property_type': 'Single Family',
            'listing_date': '2024-06-20',
            'days_on_market': 12,
            'ai_score': 8.7,
            'trend': 'Rising',
            'description': 'Modern luxury home in North Ranch with mountain views, chef\'s kitchen, and spa-like master suite.',
            'amenities': 'Gourmet kitchen, spa bathroom, office, pool, solar panels, EV charger',
            'neighborhood_score': 9.2,
            'walkability_score': 65,
            'school_rating': 9.0,
            'crime_rating': 'Very Low',
            'investment_potential': 'Excellent',
            'rental_estimate': 8500,
            'cap_rate': 6.2
        },
        {
            'address': '2156 Thousand Oaks Boulevard',
            'city': 'Thousand Oaks',
            'state': 'CA',
            'zip_code': '91362',
            'price': 1250000,
            'bedrooms': 4,
            'bathrooms': 3.0,
            'square_feet': 2800,
            'property_type': 'Single Family',
            'listing_date': '2024-05-10',
            'days_on_market': 25,
            'ai_score': 8.4,
            'trend': 'Stable',
            'description': 'Beautiful ranch-style home in desirable Lang Ranch area with updated kitchen, hardwood floors, and large backyard.',
            'amenities': 'Updated kitchen, hardwood floors, fireplace, 2-car garage, covered patio',
            'neighborhood_score': 8.8,
            'walkability_score': 58,
            'school_rating': 8.8,
            'crime_rating': 'Low',
            'investment_potential': 'Very Good',
            'rental_estimate': 6200,
            'cap_rate': 6.0
        },
        {
            'address': '4521 Conejo School Road',
            'city': 'Thousand Oaks',
            'state': 'CA',
            'zip_code': '91360',
            'price': 975000,
            'bedrooms': 3,
            'bathrooms': 2.5,
            'square_feet': 2200,
            'property_type': 'Single Family',
            'listing_date': '2024-06-25',
            'days_on_market': 8,
            'ai_score': 8.1,
            'trend': 'Rising',
            'description': 'Move-in ready home near top-rated schools with open floor plan, granite counters, and mountain views.',
            'amenities': 'Granite counters, stainless appliances, fireplace, landscaped yard, 2-car garage',
            'neighborhood_score': 8.5,
            'walkability_score': 62,
            'school_rating': 9.1,
            'crime_rating': 'Low',
            'investment_potential': 'Very Good',
            'rental_estimate': 5200,
            'cap_rate': 6.4
        },
        {
            'address': '789 Westlake Plaza',
            'city': 'Westlake Village',
            'state': 'CA',
            'zip_code': '91361',
            'price': 895000,
            'bedrooms': 2,
            'bathrooms': 2.5,
            'square_feet': 1850,
            'property_type': 'Townhouse',
            'listing_date': '2024-06-18',
            'days_on_market': 15,
            'ai_score': 7.9,
            'trend': 'Stable',
            'description': 'Elegant townhouse in prime location near The Oaks shopping center with modern finishes and community amenities.',
            'amenities': 'Community pool, gym, attached garage, granite counters, walk-in closets',
            'neighborhood_score': 9.0,
            'walkability_score': 85,
            'school_rating': 8.7,
            'crime_rating': 'Very Low',
            'investment_potential': 'Good',
            'rental_estimate': 4800,
            'cap_rate': 6.4
        },
        {
            'address': '3345 Moorpark Road',
            'city': 'Thousand Oaks',
            'state': 'CA',
            'zip_code': '91360',
            'price': 825000,
            'bedrooms': 3,
            'bathrooms': 2.0,
            'square_feet': 1950,
            'property_type': 'Single Family',
            'listing_date': '2024-07-05',
            'days_on_market': 22,
            'ai_score': 7.6,
            'trend': 'Rising',
            'description': 'Charming single-story home in established neighborhood with vaulted ceilings and private backyard.',
            'amenities': 'Vaulted ceilings, updated kitchen, large lot, fruit trees, 2-car garage',
            'neighborhood_score': 8.2,
            'walkability_score': 55,
            'school_rating': 8.5,
            'crime_rating': 'Low',
            'investment_potential': 'Good',
            'rental_estimate': 4500,
            'cap_rate': 6.5
        }
    ]
    
    for prop in sample_properties:
        cursor.execute('''
            INSERT INTO properties (
                address, city, state, zip_code, price, bedrooms, bathrooms, 
                square_feet, property_type, listing_date, days_on_market, 
                ai_score, trend, description, amenities, neighborhood_score,
                walkability_score, school_rating, crime_rating, investment_potential,
                rental_estimate, cap_rate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            prop['address'], prop['city'], prop['state'], prop['zip_code'],
            prop['price'], prop['bedrooms'], prop['bathrooms'], prop['square_feet'],
            prop['property_type'], prop['listing_date'], prop['days_on_market'],
            prop['ai_score'], prop['trend'], prop['description'], prop['amenities'],
            prop['neighborhood_score'], prop['walkability_score'], prop['school_rating'],
            prop['crime_rating'], prop['investment_potential'], prop['rental_estimate'],
            prop['cap_rate']
        ))
    
    conn.commit()
    conn.close()
    logger.info("Sample data populated successfully")

if __name__ == '__main__':
    init_db()
    populate_sample_data()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
