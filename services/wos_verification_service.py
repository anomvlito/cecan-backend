"""
WOS Verification Service

Handles all logic related to Web of Science journal verification,
including decile calculation, quartile matching, and verification output building.

Extracted from api/routes/publications.py to follow Single Responsibility Principle.
"""

from typing import Optional, Tuple
from sqlalchemy.orm import Session

from core.models import Publication, WosJournalMirror
from services.journal_service import JournalMatchingService
from schemas import WosVerificationOut


def calculate_decile(percent: float) -> int:
    """
    Calculate decile from ranking percentile.

    Decile 1 = Top 10% (percentile >= 90)
    Decile 10 = Bottom 10% (percentile < 10)

    Args:
        percent: Ranking percentile (0-100)

    Returns:
        Decile number (1-10)
    """
    if percent >= 90:
        return 1
    elif percent >= 80:
        return 2
    elif percent >= 70:
        return 3
    elif percent >= 60:
        return 4
    elif percent >= 50:
        return 5
    elif percent >= 40:
        return 6
    elif percent >= 30:
        return 7
    elif percent >= 20:
        return 8
    elif percent >= 10:
        return 9
    else:
        return 10


def parse_ranking_percent(ranking_percent_str: Optional[str]) -> Optional[float]:
    """
    Parse ranking percent string (e.g., "99.7%") to float.

    Args:
        ranking_percent_str: String like "99.7%" or "85.3%"

    Returns:
        Float value or None if parsing fails
    """
    if not ranking_percent_str:
        return None

    try:
        return float(ranking_percent_str.replace('%', '').strip())
    except (ValueError, AttributeError):
        return None


def build_wos_verification(
    match: WosJournalMirror,
    match_type: str
) -> WosVerificationOut:
    """
    Build WosVerificationOut schema from a WOS Mirror match.

    Args:
        match: WosJournalMirror ORM object
        match_type: String describing match type (e.g., "issn_exact", "name_fuzzy")

    Returns:
        WosVerificationOut Pydantic schema
    """
    decile = None
    is_top_10 = False

    percent = parse_ranking_percent(match.best_ranking_percent)
    if percent is not None:
        decile = calculate_decile(percent)
        is_top_10 = percent >= 90.0

    return WosVerificationOut(
        match_type=match_type,
        quartile=match.best_quartile,
        decile=decile,
        is_top_10=is_top_10,
        source_url=match.source_url,
        categories=match.categories if match.categories else [],
        journal_name=match.journal_name
    )


def get_wos_verification_for_publication(
    pub: Publication,
    db: Session
) -> Optional[WosVerificationOut]:
    """
    Get WOS verification data for a publication.

    This is the main entry point for WOS verification. It:
    1. Extracts journal info from publication
    2. Searches WOS Mirror for matching journal
    3. Builds and returns verification data

    Args:
        pub: Publication ORM object
        db: Database session

    Returns:
        WosVerificationOut if match found, None otherwise
    """
    try:
        # Initialize matcher
        matcher = JournalMatchingService(db)

        # Extract journal identification info
        journal_name = pub.journal.name if pub.journal else pub.journal_name_temp
        issn = pub.journal.issn if pub.journal else None
        publisher = pub.publisher_temp

        # Find best match in WOS Mirror
        match, match_type = matcher.find_best_match(
            journal_name=journal_name,
            issn=issn,
            publisher=publisher
        )

        if match:
            return build_wos_verification(match, match_type)

        return None

    except Exception as e:
        # Log but don't raise - verification is non-critical
        print(f"Error in WOS verification for pub {pub.id}: {e}")
        return None


def enrich_publication_with_wos_verification(
    pub_out,  # PublicationOut or PublicationDetailOut
    pub: Publication,
    db: Session
) -> None:
    """
    Enrich a publication output schema with WOS verification data.
    Modifies pub_out in place.

    Args:
        pub_out: Pydantic output schema (PublicationOut or PublicationDetailOut)
        pub: Publication ORM object
        db: Database session
    """
    verification = get_wos_verification_for_publication(pub, db)
    if verification:
        pub_out.wos_verification = verification
