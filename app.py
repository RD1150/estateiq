"""
EstateIQ - Refined Real Estate Intelligence Platform
Implements opinionated AI with guardrails, liability-safe language, and clear assumptions
"""

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import sqlite3
import json
import os
import requests
from datetime import datetime, timedelta
from openai import OpenAI
from typing import List, Dict, Any, Optional
import logging
import time
import statistics

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app, origins="*")

# API Configuration - US Real Estate API
US_REALESTATE_KEY = os.getenv('US_REALESTATE_KEY', '2cfb05f293mshf960e959d3fa672p1ee089jsne4fed6afa385')
US_REALESTATE_HOST = "us-real-estate.p.rapidapi.com"
US_REALESTATE_BASE_URL = f"https://{US_REALESTATE_HOST}"

# Legacy Realtor16 API (keep for backward compatibility)
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
comps_cache = {}  # Cache for comparable sales by ZIP code

# Conejo Valley Area ZIP codes
CONEJO_VALLEY_ZIPS = ['91361', '91362', '91320', '91360', '91377', '91301', '93021', '93063', '91302']

# ===== ESTATEIQ AI SYSTEM PROMPT (LIABILITY-SAFE) =====

ESTATEIQ_SYSTEM_PROMPT = """You are EstateIQ, an AI-powered real estate analysis assistant.

Your role is to provide objective, data-driven insights about residential real estate based solely on publicly available information, comparable sales data, price-per-square-foot metrics, market trends, and user-provided inputs.

You are NOT a licensed appraiser, inspector, or financial advisor.

You must follow these rules at all times:

1. You do NOT make definitive judgments about property condition, structural integrity, or unseen features.
2. You do NOT guarantee investment performance, appreciation, or profitability.
3. You do NOT state whether a property is "good," "bad," "worth it," or "overpriced" as an absolute fact.
4. You DO explain how a property compares to similar properties based on objective metrics.
5. You DO clearly state assumptions and limitations when data is incomplete.

### Valuation Logic Rules
- Base comparisons on recent comparable sales when available.
- Use price-per-square-foot comparisons within the same market or zip code.
- Identify statistical deviations (above, below, or within local averages).
- Frame conclusions as "relative to market data" rather than personal opinion.

### When a Property Appears High or Low Priced
- Use neutral language such as:
  - "This price is above the recent average for similar homes in this area."
  - "Comparable sales suggest a lower typical price range, assuming similar condition."
- Always include a condition disclaimer:
  - "Actual value may vary based on interior condition, upgrades, lot characteristics, or other factors not visible in public data."

### Condition & Inspection Safeguards
- If asked about condition, defects, or renovations:
  - State that condition cannot be assessed without an in-person inspection.
  - Recommend professional inspections or agent review without directing to a specific provider.

### Investment & Deal Analysis
- Provide scenario-based analysis only.
- Use phrasing such as:
  - "Based on current data, some buyers may view this as…"
  - "From a data perspective, this pricing aligns / does not align with recent trends."
- Never state that a user should or should not buy a property.

### Tone & Style
- Professional, neutral, calm, and analytical.
- No hype, emojis, slang, or sales language.
- Sound like an experienced real estate analyst, not a salesperson.

### User Guidance
- Encourage users to consult licensed professionals for final decisions.
- Reinforce that EstateIQ is an informational tool, not a substitute for due diligence.

If a user requests advice that exceeds these boundaries, politely reframe the response using data and disclaimers rather than refusing outright.

Reminder: Always prioritize neutrality, data transparency, and disclaimers. Never provide absolute conclusions or personalized financial advice."""

# ===== PERSPECTIVE PROMPT TEMPLATES =====

BUYER_PROMPT_TEMPLATE = """Analyze this property using available market data.

Compare the price to recent comparable sales in the same area.
Explain how the price per square foot compares to local averages.
Identify whether the pricing appears above, below, or within typical market ranges based on available data.

Clearly state any assumptions or limitations due to missing information.
Do not assess property condition or unseen features.

Note: This analysis is based on publicly available data and does not account for interior condition, upgrades, or inspection findings."""

