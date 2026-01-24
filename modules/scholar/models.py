from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class CitationIntent(BaseModel):
    paper_id: str
    title: Optional[str] = None
    intent_type: List[str]
    is_influential: bool

class SmartPaperResponse(BaseModel):
    """
    Standardized response format for paper intelligence data.
    """
    paperId: str
    doi: Optional[str] = None
    title: str
    year: Optional[int] = None
    authors: List[Dict[str, Any]] = []
    
    # Intelligence Fields
    tldr: Optional[str] = None
    embedding_sample: List[float] = [] # First 5 dimensions of the vector
    intent_breakdown: Dict[str, int] = {} # Summary of citation intents (e.g., {"methodology": 5})
    smart_citations: List[CitationIntent] = [] # Detailed list of citations with context

class AuthorResponse(BaseModel):
    authorId: str
    name: str
    paperCount: int = 0
    citationCount: int = 0
    hIndex: int = 0
    papers: List[Dict[str, Any]] = []

class SearchResponse(BaseModel):
    total: int = 0
    offset: int = 0
    data: List[Dict[str, Any]] = []

class AutocompleteMatch(BaseModel):
    id: str
    title: str
    type: str # 'paper' or 'author'
    year: Optional[int] = None
    authors: List[Dict[str, Any]] = []

class AutocompleteResponse(BaseModel):
    matches: List[AutocompleteMatch]
