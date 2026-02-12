"""
Clinical Guidelines Data Models

Pydantic models for the Clinical Guidelines Compliance System,
including guideline documents, compliance results, and search results.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class GuidelineSpecialty(str, Enum):
    """Medical specialties for clinical guidelines."""
    CARDIOLOGY = "cardiology"
    PULMONOLOGY = "pulmonology"
    ENDOCRINOLOGY = "endocrinology"
    NEPHROLOGY = "nephrology"
    GASTROENTEROLOGY = "gastroenterology"
    NEUROLOGY = "neurology"
    INFECTIOUS_DISEASE = "infectious_disease"
    RHEUMATOLOGY = "rheumatology"
    ONCOLOGY = "oncology"
    HEMATOLOGY = "hematology"
    GERIATRICS = "geriatrics"
    PEDIATRICS = "pediatrics"
    PSYCHIATRY = "psychiatry"
    OBSTETRICS = "obstetrics"
    GENERAL = "general"


class GuidelineSource(str, Enum):
    """Source organizations for clinical guidelines."""
    AHA = "AHA"  # American Heart Association
    ACC = "ACC"  # American College of Cardiology
    AHA_ACC = "AHA/ACC"  # Joint guidelines
    ADA = "ADA"  # American Diabetes Association
    GOLD = "GOLD"  # Global Initiative for Chronic Obstructive Lung Disease
    NICE = "NICE"  # National Institute for Health and Care Excellence
    HFSA = "HFSA"  # Heart Failure Society of America
    USPSTF = "USPSTF"  # US Preventive Services Task Force
    IDSA = "IDSA"  # Infectious Diseases Society of America
    ACR = "ACR"  # American College of Rheumatology
    ASCO = "ASCO"  # American Society of Clinical Oncology
    AAN = "AAN"  # American Academy of Neurology
    APA = "APA"  # American Psychiatric Association
    ACOG = "ACOG"  # American College of Obstetricians and Gynecologists
    AAP = "AAP"  # American Academy of Pediatrics
    AGS = "AGS"  # American Geriatrics Society
    OTHER = "OTHER"


class GuidelineType(str, Enum):
    """Types of clinical guidelines."""
    TREATMENT_PROTOCOL = "treatment_protocol"
    DIAGNOSTIC_CRITERIA = "diagnostic_criteria"
    SCREENING_RECOMMENDATION = "screening_recommendation"
    PREVENTION_GUIDELINE = "prevention_guideline"
    MANAGEMENT_ALGORITHM = "management_algorithm"
    QUALITY_MEASURE = "quality_measure"
    CLINICAL_PATHWAY = "clinical_pathway"


class RecommendationClass(str, Enum):
    """Guideline recommendation strength classes."""
    CLASS_I = "I"  # Strong recommendation - benefit >>> risk
    CLASS_IIA = "IIa"  # Moderate recommendation - benefit >> risk
    CLASS_IIB = "IIb"  # Weak recommendation - benefit >= risk
    CLASS_III = "III"  # No benefit or harmful


class EvidenceLevel(str, Enum):
    """Level of evidence supporting the recommendation."""
    LEVEL_A = "A"  # Multiple RCTs or meta-analyses
    LEVEL_B = "B"  # Single RCT or non-randomized studies
    LEVEL_BR = "B-R"  # Randomized studies
    LEVEL_BNR = "B-NR"  # Non-randomized studies
    LEVEL_C = "C"  # Consensus opinion or case studies
    LEVEL_CLD = "C-LD"  # Limited data
    LEVEL_CEO = "C-EO"  # Expert opinion


class ComplianceStatus(str, Enum):
    """Status of compliance with a guideline."""
    COMPLIANT = "compliant"
    GAP = "gap"
    WARNING = "warning"
    NOT_APPLICABLE = "not_applicable"


class SectionType(str, Enum):
    """Types of sections in guideline documents."""
    RECOMMENDATION = "recommendation"
    WARNING = "warning"
    EVIDENCE = "evidence"
    RATIONALE = "rationale"
    MONITORING = "monitoring"
    CONTRAINDICATION = "contraindication"


class GuidelineUploadStatus(str, Enum):
    """Status of guideline document upload and processing."""
    PENDING = "pending"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    SYNCING = "syncing"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# Dataclasses for compliance results
# ============================================================================

@dataclass
class GuidelineReference:
    """Reference to a specific guideline recommendation."""
    source: str  # e.g., "AHA/ACC"
    title: str  # e.g., "Hypertension Guidelines 2024"
    section: str  # e.g., "Section 8.2"
    recommendation_class: str  # e.g., "Class I"
    evidence_level: str  # e.g., "Level A"
    year: Optional[int] = None
    url: Optional[str] = None


@dataclass
class ComplianceItem:
    """A single compliance check result against a guideline."""
    guideline_ref: GuidelineReference
    status: str  # "compliant", "gap", "warning"
    finding: str  # What was found/missing in the SOAP note
    suggestion: str  # Action to take for compliance
    relevance_score: float = 0.0  # How relevant this guideline is to the case
    chunk_text: Optional[str] = None  # The guideline text that was matched


@dataclass
class ComplianceResult:
    """Complete compliance analysis result."""
    overall_score: float  # 0.0 to 1.0
    items: list = field(default_factory=list)  # List[ComplianceItem]
    guidelines_checked: int = 0
    compliant_count: int = 0
    gap_count: int = 0
    warning_count: int = 0
    processing_time_ms: float = 0.0
    soap_note_summary: Optional[str] = None
    specialties_analyzed: list = field(default_factory=list)  # List[str]


@dataclass
class ConditionFinding:
    """A single compliance finding for a condition."""
    status: str  # ALIGNED | GAP | REVIEW
    finding: str
    guideline_reference: str
    recommendation: str = ""  # empty for ALIGNED
    citation_verified: bool = False


@dataclass
class ConditionCompliance:
    """Compliance results for a single condition."""
    condition: str
    status: str  # ALIGNED | GAP | REVIEW (worst finding)
    findings: list = field(default_factory=list)  # List[ConditionFinding]
    score: float = 0.0
    guidelines_matched: int = 0


@dataclass
class ComplianceAnalysisResult:
    """Complete condition-centric compliance result."""
    conditions: list = field(default_factory=list)  # List[ConditionCompliance]
    overall_score: float = 0.0
    has_sufficient_data: bool = False
    guidelines_searched: int = 0
    disclaimer: str = (
        "AI-assisted analysis for clinical decision support. "
        "Verify findings against current clinical guidelines."
    )


# ============================================================================
# Pydantic models for database and API
# ============================================================================

class GuidelineMetadata(BaseModel):
    """Metadata for a clinical guideline document."""
    title: Optional[str] = None
    specialty: GuidelineSpecialty = GuidelineSpecialty.GENERAL
    source: str = GuidelineSource.OTHER.value
    version: Optional[str] = None
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None
    document_type: GuidelineType = GuidelineType.TREATMENT_PROTOCOL
    authors: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    conditions_covered: list[str] = Field(default_factory=list)
    medications_covered: list[str] = Field(default_factory=list)
    superseded_by: Optional[str] = None


class GuidelineChunk(BaseModel):
    """A chunk of text from a guideline document with metadata."""
    chunk_index: int
    chunk_text: str
    token_count: int
    section_type: SectionType = SectionType.RECOMMENDATION
    recommendation_class: Optional[str] = None
    evidence_level: Optional[str] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    neon_id: Optional[str] = None
    embedding: Optional[list[float]] = None


class GuidelineDocument(BaseModel):
    """A clinical guideline document in the system."""
    guideline_id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    file_type: str  # pdf, docx, txt
    file_path: Optional[str] = None
    file_size_bytes: int = 0
    page_count: int = 0
    upload_status: GuidelineUploadStatus = GuidelineUploadStatus.PENDING
    chunk_count: int = 0
    neon_synced: bool = False
    neo4j_synced: bool = False
    error_message: Optional[str] = None
    superseded_by: Optional[str] = None
    metadata: GuidelineMetadata = Field(default_factory=GuidelineMetadata)
    chunks: list[GuidelineChunk] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


class GuidelineSearchQuery(BaseModel):
    """Query for searching clinical guidelines."""
    query_text: str
    specialties: Optional[list[str]] = None  # Filter by specialty
    sources: Optional[list[str]] = None  # Filter by source organization
    recommendation_class: Optional[str] = None  # Filter by recommendation strength
    evidence_level: Optional[str] = None  # Filter by evidence level
    top_k: int = 10
    similarity_threshold: float = 0.6
    include_metadata: bool = True


class GuidelineSearchResult(BaseModel):
    """A single result from guideline search."""
    guideline_id: str
    chunk_index: int
    chunk_text: str
    similarity_score: float
    section_type: str = SectionType.RECOMMENDATION.value
    recommendation_class: Optional[str] = None
    evidence_level: Optional[str] = None
    guideline_title: Optional[str] = None
    guideline_source: Optional[str] = None
    guideline_version: Optional[str] = None
    specialty: Optional[str] = None
    effective_date: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    is_superseded: bool = False


class GuidelineUploadRequest(BaseModel):
    """Request for uploading a clinical guideline."""
    file_paths: list[str]
    specialty: str = GuidelineSpecialty.GENERAL.value
    source: str = GuidelineSource.OTHER.value
    version: Optional[str] = None
    effective_date: Optional[str] = None
    document_type: str = GuidelineType.TREATMENT_PROTOCOL.value
    keywords: list[str] = Field(default_factory=list)
    extract_recommendations: bool = True
    build_knowledge_graph: bool = True


class GuidelineUploadProgress(BaseModel):
    """Progress update for guideline upload."""
    guideline_id: str
    filename: str
    status: GuidelineUploadStatus
    progress_percent: float = 0.0
    current_step: str = ""
    error_message: Optional[str] = None


class GuidelineListItem(BaseModel):
    """Summary item for guideline library display."""
    guideline_id: str
    filename: str
    title: Optional[str] = None
    specialty: str
    source: str
    version: Optional[str] = None
    effective_date: Optional[str] = None
    document_type: str
    chunk_count: int
    upload_status: GuidelineUploadStatus
    neon_synced: bool
    neo4j_synced: bool
    is_superseded: bool = False
    superseded_by: Optional[str] = None
    created_at: datetime


class ComplianceCheckRequest(BaseModel):
    """Request to check SOAP note compliance against guidelines."""
    soap_note: str
    specialties: Optional[list[str]] = None  # Limit to specific specialties
    sources: Optional[list[str]] = None  # Limit to specific sources
    max_guidelines: int = 10  # Maximum guidelines to check
    include_all_matches: bool = False  # Include non-compliant only if False


class ComplianceCheckResponse(BaseModel):
    """Response from compliance check."""
    overall_score: float
    compliant_count: int
    gap_count: int
    warning_count: int
    not_applicable_count: int
    items: list[dict[str, Any]]  # Serialized ComplianceItem list
    guidelines_checked: int
    specialties_analyzed: list[str]
    processing_time_ms: float


# ============================================================================
# Settings model
# ============================================================================

class GuidelinesSettings(BaseModel):
    """Settings for clinical guidelines system configuration."""
    # Database settings
    guidelines_database_url: Optional[str] = None
    guidelines_pool_size: int = 8

    # Neo4j settings
    neo4j_uri: Optional[str] = None
    neo4j_user: Optional[str] = None
    neo4j_password: Optional[str] = None

    # Embedding settings (uses same embeddings as main RAG)
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Chunking settings (smaller chunks for guidelines)
    chunk_size_tokens: int = 500
    chunk_overlap_tokens: int = 100
    max_chunks_per_guideline: int = 500

    # Search settings
    default_top_k: int = 10
    default_similarity_threshold: float = 0.6
    hnsw_ef_search: int = 100

    # Compliance settings
    enable_auto_compliance_check: bool = True
    compliance_delay_ms: int = 300  # Delay after SOAP generation
    min_compliance_score_warning: float = 0.7  # Show warning below this score