SELLER_PROMPT_TEMPLATE = """Evaluate this property's current list price relative to recent comparable sales.

Explain how the price aligns with recent market activity.
Highlight how similar homes have been priced and sold.
Indicate whether the price appears competitively positioned based on available data only.

Include disclaimers about condition, upgrades, and factors not visible in public records.

Note: This analysis is based on publicly available data and does not account for interior condition, upgrades, or inspection findings."""

INVESTOR_PROMPT_TEMPLATE = """Provide a data-driven investment overview of this property.

Analyze pricing relative to comparable sales and market averages.
Discuss potential rent ranges or yield scenarios if rental data is available.
Frame all insights as scenario-based and data-informed, not guaranteed outcomes.

Avoid definitive investment recommendations or profitability claims.

Note: This analysis is based on publicly available data and does not account for interior condition, upgrades, or inspection findings."""

# ===== MARKET ALIGNMENT SCORING RUBRIC =====

SCORING_RUBRIC = {
    'description': 'Market Alignment Score (1-10)',
    'scale': {
        10: 'Exceptionally aligned with recent comparable sales (rare)',
        9: 'Strong alignment with recent market data',
        8: 'Strong alignment with recent market data',
        7: 'Within typical market range',
        6: 'Within typical market range',
        5: 'Moderately above or below market norms',
        4: 'Moderately above or below market norms',
        3: 'Significantly misaligned with recent comparable data',
        2: 'Significantly misaligned with recent comparable data',
        1: 'Extreme deviation from market norms'
    },
    'required_language': [
        'Based on recent comparable sales…',
        'Relative to similar homes in this area…',
        'Assuming comparable condition…',
        'This score reflects market alignment, not property condition.'
    ],
    'forbidden_language': [
        'This is a bad deal',
        'This is overpriced (without context)',
        'You should / should not buy',
        'Guaranteed return',
        'Fair value'
    ]
}

# ===== UI DISCLAIMER =====

UI_DISCLAIMER = """EstateIQ provides informational, data-based insights using publicly available information. It does not assess property condition, guarantee outcomes, or replace professional advice. Final decisions should be made with licensed real estate and financial professionals."""

# ===== US REAL ESTATE API INTEGRATION =====

def get_sold_homes_by_zipcode(zipcode: str, limit: int = 20) -> List[Dict]:
    """Fetch sold homes (comps) from US Real Estate API by ZIP code"""
    cache_key = f"sold_{zipcode}"
    
    # Check cache
    if cache_key in comps_cache:
        cached_data, timestamp = comps_cache[cache_key]
        if time.time() - timestamp < CACHE_DURATION:
            logger.info(f"Returning cached sold homes for ZIP {zipcode}")
            return cached_data
    
    try:
        url = f"{US_REALESTATE_BASE_URL}/v2/sold-homes-by-zipcode"
        
        headers = {
            "x-rapidapi-key": US_REALESTATE_KEY,
            "x-rapidapi-host": US_REALESTATE_HOST
        }
        
        params = {
            "zipcode": zipcode,
            "limit": str(limit),
            "offset": "0"
        }
        
        logger.info(f"Fetching sold homes for ZIP {zipcode}")
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        sold_homes = data.get('data', {}).get('results', [])
        
        # Cache the results
        comps_cache[cache_key] = (sold_homes, time.time())
        
        logger.info(f"Found {len(sold_homes)} sold homes for ZIP {zipcode}")
        return sold_homes
        
    except Exception as e:
        logger.error(f"Error fetching sold homes for ZIP {zipcode}: {str(e)}")
        return []


