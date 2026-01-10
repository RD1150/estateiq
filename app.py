"""
EstateIQ - Enhanced Real Estate AI Platform with ChatGPT-style capabilities
Combines property search, market analytics, and intelligent conversation
"""

from flask import Flask, request, jsonify, send_from_directory
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

app = Flask(__name__, static_folder='../frontend/dist', static_url_path='')
CORS(app, origins="*")

# OpenAI configuration for ChatGPT-style AI
openai.api_key = os.getenv('OPENAI_API_KEY')
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
            return "I apologize, but I'm having trouble processing your request right now. Could you please try rephrasing your question about real estate?"

# Initialize AI agent
ai_agent = EstateIQAgent()

# API Routes
@app.route('/')
def serve_frontend():
    """Serve the React frontend"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/api/properties')
def get_properties():
    """Get properties with optional filtering"""
    try:
        conn = sqlite3.connect('estateiq.db')
        cursor = conn.cursor()
        
        # Get query parameters
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        bedrooms = request.args.get('bedrooms', type=int)
        city = request.args.get('city')
        property_type = request.args.get('property_type')
        
        # Build dynamic query
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
        if property_type:
            query += " AND property_type = ?"
            params.append(property_type)
        
        query += " ORDER BY ai_score DESC LIMIT 20"
        
        cursor.execute(query, params)
        properties = cursor.fetchall()
        
        # Convert to list of dictionaries
        columns = [description[0] for description in cursor.description]
        properties_list = [dict(zip(columns, row)) for row in properties]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'properties': properties_list,
            'count': len(properties_list)
        })
        
    except Exception as e:
        logger.error(f"Error fetching properties: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    """Enhanced chat endpoint with ChatGPT-style capabilities"""
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        session_id = data.get('session_id', 'default')
        
        if not user_message:
            return jsonify({'success': False, 'error': 'Message is required'}), 400
        
        # Generate AI response
        ai_response = ai_agent.generate_response(session_id, user_message)
        
        return jsonify({
            'success': True,
            'response': ai_response,
            'session_id': session_id,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/market-analytics')
def get_market_analytics():
    """Get market analytics and trends"""
    try:
        conn = sqlite3.connect('estateiq.db')
        cursor = conn.cursor()
        
        # Calculate market statistics
        cursor.execute('''
            SELECT 
                AVG(price) as avg_price,
                COUNT(*) as total_properties,
                AVG(ai_score) as avg_ai_score,
                AVG(days_on_market) as avg_days_on_market,
                COUNT(CASE WHEN trend = 'Rising' THEN 1 END) as rising_properties,
                COUNT(CASE WHEN trend = 'Stable' THEN 1 END) as stable_properties,
                COUNT(CASE WHEN trend = 'Declining' THEN 1 END) as declining_properties
            FROM properties
        ''')
        
        stats = cursor.fetchone()
        
        # Get price distribution by city
        cursor.execute('''
            SELECT city, AVG(price) as avg_price, COUNT(*) as count
            FROM properties
            GROUP BY city
            ORDER BY avg_price DESC
        ''')
        
        city_data = cursor.fetchall()
        
        conn.close()
        
        analytics = {
            'market_overview': {
                'average_price': round(stats[0] or 0, 2),
                'total_properties': stats[1] or 0,
                'average_ai_score': round(stats[2] or 0, 1),
                'average_days_on_market': round(stats[3] or 0, 1),
                'market_sentiment': {
                    'rising': stats[4] or 0,
                    'stable': stats[5] or 0,
                    'declining': stats[6] or 0
                }
            },
            'city_analysis': [
                {
                    'city': row[0],
                    'average_price': round(row[1], 2),
                    'property_count': row[2]
                }
                for row in city_data
            ]
        }
        
        return jsonify({
            'success': True,
            'analytics': analytics
        })
        
    except Exception as e:
        logger.error(f"Error fetching analytics: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/property/<int:property_id>')
def get_property_details(property_id):
    """Get detailed information about a specific property"""
    try:
        conn = sqlite3.connect('estateiq.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM properties WHERE id = ?", (property_id,))
        property_data = cursor.fetchone()
        
        if not property_data:
            return jsonify({'success': False, 'error': 'Property not found'}), 404
        
        columns = [description[0] for description in cursor.description]
        property_dict = dict(zip(columns, property_data))
        
        conn.close()
        
        return jsonify({
            'success': True,
            'property': property_dict
        })
        
    except Exception as e:
        logger.error(f"Error fetching property details: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Initialize database and populate with sample data
def populate_sample_data():
    """Populate database with enhanced sample properties"""
    conn = sqlite3.connect('estateiq.db')
    cursor = conn.cursor()
    
    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM properties")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return
    
    sample_properties = [
        {
            'address': '123 Oak Street',
            'city': 'Austin',
            'state': 'TX',
            'zip_code': '78701',
            'price': 650000,
            'bedrooms': 3,
            'bathrooms': 2.5,
            'square_feet': 1850,
            'property_type': 'Single Family',
            'listing_date': '2024-07-15',
            'days_on_market': 15,
            'ai_score': 8.5,
            'trend': 'Rising',
            'description': 'Beautiful modern home in prime Austin location with updated kitchen and spacious backyard.',
            'amenities': 'Updated kitchen, hardwood floors, large backyard, garage',
            'neighborhood_score': 9.2,
            'walkability_score': 85,
            'school_rating': 8.5,
            'crime_rating': 'Low',
            'investment_potential': 'Excellent',
            'rental_estimate': 3200,
            'cap_rate': 5.9
        },
        {
            'address': '789 Maple Drive',
            'city': 'Austin',
            'state': 'TX',
            'zip_code': '78704',
            'price': 950000,
            'bedrooms': 4,
            'bathrooms': 3.5,
            'square_feet': 2800,
            'property_type': 'Single Family',
            'listing_date': '2024-06-20',
            'days_on_market': 45,
            'ai_score': 8.2,
            'trend': 'Stable',
            'description': 'Luxury home with pool and premium finishes in desirable South Austin neighborhood.',
            'amenities': 'Swimming pool, granite countertops, master suite, 3-car garage',
            'neighborhood_score': 8.8,
            'walkability_score': 78,
            'school_rating': 9.0,
            'crime_rating': 'Very Low',
            'investment_potential': 'Good',
            'rental_estimate': 4500,
            'cap_rate': 5.7
        },
        {
            'address': '456 Pine Avenue',
            'city': 'Austin',
            'state': 'TX',
            'zip_code': '78702',
            'price': 425000,
            'bedrooms': 2,
            'bathrooms': 2.0,
            'square_feet': 1200,
            'property_type': 'Condo',
            'listing_date': '2024-07-01',
            'days_on_market': 30,
            'ai_score': 7.8,
            'trend': 'Rising',
            'description': 'Modern downtown condo with city views and premium amenities.',
            'amenities': 'City views, fitness center, rooftop deck, concierge',
            'neighborhood_score': 9.5,
            'walkability_score': 95,
            'school_rating': 7.5,
            'crime_rating': 'Moderate',
            'investment_potential': 'Very Good',
            'rental_estimate': 2800,
            'cap_rate': 7.9
        },
        {
            'address': '321 Cedar Lane',
            'city': 'Round Rock',
            'state': 'TX',
            'zip_code': '78664',
            'price': 485000,
            'bedrooms': 3,
            'bathrooms': 2.0,
            'square_feet': 1650,
            'property_type': 'Single Family',
            'listing_date': '2024-06-10',
            'days_on_market': 55,
            'ai_score': 7.5,
            'trend': 'Stable',
            'description': 'Family-friendly home in excellent school district with large yard.',
            'amenities': 'Large yard, updated appliances, 2-car garage, patio',
            'neighborhood_score': 8.5,
            'walkability_score': 65,
            'school_rating': 9.5,
            'crime_rating': 'Very Low',
            'investment_potential': 'Good',
            'rental_estimate': 2600,
            'cap_rate': 6.4
        },
        {
            'address': '987 Elm Street',
            'city': 'Cedar Park',
            'state': 'TX',
            'zip_code': '78613',
            'price': 575000,
            'bedrooms': 4,
            'bathrooms': 3.0,
            'square_feet': 2200,
            'property_type': 'Single Family',
            'listing_date': '2024-07-20',
            'days_on_market': 10,
            'ai_score': 8.0,
            'trend': 'Rising',
            'description': 'Spacious family home with open floor plan and modern updates.',
            'amenities': 'Open floor plan, granite counters, covered patio, storage',
            'neighborhood_score': 8.2,
            'walkability_score': 55,
            'school_rating': 8.8,
            'crime_rating': 'Low',
            'investment_potential': 'Excellent',
            'rental_estimate': 3000,
            'cap_rate': 6.3
        },
        {
            'address': '654 Willow Way',
            'city': 'Pflugerville',
            'state': 'TX',
            'zip_code': '78660',
            'price': 395000,
            'bedrooms': 3,
            'bathrooms': 2.0,
            'square_feet': 1450,
            'property_type': 'Single Family',
            'listing_date': '2024-07-05',
            'days_on_market': 25,
            'ai_score': 7.2,
            'trend': 'Rising',
            'description': 'Affordable starter home in growing community with great potential.',
            'amenities': 'New roof, updated HVAC, fenced yard, 1-car garage',
            'neighborhood_score': 7.8,
            'walkability_score': 45,
            'school_rating': 8.0,
            'crime_rating': 'Low',
            'investment_potential': 'Very Good',
            'rental_estimate': 2200,
            'cap_rate': 6.7
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
    app.run(host='0.0.0.0', port=5000, debug=True)

