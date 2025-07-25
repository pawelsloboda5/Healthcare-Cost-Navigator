#!/usr/bin/env python3
"""
ETL Script for Healthcare Cost Navigator
Loads Medicare data from CSV into PostgreSQL database
"""
import asyncio
import pandas as pd
import httpx
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import random
from typing import Optional, Tuple, Dict
import logging

# Add the app directory to the Python path BEFORE importing app modules
app_dir = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_dir))

# Now import the app modules
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from core.database import AsyncSessionLocal, init_db
from models.models import Provider, DRGProcedure, ProviderProcedure, ProviderRating, CSVColumnMapping


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

#load env from parent directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

MAPS_KEY = os.environ["AZURE_MAPS_KEY"]
SEARCH_URL = f"https://atlas.microsoft.com/search/Address/json?api-version=1.0&subscription-key={MAPS_KEY}"

class HealthcareETL:
    def __init__(self, csv_file_path: str = "../../data/medicare-data-raw.csv"):
        self.csv_file_path = csv_file_path
        self.azure_maps_client = httpx.AsyncClient(
            timeout=15.0,
            headers={'User-Agent': 'Healthcare-Cost-Navigator/1.0'}
        )
        self.geocoding_cache = {}
        self.column_mappings = self._get_column_mappings()
        
    def _get_column_mappings(self) -> Dict[str, Dict]:
        """Define the mapping between CSV columns and normalized model fields"""
        return {
            # Provider mappings
            'Rndrng_Prvdr_CCN': {
                'normalized_field': 'provider_id',
                'table': 'providers',
                'data_type': 'string',
                'description': 'CMS Certification Number (Provider ID)'
            },
            'Rndrng_Prvdr_Org_Name': {
                'normalized_field': 'provider_name',
                'table': 'providers',
                'data_type': 'string',
                'description': 'Provider Organization Name'
            },
            'Rndrng_Prvdr_City': {
                'normalized_field': 'provider_city',
                'table': 'providers',
                'data_type': 'string',
                'description': 'Provider City'
            },
            'Rndrng_Prvdr_St': {
                'normalized_field': 'provider_address',
                'table': 'providers',
                'data_type': 'string',
                'description': 'Provider Street Address'
            },
            'Rndrng_Prvdr_State_FIPS': {
                'normalized_field': 'provider_state_fips',
                'table': 'providers',
                'data_type': 'string',
                'description': 'Provider State FIPS Code'
            },
            'Rndrng_Prvdr_Zip5': {
                'normalized_field': 'provider_zip_code',
                'table': 'providers',
                'data_type': 'string',
                'description': 'Provider 5-digit ZIP Code'
            },
            'Rndrng_Prvdr_State_Abrvtn': {
                'normalized_field': 'provider_state',
                'table': 'providers',
                'data_type': 'string',
                'description': 'Provider State Abbreviation'
            },
            'Rndrng_Prvdr_RUCA': {
                'normalized_field': 'provider_ruca',
                'table': 'providers',
                'data_type': 'string',
                'description': 'Rural-Urban Commuting Area Code'
            },
            'Rndrng_Prvdr_RUCA_Desc': {
                'normalized_field': 'provider_ruca_description',
                'table': 'providers',
                'data_type': 'text',
                'description': 'Rural-Urban Commuting Area Description'
            },
            # DRG Procedure mappings
            'DRG_Cd': {
                'normalized_field': 'drg_code',
                'table': 'drg_procedures',
                'data_type': 'string',
                'description': 'DRG Code'
            },
            'DRG_Desc': {
                'normalized_field': 'drg_description',
                'table': 'drg_procedures',
                'data_type': 'text',
                'description': 'DRG Description'
            },
            # Provider Procedure mappings
            'Tot_Dschrgs': {
                'normalized_field': 'total_discharges',
                'table': 'provider_procedures',
                'data_type': 'integer',
                'description': 'Total Discharges'
            },
            'Avg_Submtd_Cvrd_Chrg': {
                'normalized_field': 'average_covered_charges',
                'table': 'provider_procedures',
                'data_type': 'numeric',
                'description': 'Average Submitted Covered Charges'
            },
            'Avg_Tot_Pymt_Amt': {
                'normalized_field': 'average_total_payments',
                'table': 'provider_procedures',
                'data_type': 'numeric',
                'description': 'Average Total Payment Amount'
            },
            'Avg_Mdcr_Pymt_Amt': {
                'normalized_field': 'average_medicare_payments',
                'table': 'provider_procedures',
                'data_type': 'numeric',
                'description': 'Average Medicare Payment Amount'
            }
        }
        
    async def geocode_address(self, address: str, city: str, state: str, zip_code: str) -> Optional[Tuple[float, float]]:
        """Geocode a full address using Azure Maps API"""
        # Build a comprehensive address string
        address_parts = []
        if address and address.strip() and address.strip() != 'nan':
            address_parts.append(address.strip())
        if city and city.strip():
            address_parts.append(city.strip())
        if state and state.strip():
            address_parts.append(state.strip())
        if zip_code and zip_code.strip():
            address_parts.append(zip_code.strip())
            
        full_address = ", ".join(address_parts) + ", USA"
        cache_key = full_address.lower()
        
        if cache_key in self.geocoding_cache:
            return self.geocoding_cache[cache_key]
            
        try:
            # Azure Maps has much higher rate limits - minimal delay
            await asyncio.sleep(0.1)
            
            response = await self.azure_maps_client.get(
                SEARCH_URL,
                params={
                    "query": full_address,
                    "limit": 1,
                    "countrySet": "US"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("results") and len(data["results"]) > 0:
                    result = data["results"][0]
                    position = result.get("position")
                    if position:
                        lat = float(position["lat"])
                        lon = float(position["lon"])
                        coordinates = (lon, lat)  # PostGIS uses lon, lat order
                        self.geocoding_cache[cache_key] = coordinates
                        logger.debug(f"Geocoded {full_address} -> {coordinates}")
                        return coordinates
                    
        except Exception as e:
            logger.warning(f"Azure Maps geocoding failed for {full_address}: {e}")
            
        # If full address fails, try just city, state, zip
        if address:  # Only retry if we had a street address
            fallback_address = f"{city}, {state} {zip_code}, USA"
            if fallback_address != full_address:
                return await self._geocode_fallback(fallback_address, cache_key)
            
        self.geocoding_cache[cache_key] = None
        return None
        
    async def _geocode_fallback(self, fallback_address: str, original_cache_key: str) -> Optional[Tuple[float, float]]:
        """Fallback geocoding with just city, state, zip using Azure Maps"""
        try:
            await asyncio.sleep(0.1)
            
            response = await self.azure_maps_client.get(
                SEARCH_URL,
                params={
                    "query": fallback_address,
                    "limit": 1,
                    "countrySet": "US"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("results") and len(data["results"]) > 0:
                    result = data["results"][0]
                    position = result.get("position")
                    if position:
                        lat = float(position["lat"])
                        lon = float(position["lon"])
                        coordinates = (lon, lat)
                        self.geocoding_cache[original_cache_key] = coordinates
                        logger.debug(f"Fallback geocoded {fallback_address} -> {coordinates}")
                        return coordinates
                    
        except Exception as e:
            logger.warning(f"Azure Maps fallback geocoding failed for {fallback_address}: {e}")
            
        self.geocoding_cache[original_cache_key] = None
        return None
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate the Medicare data with comprehensive null handling"""
        logger.info(f"Cleaning data for {len(df)} records")
        
        # Create a copy to avoid modifying the original
        df = df.copy()
        
        # Log initial data quality
        logger.info(f"Initial data shape: {df.shape}")
        logger.info("Columns with null values:")
        null_counts = df.isnull().sum()
        for col, count in null_counts[null_counts > 0].items():
            logger.info(f"  {col}: {count} nulls ({count/len(df)*100:.1f}%)")
        
        # Remove completely empty rows
        df = df.dropna(how='all')
        logger.info(f"After removing empty rows: {len(df)} records")
        
        # Clean and validate required fields
        
        # Provider ID - must be present and valid
        df['Rndrng_Prvdr_CCN'] = df['Rndrng_Prvdr_CCN'].astype(str).str.strip()
        df = df[df['Rndrng_Prvdr_CCN'].notna() & (df['Rndrng_Prvdr_CCN'] != '') & (df['Rndrng_Prvdr_CCN'] != 'nan')]
        
        # Provider name - must be present
        df['Rndrng_Prvdr_Org_Name'] = df['Rndrng_Prvdr_Org_Name'].fillna('').str.strip().str.title()
        df = df[df['Rndrng_Prvdr_Org_Name'] != '']
        
        # Geographic fields - clean and validate
        df['Rndrng_Prvdr_City'] = df['Rndrng_Prvdr_City'].fillna('').str.strip().str.title()
        df['Rndrng_Prvdr_State_Abrvtn'] = df['Rndrng_Prvdr_State_Abrvtn'].fillna('').str.strip().str.upper()
        
        # Clean ZIP code - ensure 5 digits, handle nulls
        df['Rndrng_Prvdr_Zip5'] = df['Rndrng_Prvdr_Zip5'].fillna('')
        df['Rndrng_Prvdr_Zip5'] = df['Rndrng_Prvdr_Zip5'].astype(str).str.strip()
        df['Rndrng_Prvdr_Zip5'] = df['Rndrng_Prvdr_Zip5'].apply(
            lambda x: x.zfill(5) if x and x != 'nan' and x.isdigit() and len(x) <= 5 else ''
        )
        
        # Address field
        df['Rndrng_Prvdr_St'] = df['Rndrng_Prvdr_St'].fillna('').str.strip()
        
        # State FIPS and RUCA codes
        df['Rndrng_Prvdr_State_FIPS'] = df['Rndrng_Prvdr_State_FIPS'].fillna('').astype(str).str.strip()
        df['Rndrng_Prvdr_RUCA'] = df['Rndrng_Prvdr_RUCA'].fillna('').astype(str).str.strip()
        df['Rndrng_Prvdr_RUCA_Desc'] = df['Rndrng_Prvdr_RUCA_Desc'].fillna('').str.strip()
        
        # DRG fields - must be present and valid
        df['DRG_Cd'] = df['DRG_Cd'].fillna('').astype(str).str.strip()
        df['DRG_Desc'] = df['DRG_Desc'].fillna('').str.strip()
        df = df[(df['DRG_Cd'] != '') & (df['DRG_Desc'] != '')]
        
        # Financial data - convert to numeric, handle nulls
        financial_columns = ['Avg_Submtd_Cvrd_Chrg', 'Avg_Tot_Pymt_Amt', 'Avg_Mdcr_Pymt_Amt', 'Tot_Dschrgs']
        
        for col in financial_columns:
            # Convert to numeric, coercing errors to NaN
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        # Remove rows where any financial data is missing or invalid
        df = df.dropna(subset=financial_columns)
        
        # Additional data validation
        # Remove rows with negative financial values
        df = df[
            (df['Avg_Submtd_Cvrd_Chrg'] >= 0) & 
            (df['Avg_Tot_Pymt_Amt'] >= 0) & 
            (df['Avg_Mdcr_Pymt_Amt'] >= 0) & 
            (df['Tot_Dschrgs'] > 0)
        ]
        
        # Remove rows with essential geographic info missing
        df = df[
            (df['Rndrng_Prvdr_City'] != '') & 
            (df['Rndrng_Prvdr_State_Abrvtn'] != '')
        ]
        
        logger.info(f"After cleaning and validation: {len(df)} records")
        
        # Log final data quality
        logger.info(f"Final data shape: {df.shape}")
        remaining_nulls = df.isnull().sum()
        if remaining_nulls.sum() > 0:
            logger.info("Remaining columns with null values:")
            for col, count in remaining_nulls[remaining_nulls > 0].items():
                logger.info(f"  {col}: {count} nulls ({count/len(df)*100:.1f}%)")
        
        return df
    
    def generate_mock_ratings(self, provider_ids: list) -> list:
        """Generate mock star ratings for providers"""
        ratings = []
        
        for provider_id in provider_ids:
            # Generate realistic ratings with some correlation
            base_rating = random.uniform(6.0, 9.5)
            
            overall_rating = round(base_rating + random.uniform(-0.5, 0.5), 1)
            quality_rating = round(overall_rating + random.uniform(-1.0, 1.0), 1)
            safety_rating = round(overall_rating + random.uniform(-0.8, 0.8), 1)
            patient_exp_rating = round(overall_rating + random.uniform(-1.2, 1.2), 1)
            
            # Ensure ratings are within bounds
            overall_rating = max(1.0, min(10.0, overall_rating))
            quality_rating = max(1.0, min(10.0, quality_rating))
            safety_rating = max(1.0, min(10.0, safety_rating))
            patient_exp_rating = max(1.0, min(10.0, patient_exp_rating))
            
            ratings.append({
                'provider_id': provider_id,
                'overall_rating': overall_rating,
                'quality_rating': quality_rating,
                'safety_rating': safety_rating,
                'patient_experience_rating': patient_exp_rating
            })
            
        return ratings
    
    async def initialize_column_mappings(self, session: AsyncSession):
        """Initialize the CSV column mapping table"""
        logger.info("Initializing CSV column mappings")
        
        # Clear existing mappings
        await session.execute(text("DELETE FROM csv_column_mappings"))
        
        mappings = []
        for csv_col, mapping_info in self.column_mappings.items():
            mapping = CSVColumnMapping(
                csv_column_name=csv_col,
                normalized_field_name=mapping_info['normalized_field'],
                table_name=mapping_info['table'],
                data_type=mapping_info['data_type'],
                description=mapping_info['description']
            )
            mappings.append(mapping)
        
        session.add_all(mappings)
        await session.flush()
        logger.info(f"Initialized {len(mappings)} column mappings")

    async def load_data(self):
        """Main ETL process"""
        logger.info("Starting ETL process")
        
        # Initialize database
        await init_db()
        
        # Read and clean data
        logger.info(f"Reading data from {self.csv_file_path}")
        if not os.path.exists(self.csv_file_path):
            raise FileNotFoundError(f"CSV file not found: {self.csv_file_path}")
            
        df = pd.read_csv(self.csv_file_path)
        df = self.clean_data(df)
        
        async with AsyncSessionLocal() as session:
            try:
                # Enable required extensions
                await session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
                await session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                
                # Initialize column mappings
                await self.initialize_column_mappings(session)
                
                # Load data in order of dependencies
                await self.load_providers(session, df)
                await self.load_drg_procedures(session, df)
                await self.load_provider_procedures(session, df)
                await self.load_provider_ratings(session, df)
                
                await session.commit()
                logger.info("ETL process completed successfully")
                
            except Exception as e:
                await session.rollback()
                logger.error(f"ETL process failed: {e}")
                raise
        
        await self.azure_maps_client.aclose()
    
    async def load_providers(self, session: AsyncSession, df: pd.DataFrame):
        """Load unique providers with enhanced geocoding"""
        logger.info("Loading providers")
        
        # Get unique providers
        providers_df = df.groupby('Rndrng_Prvdr_CCN').first().reset_index()
        
        providers = []
        geocoded_count = 0
        
        for idx, row in providers_df.iterrows():
            # Geocode the provider location
            coordinates = await self.geocode_address(
                row.get('Rndrng_Prvdr_St', ''),
                row['Rndrng_Prvdr_City'], 
                row['Rndrng_Prvdr_State_Abrvtn'], 
                str(row['Rndrng_Prvdr_Zip5'])
            )
            
            location_wkt = None
            if coordinates:
                lon, lat = coordinates
                location_wkt = f"POINT({lon} {lat})"
                geocoded_count += 1
            
            provider = Provider(
                provider_id=str(row['Rndrng_Prvdr_CCN']),
                provider_name=row['Rndrng_Prvdr_Org_Name'],
                provider_city=row['Rndrng_Prvdr_City'],
                provider_state=row['Rndrng_Prvdr_State_Abrvtn'],
                provider_zip_code=str(row['Rndrng_Prvdr_Zip5']),
                provider_address=row.get('Rndrng_Prvdr_St', ''),
                provider_state_fips=str(row.get('Rndrng_Prvdr_State_FIPS', '')),
                provider_ruca=str(row.get('Rndrng_Prvdr_RUCA', '')),
                provider_ruca_description=row.get('Rndrng_Prvdr_RUCA_Desc', ''),
                location=location_wkt
            )
            providers.append(provider)
            
            # Log progress every 50 providers
            if (idx + 1) % 50 == 0:
                logger.info(f"Processed {idx + 1}/{len(providers_df)} providers, geocoded {geocoded_count}")
        
        session.add_all(providers)
        await session.flush()
        logger.info(f"Loaded {len(providers)} providers, successfully geocoded {geocoded_count} ({geocoded_count/len(providers)*100:.1f}%)")
    
    async def load_drg_procedures(self, session: AsyncSession, df: pd.DataFrame):
        """Load unique DRG procedures"""
        logger.info("Loading DRG procedures")
        
        # Get unique DRG procedures
        drg_df = df[['DRG_Cd', 'DRG_Desc']].drop_duplicates()
        
        procedures = []
        for _, row in drg_df.iterrows():
            procedure = DRGProcedure(
                drg_code=str(row['DRG_Cd']),
                drg_description=row['DRG_Desc']
            )
            procedures.append(procedure)
        
        session.add_all(procedures)
        await session.flush()
        logger.info(f"Loaded {len(procedures)} DRG procedures")
    
    async def load_provider_procedures(self, session: AsyncSession, df: pd.DataFrame):
        """Load provider procedure data"""
        logger.info("Loading provider procedures")
        
        procedures = []
        for _, row in df.iterrows():
            procedure = ProviderProcedure(
                provider_id=str(row['Rndrng_Prvdr_CCN']),
                drg_code=str(row['DRG_Cd']),
                total_discharges=int(row['Tot_Dschrgs']),
                average_covered_charges=float(row['Avg_Submtd_Cvrd_Chrg']),
                average_total_payments=float(row['Avg_Tot_Pymt_Amt']),
                average_medicare_payments=float(row['Avg_Mdcr_Pymt_Amt'])
            )
            procedures.append(procedure)
        
        session.add_all(procedures)
        await session.flush()
        logger.info(f"Loaded {len(procedures)} provider procedures")
    
    async def load_provider_ratings(self, session: AsyncSession, df: pd.DataFrame):
        """Load mock provider ratings"""
        logger.info("Loading provider ratings")
        
        # Get unique provider IDs
        provider_ids = df['Rndrng_Prvdr_CCN'].unique().tolist()
        mock_ratings = self.generate_mock_ratings(provider_ids)
        
        ratings = []
        for rating_data in mock_ratings:
            rating = ProviderRating(**rating_data)
            ratings.append(rating)
        
        session.add_all(ratings)
        await session.flush()
        logger.info(f"Loaded {len(ratings)} provider ratings")

async def main():
    """Run the ETL process"""
    etl = HealthcareETL()
    await etl.load_data()

if __name__ == "__main__":
    asyncio.run(main()) 