def calculate_market_metrics(sold_homes: List[Dict], subject_property: Dict) -> Dict:
    """Calculate market metrics from comparable sales"""
    if not sold_homes:
        return None
    
    try:
        # Extract sold prices and $/sqft
        sold_prices = []
        price_per_sqft_list = []
        days_on_market_list = []
        
        for home in sold_homes:
            # Get sold price
            if 'sold_price' in home and home['sold_price']:
                sold_prices.append(home['sold_price'])
            elif 'list_price' in home and home['list_price']:
                sold_prices.append(home['list_price'])
            
            # Calculate $/sqft
            sqft = home.get('sqft') or home.get('building_size', {}).get('size')
            price = home.get('sold_price') or home.get('list_price')
            if sqft and price and sqft > 0:
                price_per_sqft_list.append(price / sqft)
            
            # Get days on market
            if 'days_on_market' in home and home['days_on_market']:
                days_on_market_list.append(home['days_on_market'])
        
        # Calculate subject property $/sqft
        subject_sqft = subject_property.get('square_feet') or subject_property.get('sqft', 0)
        subject_price = subject_property.get('price') or subject_property.get('list_price', 0)
        subject_price_per_sqft = subject_price / subject_sqft if subject_sqft > 0 else 0
        
        # Calculate medians and averages
        price_diff_pct = ((subject_price - statistics.median(sold_prices)) / statistics.median(sold_prices) * 100) if sold_prices else 0
        
        # Calculate Market Alignment Score (1-10)
        # Based on how closely the price aligns with recent comparable sales
        abs_diff = abs(price_diff_pct)
        if abs_diff <= 2:
            market_score = 10  # Exceptionally aligned
        elif abs_diff <= 5:
            market_score = 8 if abs_diff <= 3 else 7  # Strong alignment / Within typical range
        elif abs_diff <= 10:
            market_score = 6  # Within typical market range
        elif abs_diff <= 15:
            market_score = 5 if abs_diff <= 12 else 4  # Moderately misaligned
        elif abs_diff <= 25:
            market_score = 3 if abs_diff <= 20 else 2  # Significantly misaligned
        else:
            market_score = 1  # Extreme deviation
        
        metrics = {
            'median_sold_price': int(statistics.median(sold_prices)) if sold_prices else 0,
            'avg_price_per_sqft': int(statistics.mean(price_per_sqft_list)) if price_per_sqft_list else 0,
            'subject_price_per_sqft': int(subject_price_per_sqft),
            'avg_days_on_market': int(statistics.mean(days_on_market_list)) if days_on_market_list else 0,
            'comp_count': len(sold_homes),
            'price_diff_pct': price_diff_pct,
            'market_alignment_score': market_score
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error calculating market metrics: {str(e)}")
        return None


def generate_pricing_analysis(property_data: Dict, market_metrics: Dict) -> str:
    """Generate pricing analysis with liability-safe, market-relative language"""
    
    # Extract property info
    address = property_data.get('address', 'Unknown')
    city = property_data.get('city', '')
    state = property_data.get('state', '')
    zip_code = property_data.get('zip_code', '')
    list_price = property_data.get('price', 0)
    beds = property_data.get('bedrooms', 0)
    baths = property_data.get('bathrooms', 0)
    sqft = property_data.get('square_feet', 0)
    
    # Market metrics
    median_sold = market_metrics.get('median_sold_price', 0)
    avg_price_sqft = market_metrics.get('avg_price_per_sqft', 0)
    subject_price_sqft = market_metrics.get('subject_price_per_sqft', 0)
    avg_dom = market_metrics.get('avg_days_on_market', 0)
    comp_count = market_metrics.get('comp_count', 0)
    price_diff_pct = market_metrics.get('price_diff_pct', 0)
    market_score = market_metrics.get('market_alignment_score', 5)
    
    # Get score description
    score_description = SCORING_RUBRIC['scale'].get(market_score, 'Within typical market range')
    
    # Calculate valuation range (±5-7% of median to reflect condition variance)
    estimated_low = int(median_sold * 0.93)
    estimated_high = int(median_sold * 1.07)
    
    # Determine market-relative positioning (NOT absolute verdicts)
    if price_diff_pct > 10:
        position = "above the typical range"
        positioning_detail = "positioned at the higher end of recent comparable sales"
    elif price_diff_pct < -10:
        position = "below the typical range"
        positioning_detail = "positioned at the lower end of recent comparable sales"
    else:
        position = "within the typical range"
        positioning_detail = "aligned with recent comparable sales"
    
    # Market speed context
    if avg_dom > 60:
        market_context = "Properties in this area have been taking longer to sell, which may provide negotiation opportunities."
    elif avg_dom < 30:
        market_context = "Properties in this area are moving quickly, suggesting strong buyer demand."
    else:
        market_context = "Market absorption appears balanced based on recent sales velocity."
    
    # Condition variance explanation
    condition_note = "In this price range, condition typically explains price differences of approximately 5–15%. Extensive renovations, unique features, or deferred maintenance can materially affect value."
    
    # Build response with liability-safe language
    response = f"""**Market Analysis: {address}**
{city}, {state} {zip_code}
List Price: ${list_price:,} | {beds} beds, {baths} baths, {sqft:,} sqft

**Market Alignment Score: {market_score}/10**
{score_description}

Based on recent comparable sales, this score reflects how closely the asking price aligns with recent market activity. This score reflects market alignment, not property condition.

**Price Positioning**
Based on {comp_count} recent comparable sales in {zip_code}:
• Median sold price: ${median_sold:,}
• Typical $/sqft range: ${avg_price_sqft}
• Subject property $/sqft: ${subject_price_sqft}

Relative to similar homes in this area, this listing is priced {position}, {positioning_detail}.

**Market Context**
{market_context}

Average days on market: {avg_dom} days
Subject property is positioned {abs(price_diff_pct):.1f}% {'above' if price_diff_pct > 0 else 'below'} the area median.

**EstateIQ Value Range**
${estimated_low:,} - ${estimated_high:,}

This range reflects typical market variance and assumes average condition. {condition_note}

**Important Assumptions**
This analysis is based on publicly available market data and assumes average condition. Interior condition, upgrades, lot characteristics, and seller motivation can materially affect value. Professional inspection and agent consultation are recommended for final decision-making.

---
*EstateIQ provides data-driven market intelligence and is not a substitute for professional appraisal or inspection.*"""
    
    return response


# ===== LEGACY REALTOR16 API (Keep for property search) =====

def get_high_res_photo(photo_url: str) -> str:
    """Convert photo URL to higher resolution version"""
    if not photo_url:
        return ''
    # Replace 's.jpg' (small) with 'od.jpg' (original/large)
    return photo_url.replace('s.jpg', 'od.jpg').replace('s.webp', 'od.webp')


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
            "limit": str(limit)
        }
        
        logger.info(f"Fetching properties for location: {location}")
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        properties = data.get('data', {}).get('results', [])
        
        # Transform to our format
        transformed = []
        for prop in properties:
            transformed_prop = {
                'id': prop.get('property_id', ''),
                'address': prop.get('location', {}).get('address', {}).get('line', ''),
                'city': prop.get('location', {}).get('address', {}).get('city', ''),
                'state': prop.get('location', {}).get('address', {}).get('state_code', ''),
                'zip_code': prop.get('location', {}).get('address', {}).get('postal_code', ''),
                'price': prop.get('list_price', 0),
                'bedrooms': prop.get('description', {}).get('beds', 0),
                'bathrooms': prop.get('description', {}).get('baths', 0),
                'square_feet': prop.get('description', {}).get('sqft', 0),
                'photo_url': get_high_res_photo(prop.get('primary_photo', {}).get('href', ''))
            }
            transformed.append(transformed_prop)
        
        logger.info(f"Successfully fetched {len(transformed)} properties")
        return transformed
        
    except Exception as e:
        logger.error(f"Error fetching properties: {str(e)}")
        return []


