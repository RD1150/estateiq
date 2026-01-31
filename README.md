# EstateIQ

**Intelligence Meets Wealth**

EstateIQ is an AI-powered real estate intelligence platform designed to help users understand price signals, market context, and tradeoffs before making decisions in the Conejo Valley Area.

## Product Philosophy

EstateIQ is **not** a home search tool or Zillow replacement.

EstateIQ is a **market intelligence layer** that provides:
- Data-driven price positioning analysis
- Comparable sales context
- Market behavior insights
- Risk and leverage framing

**The product's value is judgment and clarity, not raw data or listings.**

---

## Core Principles

### 1. Opinionated AI with Guardrails

EstateIQ provides confident, analytical insights while maintaining clear liability boundaries.

**We NEVER say:**
- "This is a good buy"
- "This is a bad deal"
- "This home is overpriced"
- "You should buy/avoid this property"

**We DO say:**
- "Priced above the typical range for similar homes"
- "Positioned at the higher end of recent comparable sales"
- "This price assumes strong condition or unique features"
- "From a buyer perspective, this pricing limits leverage"

### 2. Assumption Transparency

Every analysis clearly states:
- Based on publicly available market data
- Assumes average condition
- Interior condition, upgrades, and seller motivation can materially affect value

### 3. Market-Relative Language

We frame pricing as **relative to market data**, not absolute judgments:
- "Above typical range" vs "Overpriced"
- "Below recent averages" vs "Underpriced"
- "Aligned with comparable sales" vs "Fairly priced"

---

## Technical Architecture

### Stack
- **Backend**: Python Flask
- **Frontend**: Vanilla HTML/CSS/JavaScript
- **AI**: OpenAI GPT-4o-mini
- **Deployment**: Render

### APIs
- **US Real Estate API** (RapidAPI): Comparable sales data
- **Realtor16 API** (RapidAPI): Property listings
- **OpenAI API**: AI-powered market analysis

### Key Features
- Real-time property listings for Conejo Valley Area
- Comparable sales analysis with market metrics
- AI assistant with liability-safe language framework
- Email capture gates (5 properties, 3 AI questions)
- Activity tracking and lead management

---

## Geographic Coverage

**Conejo Valley Area** includes:
- Westlake Village
- Thousand Oaks
- Agoura Hills
- Newbury Park
- Oak Park
- Moorpark
- Simi Valley
- Calabasas
- Lake Sherwood
- Hidden Valley

---

## Environment Variables

```bash
# Required
OPENAI_API_KEY=your_openai_api_key
US_REALESTATE_KEY=your_rapidapi_key
RAPIDAPI_KEY=your_rapidapi_key

# Optional
PORT=5000
```

---

## Local Development

### Prerequisites
- Python 3.11+
- pip

### Setup

```bash
# Clone repository
git clone https://github.com/RD1150/estateiq.git
cd estateiq

# Install dependencies
pip install flask flask-cors openai requests

# Set environment variables
export OPENAI_API_KEY=your_key
export US_REALESTATE_KEY=your_key
export RAPIDAPI_KEY=your_key

# Run application
python app.py
```

Visit `http://localhost:5000`

---

## API Endpoints

### `GET /api/properties`
Fetch property listings for Conejo Valley Area

**Query Parameters:**
- `location` (optional): Search location (default: "Conejo Valley Area, CA")
- `limit` (optional): Number of results (default: 20)

**Response:**
```json
[
  {
    "id": "property_id",
    "address": "123 Main St",
    "city": "Westlake Village",
    "state": "CA",
    "zip_code": "91361",
    "price": 1250000,
    "bedrooms": 4,
    "bathrooms": 3,
    "square_feet": 2800,
    "photo_url": "https://..."
  }
]
```

### `POST /api/analyze-pricing`
Analyze property pricing with comparable sales

**Request Body:**
```json
{
  "property": {
    "address": "123 Main St",
    "city": "Westlake Village",
    "zip_code": "91361",
    "price": 1250000,
    "square_feet": 2800,
    "bedrooms": 4,
    "bathrooms": 3
  }
}
```

**Response:**
```json
{
  "analysis": "Market analysis text with liability-safe language...",
  "metrics": {
    "median_sold_price": 1180000,
    "avg_price_per_sqft": 425,
    "subject_price_per_sqft": 446,
    "avg_days_on_market": 45,
    "comp_count": 18,
    "price_diff_pct": 5.9
  },
  "comp_count": 18
}
```

### `POST /api/chat`
AI-powered market intelligence assistant

**Request Body:**
```json
{
  "messages": [
    {"role": "user", "content": "How does this property compare?"}
  ],
  "property": {
    "address": "123 Main St",
    "city": "Westlake Village",
    "price": 1250000
  }
}
```

**Response:**
```json
{
  "message": "Based on recent comparable sales..."
}
```

### `POST /api/capture-lead`
Capture user email for lead generation

**Request Body:**
```json
{
  "email": "user@example.com",
  "session_id": "unique_session_id",
  "source": "email_gate"
}
```

### `POST /api/track-activity`
Track user activity for analytics

**Request Body:**
```json
{
  "session_id": "unique_session_id",
  "activity_type": "pricing_analysis",
  "property_id": "property_id"
}
```

---

## AI System Prompt

EstateIQ uses a carefully crafted system prompt that enforces:

1. **No absolute judgments** about property value
2. **Market-relative comparisons** based on data
3. **Clear assumption disclosures** about condition
4. **Professional, analytical tone** without hype
5. **Liability safeguards** for investment advice

See `app.py` for the complete system prompt.

---

## Design Philosophy

**Inspiration**: Hybrid of Compass and Redfin
- Clean, sophisticated layouts (Compass)
- Accessible, data-driven approach (Redfin)
- Professional typography and spacing
- High-resolution property images
- Minimal, purposeful UI elements

---

## Database Schema

### `leads` table
```sql
CREATE TABLE leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    session_id TEXT,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `activity` table
```sql
CREATE TABLE activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    property_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Deployment

### Render Configuration

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
python app.py
```

**Environment Variables:**
- `OPENAI_API_KEY`
- `US_REALESTATE_KEY`
- `RAPIDAPI_KEY`
- `PORT` (auto-set by Render)

---

## Success Criteria

EstateIQ is successful when:

✅ It feels confident, not neutral  
✅ It explains price positioning clearly  
✅ It acknowledges uncertainty honestly  
✅ It helps users ask better questions  
✅ It does not make promises or absolute judgments  

---

## Product Definition

> "EstateIQ helps users understand what the market is actually saying—before they act—using opinionated, data-backed price intelligence with clear assumptions."

---

## Relationship to IDX

**IDX** = What's available  
**EstateIQ** = What it means

EstateIQ is designed to live **before, around, or alongside IDX**—never to replace it. IDX remains the primary inventory browsing experience, while EstateIQ provides market interpretation and decision confidence.

---

## What EstateIQ Evaluates

✅ **Does assess:**
- Price relative to comps
- Price per square foot vs norms
- Market positioning
- Risk and leverage implications

❌ **Does NOT assess:**
- Interior condition
- Build quality
- Renovation level
- Seller motivation

---

## License

Proprietary - All rights reserved

---

## Contact

For questions or support, contact: sold@reenadutta.com

---

## Acknowledgments

Built with:
- OpenAI GPT-4o-mini
- US Real Estate API (RapidAPI)
- Realtor16 API (RapidAPI)
- Flask & Python
- Deployed on Render
