"""
DRG Code Lookup Service
Translates free-text procedure phrases to DRG codes using PostgreSQL similarity search
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)

_LOOKUP_SQL = """
SELECT drg_code
FROM   drg_procedures
WHERE  drg_description ILIKE '%' || :phrase || '%'
ORDER  BY similarity(drg_description, :phrase) DESC      -- pg_trgm
LIMIT  1;
"""

async def drg_code_from_phrase(session: AsyncSession, phrase: str) -> str | None:
    """
    Return the best-match DRG code for a free-text phrase such as
    'hip replacement'.  Requires the pg_trgm extension (already enabled).
    
    Args:
        session: Database session
        phrase: Free-text procedure description
        
    Returns:
        DRG code string if found, None otherwise
    """
    if not phrase or not phrase.strip():
        return None
        
    try:
        result = await session.execute(text(_LOOKUP_SQL), {"phrase": phrase.strip()})
        row = result.first()
        
        if row:
            logger.info(f"DRG lookup: '{phrase}' -> '{row.drg_code}'")
            return row.drg_code
        else:
            logger.warning(f"DRG lookup: no match found for '{phrase}'")
            return None
            
    except Exception as e:
        logger.error(f"DRG lookup failed for '{phrase}': {e}")
        return None 