# ===== DATABASE SETUP =====

def init_db():
    """Initialize SQLite database with tables"""
    conn = sqlite3.connect('estateiq.db')
    c = conn.cursor()
    
    # Leads table
    c.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            session_id TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Activity tracking table
    c.execute('''
        CREATE TABLE IF NOT EXISTS activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            property_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")


# Initialize database on startup
init_db()


# ===== API ENDPOINTS =====

@app.route('/api/properties', methods=['GET'])
def get_properties():
    """Get properties with caching"""
    location = request.args.get('location', 'Conejo Valley Area, CA')
    limit = int(request.args.get('limit', 20))
    
    # Check cache
    if property_cache['data'] and property_cache['timestamp']:
        if time.time() - property_cache['timestamp'] < CACHE_DURATION:
            logger.info("Returning cached properties")
            return jsonify(property_cache['data'])
    
    # Fetch fresh data
    properties = fetch_properties_from_api(location, limit)
    
    # Update cache
    property_cache['data'] = properties
    property_cache['timestamp'] = time.time()
    
    return jsonify(properties)


@app.route('/api/analyze-pricing', methods=['POST'])
def analyze_pricing():
    """Analyze property pricing with comparable sales data"""
    try:
        data = request.json
        property_data = data.get('property', {})
        
        # Get ZIP code
        zip_code = property_data.get('zip_code', '')
        if not zip_code:
            return jsonify({'error': 'ZIP code required for pricing analysis'}), 400
        
        # Fetch comparable sales
        sold_homes = get_sold_homes_by_zipcode(zip_code, limit=20)
        
        if not sold_homes:
            return jsonify({
                'error': 'Limited comparable data',
                'message': 'Insufficient recent sales data is available for this area. A professional appraisal or agent consultation is recommended for accurate valuation.'
            }), 404
        
        # Calculate market metrics
        market_metrics = calculate_market_metrics(sold_homes, property_data)
        
        if not market_metrics:
            return jsonify({'error': 'Unable to calculate market metrics'}), 500
        
        # Generate pricing analysis
        analysis = generate_pricing_analysis(property_data, market_metrics)
        
        return jsonify({
            'analysis': analysis,
            'metrics': market_metrics,
            'comp_count': len(sold_homes)
        })
        
    except Exception as e:
        logger.error(f"Error in pricing analysis: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Internal server error during pricing analysis'}), 500


@app.route('/api/chat', methods=['POST'])
def chat():
    """AI chat endpoint with liability-safe intelligence and perspective support"""
    try:
        data = request.json
        messages = data.get('messages', [])
        property_context = data.get('property', None)
        perspective = data.get('perspective', 'buyer')  # buyer, seller, or investor
        
        # Build system prompt with property context
        system_prompt = ESTATEIQ_SYSTEM_PROMPT
        
        # Add perspective-specific prompt template
        if perspective == 'seller':
            system_prompt += f"\n\n{SELLER_PROMPT_TEMPLATE}"
        elif perspective == 'investor':
            system_prompt += f"\n\n{INVESTOR_PROMPT_TEMPLATE}"
        else:  # default to buyer
            system_prompt += f"\n\n{BUYER_PROMPT_TEMPLATE}"
        
        # Add property context if available
        if property_context:
            system_prompt += f"\n\nCurrent property context:\n{json.dumps(property_context, indent=2)}"
        
        # Prepare messages for OpenAI
        openai_messages = [{"role": "system", "content": system_prompt}]
        openai_messages.extend(messages)
        
        # Call OpenAI
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=openai_messages,
            temperature=0.7,
            max_tokens=1000
        )
        
        assistant_message = response.choices[0].message.content
        
        return jsonify({
            'message': assistant_message
        })
        
    except Exception as e:
        logger.error(f"Error generating AI response: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'I apologize, but I encountered an error. Could you please rephrase your question?'}), 500


@app.route('/api/capture-lead', methods=['POST'])
def capture_lead():
    """Capture lead email"""
    try:
        data = request.json
        email = data.get('email', '').strip()
        session_id = data.get('session_id', '')
        source = data.get('source', 'email_gate')
        
        if not email:
            return jsonify({'error': 'Email is required'}), 400
        
        conn = sqlite3.connect('estateiq.db')
        c = conn.cursor()
        
        try:
            c.execute('''
                INSERT INTO leads (email, session_id, source)
                VALUES (?, ?, ?)
            ''', (email, session_id, source))
            conn.commit()
            logger.info(f"Captured lead: {email}")
            return jsonify({'success': True, 'message': 'Email captured successfully'})
        except sqlite3.IntegrityError:
            logger.info(f"Lead already exists: {email}")
            return jsonify({'success': True, 'message': 'Email already registered'})
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error capturing lead: {str(e)}")
        return jsonify({'error': 'Failed to capture email'}), 500


@app.route('/api/track-activity', methods=['POST'])
def track_activity():
    """Track user activity"""
    try:
        data = request.json
        session_id = data.get('session_id', '')
        activity_type = data.get('activity_type', '')
        property_id = data.get('property_id', '')
        
        if not session_id or not activity_type:
            return jsonify({'error': 'Session ID and activity type required'}), 400
        
        conn = sqlite3.connect('estateiq.db')
        c = conn.cursor()
        
        c.execute('''
            INSERT INTO activity (session_id, activity_type, property_id)
            VALUES (?, ?, ?)
        ''', (session_id, activity_type, property_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Error tracking activity: {str(e)}")
        return jsonify({'error': 'Failed to track activity'}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'apis': {
            'us_real_estate': 'configured',
            'realtor16': 'configured',
            'openai': 'configured'
        }
    })


@app.route('/', methods=['GET'])
def home():
    """Serve the main application"""
    return send_file('index.html')


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
