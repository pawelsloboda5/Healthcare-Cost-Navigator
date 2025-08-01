from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Index, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from pgvector.sqlalchemy import Vector
from ..core.database import Base

class Provider(Base):
    __tablename__ = "providers"
    
    # Primary key - using CMS provider ID
    provider_id = Column(String(10), primary_key=True)
    
    # Provider information
    provider_name = Column(String(200), nullable=False)
    provider_city = Column(String(100), nullable=False)
    provider_state = Column(String(2), nullable=False)
    provider_zip_code = Column(String(10), nullable=False)
    provider_address = Column(String(500))
    
    # Additional fields from CSV
    provider_state_fips = Column(String(2))
    provider_ruca = Column(String(10))
    provider_ruca_description = Column(Text)
    
    # Geographic point for spatial queries (longitude, latitude)
    location = Column(Geometry('POINT', srid=4326))
    
    # Relationships
    procedures = relationship("ProviderProcedure", back_populates="provider")
    ratings = relationship("ProviderRating", back_populates="provider")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_provider_zip', 'provider_zip_code'),
        Index('idx_provider_state', 'provider_state'),
        Index('idx_provider_location', 'location', postgresql_using='gist'),
    )

class DRGProcedure(Base):
    __tablename__ = "drg_procedures"
    
    drg_code = Column(String(10), primary_key=True)
    drg_description = Column(Text, nullable=False)
    
    # Vector embedding for semantic search of procedure descriptions
    embedding = Column(Vector(1536))  # OpenAI text-embedding-3-small vector
    
    # Relationships
    provider_procedures = relationship("ProviderProcedure", back_populates="drg_procedure")
    
    # Index for text search (fallback) and vector search
    __table_args__ = (
        Index('idx_drg_description', 'drg_description', postgresql_using='gin', postgresql_ops={'drg_description': 'gin_trgm_ops'}),
        # Vector index will be created separately after embeddings are populated
    )

class ProviderProcedure(Base):
    __tablename__ = "provider_procedures"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(String(10), ForeignKey('providers.provider_id'), nullable=False)
    drg_code = Column(String(10), ForeignKey('drg_procedures.drg_code'), nullable=False)
    
    # Financial data
    total_discharges = Column(Integer, nullable=False)
    average_covered_charges = Column(Numeric(12, 2), nullable=False)
    average_total_payments = Column(Numeric(12, 2), nullable=False)
    average_medicare_payments = Column(Numeric(12, 2), nullable=False)
    
    # PERFORMANCE OPTIMIZATION: Denormalized provider state for faster queries
    provider_state = Column(String(2))  # Eliminates expensive JOINs to providers table
    
    # Relationships
    provider = relationship("Provider", back_populates="procedures")
    drg_procedure = relationship("DRGProcedure", back_populates="provider_procedures")
    
    # Indexes for efficient queries
    __table_args__ = (
        Index('idx_provider_drg', 'provider_id', 'drg_code'),
        Index('idx_avg_covered_charges', 'average_covered_charges'),
        Index('idx_drg_code', 'drg_code'),
    )

class ProviderRating(Base):
    __tablename__ = "provider_ratings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    provider_id = Column(String(10), ForeignKey('providers.provider_id'), nullable=False)
    
    # Rating information
    overall_rating = Column(Numeric(3, 1), nullable=False)  # 1.0 to 10.0
    quality_rating = Column(Numeric(3, 1))
    safety_rating = Column(Numeric(3, 1))
    patient_experience_rating = Column(Numeric(3, 1))
    
    # Relationship
    provider = relationship("Provider", back_populates="ratings")
    
    # Index
    __table_args__ = (
        Index('idx_provider_rating', 'provider_id'),
        Index('idx_overall_rating', 'overall_rating'),
    )

class CSVColumnMapping(Base):
    """Table to track the mapping between CSV columns and our normalized model fields"""
    __tablename__ = "csv_column_mappings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    csv_column_name = Column(String(100), nullable=False, unique=True)
    normalized_field_name = Column(String(100), nullable=False)
    table_name = Column(String(50), nullable=False)
    data_type = Column(String(50))
    description = Column(Text)
    
    # Index for quick lookups
    __table_args__ = (
        Index('idx_csv_column', 'csv_column_name'),
        Index('idx_normalized_field', 'normalized_field_name'),
    )


class TemplateCatalog(Base):
    """
    SQL Template Catalog for vector-based template matching and RAG
    Based on Template_Catalog_Vector_Search.md
    """
    __tablename__ = "template_catalog"
    
    template_id = Column(Integer, primary_key=True, autoincrement=True)
    canonical_sql = Column(Text, nullable=False)  # Normalized SQL with placeholders
    raw_sql = Column(Text, nullable=False)        # Original SQL template
    embedding = Column(Vector(1536))              # OpenAI text-embedding-3-small vector
    comment = Column(Text)                        # Human-readable description
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Indexes for efficient searches
    __table_args__ = (
        Index('idx_template_canonical', 'canonical_sql'),
        Index('idx_template_created', 'created_at'),
        # Vector index will be created separately after data load
    ) 