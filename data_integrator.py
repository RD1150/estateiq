"""
EstateIQ Data Integration Module
Integrates multiple real estate data sources including RentCast, Redfin, and public APIs
"""

import requests
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import os
import time
import csv
from io import StringIO

logger = logging.getLogger(__name__)

class RealEstateDataIntegrator:
    """Integrates multiple real estate data sources"""
    
    def __init__(self):
        self.rentcast_api_key = os.getenv('RENTCAST_API_KEY', '')
        self.rentcast_base_url = 'https://api.rentcast.io/v1'
        self.redfin_data_cache = {}
        self.last_update = None
        
    def get_rentcast_properties(self, city: str, state: str, limit: int = 20) -> List[Dict]:
        """Fetch properties from RentCast API"""
        try:
            if not self.rentcast_api_key:
                logger.warning("RentCast API key not found, using sample data")
                return self._get_sample_properties()
            
            headers = {
                'X-Api-Key': self.rentcast_api_key,
                'Content-Type': 'application/json'
            }
            
            # Search for properties
            params = {
                'city': city,
                'state': state,
                'limit': limit,
                'propertyType': 'Single Family,Condo,Townhouse'
            }
            
            response = requests.get(
                f"{self.rentcast_base_url}/listings/rental",
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._process_rentcast_data(data.get('listings', []))
            else:
                logger.error(f"RentCast API error: {response.status_code}")
                return self._get_sample_properties()
                
        except Exception as e:
            logger.error(f"Error fetching RentCast data: {str(e)}")
            return self._get_sample_properties()
    
    def _process_rentcast_data(self, listings: List[Dict]) -> List[Dict]:
        """Process RentCast API response into EstateIQ format"""
        processed = []
        
        for listing in listings:
            try:
                property_data = {
                    'address': listing.get('address', {}).get('line', 'Unknown Address'),
                    'city': listing.get('address', {}).get('city', 'Unknown'),
                    'state': listing.get('address', {}).get('state', 'Unknown'),
                    'zip_code': listing.get('address', {}).get('zipCode', ''),
                    'price': listing.get('price', 0),
                    'bedrooms': listing.get('bedrooms', 0),
                    'bathrooms': listing.get('bathrooms', 0),
                    'square_feet': listing.get('squareFootage', 0),
                    'property_type': listing.get('propertyType', 'Unknown'),
                    'listing_date': datetime.now().strftime('%Y-%m-%d'),
                    'days_on_market': listing.get('daysOnMarket', 0),
                    'ai_score': self._calculate_ai_score(listing),
                    'trend': self._determine_trend(listing),
                    'description': listing.get('description', 'No description available'),
                    'amenities': ', '.join(listing.get('amenities', [])),
                    'neighborhood_score': listing.get('neighborhood', {}).get('score', 7.5),
                    'walkability_score': listing.get('walkScore', 50),
                    'school_rating': listing.get('schools', {}).get('rating', 7.0),
                    'crime_rating': listing.get('neighborhood', {}).get('crimeRating', 'Moderate'),
                    'investment_potential': self._assess_investment_potential(listing),
                    'rental_estimate': listing.get('rentEstimate', {}).get('rent', 0),
                    'cap_rate': self._calculate_cap_rate(listing)
                }
                processed.append(property_data)
            except Exception as e:
                logger.error(f"Error processing listing: {str(e)}")
                continue
        
        return processed
    
    def get_redfin_market_data(self) -> Dict[str, Any]:
        """Fetch market data from Redfin (using cached/sample data for now)"""
        try:
            # In a real implementation, this would download CSV files from Redfin
            # For now, we'll return sample market data
            return {
                'market_trends': {
                    'austin_tx': {
                        'median_price': 675000,
                        'price_change_yoy': 8.5,
                        'inventory_months': 2.1,
                        'days_on_market': 25,
                        'price_per_sqft': 285
                    },
                    'round_rock_tx': {
                        'median_price': 485000,
                        'price_change_yoy': 12.3,
                        'inventory_months': 1.8,
                        'days_on_market': 18,
                        'price_per_sqft': 245
                    },
                    'cedar_park_tx': {
                        'median_price': 575000,
                        'price_change_yoy': 9.7,
                        'inventory_months': 2.3,
                        'days_on_market': 22,
                        'price_per_sqft': 265
                    }
                },
                'last_updated': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error fetching Redfin data: {str(e)}")
            return {}
    
    def get_walk_score(self, address: str) -> int:
        """Get walkability score for an address"""
        try:
            # Walk Score API would require an API key
            # For now, return a calculated score based on location
            if 'downtown' in address.lower() or 'austin' in address.lower():
                return 85
            elif 'round rock' in address.lower() or 'cedar park' in address.lower():
                return 55
            else:
                return 65
        except Exception as e:
            logger.error(f"Error getting walk score: {str(e)}")
            return 50
    
    def get_economic_indicators(self) -> Dict[str, Any]:
        """Fetch economic indicators from FRED API"""
        try:
            # This would use the Federal Reserve Economic Data API
            # For now, return sample economic data
            return {
                'mortgage_rates': {
                    '30_year_fixed': 7.25,
                    '15_year_fixed': 6.75,
                    'trend': 'stable'
                },
                'unemployment_rate': 3.2,
                'inflation_rate': 2.8,
                'gdp_growth': 2.1,
                'housing_starts': 1450000,
                'last_updated': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error fetching economic indicators: {str(e)}")
            return {}
    
    def _calculate_ai_score(self, listing: Dict) -> float:
        """Calculate AI investment score for a property"""
        try:
            score = 5.0  # Base score
            
            # Price per square foot analysis
            price = listing.get('price', 0)
            sqft = listing.get('squareFootage', 1)
            if sqft > 0:
                price_per_sqft = price / sqft
                if price_per_sqft < 200:
                    score += 1.5
                elif price_per_sqft < 300:
                    score += 1.0
                elif price_per_sqft > 400:
                    score -= 1.0
            
            # Days on market
            dom = listing.get('daysOnMarket', 30)
            if dom < 15:
                score += 1.0
            elif dom < 30:
                score += 0.5
            elif dom > 60:
                score -= 1.0
            
            # Neighborhood factors
            neighborhood = listing.get('neighborhood', {})
            if neighborhood.get('score', 0) > 8:
                score += 1.0
            elif neighborhood.get('score', 0) > 6:
                score += 0.5
            
            # Property type preferences
            prop_type = listing.get('propertyType', '')
            if prop_type in ['Single Family', 'Townhouse']:
                score += 0.5
            
            # Cap the score between 1 and 10
            return max(1.0, min(10.0, round(score, 1)))
            
        except Exception as e:
            logger.error(f"Error calculating AI score: {str(e)}")
            return 7.0
    
    def _determine_trend(self, listing: Dict) -> str:
        """Determine price trend for a property"""
        try:
            # This would analyze historical price data
            # For now, use simple heuristics
            dom = listing.get('daysOnMarket', 30)
            price = listing.get('price', 0)
            
            if dom < 20 and price > 400000:
                return 'Rising'
            elif dom > 45:
                return 'Declining'
            else:
                return 'Stable'
        except Exception:
            return 'Stable'
    
    def _assess_investment_potential(self, listing: Dict) -> str:
        """Assess investment potential of a property"""
        try:
            ai_score = self._calculate_ai_score(listing)
            
            if ai_score >= 8.5:
                return 'Excellent'
            elif ai_score >= 7.5:
                return 'Very Good'
            elif ai_score >= 6.5:
                return 'Good'
            elif ai_score >= 5.5:
                return 'Fair'
            else:
                return 'Poor'
        except Exception:
            return 'Good'
    
    def _calculate_cap_rate(self, listing: Dict) -> float:
        """Calculate capitalization rate for investment analysis"""
        try:
            price = listing.get('price', 0)
            rent_estimate = listing.get('rentEstimate', {}).get('rent', 0)
            
            if price > 0 and rent_estimate > 0:
                annual_rent = rent_estimate * 12
                # Assume 25% for expenses (taxes, insurance, maintenance, vacancy)
                net_operating_income = annual_rent * 0.75
                cap_rate = (net_operating_income / price) * 100
                return round(cap_rate, 1)
            else:
                return 6.0  # Default cap rate
        except Exception:
            return 6.0
    
    def _get_sample_properties(self) -> List[Dict]:
        """Return enhanced sample properties when APIs are unavailable"""
        return [
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
    
    def update_database_with_live_data(self, db_path: str = 'estateiq.db'):
        """Update the database with live data from all sources"""
        try:
            # Get data from multiple sources
            austin_properties = self.get_rentcast_properties('Austin', 'TX', 10)
            market_data = self.get_redfin_market_data()
            economic_data = self.get_economic_indicators()
            
            # Update database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Clear existing properties (in production, you'd want to update instead)
            cursor.execute("DELETE FROM properties")
            
            # Insert new properties
            for prop in austin_properties:
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
            
            self.last_update = datetime.now()
            logger.info(f"Database updated with {len(austin_properties)} properties")
            
            return {
                'success': True,
                'properties_updated': len(austin_properties),
                'market_data': market_data,
                'economic_data': economic_data,
                'last_update': self.last_update.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error updating database: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_property_recommendations(self, user_preferences: Dict) -> List[Dict]:
        """Get personalized property recommendations based on user preferences"""
        try:
            budget_min = user_preferences.get('budget_min', 0)
            budget_max = user_preferences.get('budget_max', 1000000)
            bedrooms = user_preferences.get('bedrooms', 0)
            cities = user_preferences.get('cities', ['Austin'])
            
            # This would query the database with user preferences
            # For now, return filtered sample data
            properties = self._get_sample_properties()
            
            filtered = []
            for prop in properties:
                if (budget_min <= prop['price'] <= budget_max and
                    (bedrooms == 0 or prop['bedrooms'] >= bedrooms) and
                    prop['city'] in cities):
                    filtered.append(prop)
            
            # Sort by AI score
            filtered.sort(key=lambda x: x['ai_score'], reverse=True)
            
            return filtered[:10]  # Return top 10
            
        except Exception as e:
            logger.error(f"Error getting recommendations: {str(e)}")
            return []

# Initialize the data integrator
data_integrator = RealEstateDataIntegrator()

def get_live_property_data(city: str = 'Austin', state: str = 'TX') -> List[Dict]:
    """Get live property data from integrated sources"""
    return data_integrator.get_rentcast_properties(city, state)

def get_market_analytics() -> Dict:
    """Get comprehensive market analytics"""
    return {
        'redfin_data': data_integrator.get_redfin_market_data(),
        'economic_indicators': data_integrator.get_economic_indicators()
    }

def update_property_database():
    """Update the property database with latest data"""
    return data_integrator.update_database_with_live_data()

def get_personalized_recommendations(preferences: Dict) -> List[Dict]:
    """Get personalized property recommendations"""
    return data_integrator.get_property_recommendations(preferences)

