# CSV Column Mappings for Healthcare Cost Navigator

This document shows how the raw Medicare CSV data columns are mapped to our normalized database schema.

## Raw CSV Columns → Normalized Database Fields

### Provider Information (`providers` table)

| CSV Column | Normalized Field | Data Type | Description |
|------------|------------------|-----------|-------------|
| `Rndrng_Prvdr_CCN` | `provider_id` | String(10) | CMS Certification Number (Primary Key) |
| `Rndrng_Prvdr_Org_Name` | `provider_name` | String(200) | Provider Organization Name |
| `Rndrng_Prvdr_City` | `provider_city` | String(100) | Provider City |
| `Rndrng_Prvdr_St` | `provider_address` | String(500) | Provider Street Address |
| `Rndrng_Prvdr_State_FIPS` | `provider_state_fips` | String(2) | Provider State FIPS Code |
| `Rndrng_Prvdr_Zip5` | `provider_zip_code` | String(10) | Provider 5-digit ZIP Code |
| `Rndrng_Prvdr_State_Abrvtn` | `provider_state` | String(2) | Provider State Abbreviation |
| `Rndrng_Prvdr_RUCA` | `provider_ruca` | String(10) | Rural-Urban Commuting Area Code |
| `Rndrng_Prvdr_RUCA_Desc` | `provider_ruca_description` | Text | Rural-Urban Commuting Area Description |
| *[Geocoded]* | `location` | PostGIS Point | Geographic coordinates (lon, lat) |

### DRG Procedures (`drg_procedures` table)

| CSV Column | Normalized Field | Data Type | Description |
|------------|------------------|-----------|-------------|
| `DRG_Cd` | `drg_code` | String(10) | DRG Code (Primary Key) |
| `DRG_Desc` | `drg_description` | Text | DRG Description |

### Provider Procedures (`provider_procedures` table)

| CSV Column | Normalized Field | Data Type | Description |
|------------|------------------|-----------|-------------|
| `Rndrng_Prvdr_CCN` | `provider_id` | String(10) | Foreign Key to Providers |
| `DRG_Cd` | `drg_code` | String(10) | Foreign Key to DRG Procedures |
| `Tot_Dschrgs` | `total_discharges` | Integer | Total Discharges |
| `Avg_Submtd_Cvrd_Chrg` | `average_covered_charges` | Numeric(12,2) | Average Submitted Covered Charges |
| `Avg_Tot_Pymt_Amt` | `average_total_payments` | Numeric(12,2) | Average Total Payment Amount |
| `Avg_Mdcr_Pymt_Amt` | `average_medicare_payments` | Numeric(12,2) | Average Medicare Payment Amount |

### Provider Ratings (`provider_ratings` table)

| Data Source | Normalized Field | Data Type | Description |
|-------------|------------------|-----------|-------------|
| *[Generated]* | `overall_rating` | Numeric(3,1) | Overall Rating (1.0-10.0) |
| *[Generated]* | `quality_rating` | Numeric(3,1) | Quality Rating |
| *[Generated]* | `safety_rating` | Numeric(3,1) | Safety Rating |
| *[Generated]* | `patient_experience_rating` | Numeric(3,1) | Patient Experience Rating |

## Data Cleaning Process

### Null Value Handling
- **Provider ID**: Must be present and non-empty
- **Provider Name**: Must be present and non-empty
- **Geographic Fields**: City and State are required; ZIP code validated to 5 digits
- **Financial Data**: All financial columns must be present and >= 0
- **DRG Fields**: Code and description must be present

### Data Validation Rules
1. Provider IDs are cleaned to remove whitespace
2. Names and cities are title-cased
3. State abbreviations are uppercase
4. ZIP codes are zero-padded to 5 digits
5. Financial data is converted to numeric, invalid values filtered out
6. Addresses are geocoded to PostGIS Point geometry

### Geocoding Enhancement
- Full address geocoding: Street + City + State + ZIP
- Fallback to City + State + ZIP if street address fails
- Results cached to avoid duplicate API calls
- Rate-limited to respect Nominatim usage policies

## Sample Data Transformation

### Before (Raw CSV)
```
Rndrng_Prvdr_CCN: 010001
Rndrng_Prvdr_Org_Name: Southeast Health Medical Center
Rndrng_Prvdr_City: Dothan
Rndrng_Prvdr_St: 1108 Ross Clark Circle
Rndrng_Prvdr_State_Abrvtn: AL
Rndrng_Prvdr_Zip5: 36301
DRG_Cd: 023
DRG_Desc: CRANIOTOMY WITH MAJOR DEVICE IMPLANT...
Tot_Dschrgs: 25
Avg_Submtd_Cvrd_Chrg: 158541.64
```

### After (Normalized Database)
```sql
-- providers table
provider_id: '010001'
provider_name: 'Southeast Health Medical Center'
provider_city: 'Dothan'
provider_address: '1108 Ross Clark Circle'
provider_state: 'AL'
provider_zip_code: '36301'
location: POINT(-85.390251 31.223334)

-- drg_procedures table
drg_code: '023'
drg_description: 'CRANIOTOMY WITH MAJOR DEVICE IMPLANT...'

-- provider_procedures table
provider_id: '010001'
drg_code: '023'
total_discharges: 25
average_covered_charges: 158541.64
```

## Benefits of Normalization

1. **Consistent Naming**: Clear, descriptive field names
2. **Data Integrity**: Foreign key relationships prevent orphaned records
3. **Performance**: Proper indexing on commonly queried fields
4. **Spatial Queries**: PostGIS integration for location-based searches
5. **Extensibility**: Easy to add new fields or related tables
6. **Documentation**: Mapping table provides audit trail of transformations 