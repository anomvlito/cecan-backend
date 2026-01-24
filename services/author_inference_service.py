"""
Author Inference Service

Automatically infers and connects authors to publications by:
1. Fetching author lists from external APIs (OpenAlex, Semantic Scholar)
2. Using fuzzy matching to find CECAN members
3. Creating researcher_publication links with confidence scores

Used in two modes:
- Single: Auto-link authors when uploading new PDFs
- Batch: Audit existing publications without authors
"""

import logging
import requests
import unicodedata
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from thefuzz import fuzz

from core.models import Publication, AcademicMember, ResearcherPublication, ResearcherDetails

logger = logging.getLogger(__name__)


class AuthorInferenceService:
    """Service for inferring publication authors via external APIs and fuzzy matching."""

    def __init__(self, db: Session):
        self.db = db
        # Cache eligible members to avoid repeated DB queries
        self._eligible_members_cache = None

    def infer_authors_for_publication(
        self,
        publication_id: int,
        auto_link: bool = True,
        threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Infer authors for a single publication.

        Args:
            publication_id: ID of the publication
            auto_link: If True, automatically create researcher_publication links
            threshold: Minimum fuzzy match score (0.0-1.0) to consider a match

        Returns:
            Dictionary with inference results including candidates and stats
        """
        # Get publication
        pub = self.db.query(Publication).filter(Publication.id == publication_id).first()
        if not pub:
            raise ValueError(f"Publication {publication_id} not found")

        if not pub.canonical_doi:
            return {
                "publication_id": publication_id,
                "doi": None,
                "sources_consulted": [],
                "external_authors": [],
                "candidates": [],
                "stats": {
                    "total_external_authors": 0,
                    "total_matches_found": 0,
                    "auto_linked": 0,
                    "skipped": 0
                }
            }

        # Fetch authors from external APIs
        external_authors = self._fetch_authors_from_apis(pub.canonical_doi)

        sources_consulted = list(set([a["source"] for a in external_authors]))

        # Fuzzy match against CECAN members
        candidates = self._fuzzy_match_members(external_authors, threshold)

        # Stats
        stats = {
            "total_external_authors": len(external_authors),
            "total_matches_found": len(candidates),
            "auto_linked": 0,
            "skipped": 0
        }

        # Auto-link if requested
        for candidate in candidates:
            if not candidate.get("matched_member"):
                continue

            # Check for existing link
            existing_link = self.db.query(ResearcherPublication).filter(
                ResearcherPublication.publication_id == publication_id,
                ResearcherPublication.member_id == candidate["matched_member"]["id"]
            ).first()

            if existing_link:
                candidate["auto_linked"] = False
                candidate["skipped_reason"] = "existing_link"
                stats["skipped"] += 1
                continue

            if auto_link:
                # Create link
                link = self._create_researcher_publication_link(
                    publication_id=publication_id,
                    member_id=candidate["matched_member"]["id"],
                    score=candidate["score"],
                    method=f"fuzzy_doi_{candidate['source']}",
                    position=candidate.get("position", 0)
                )
                if link:
                    candidate["auto_linked"] = True
                    stats["auto_linked"] += 1
                else:
                    candidate["auto_linked"] = False
                    candidate["skipped_reason"] = "db_error"
                    stats["skipped"] += 1
            else:
                candidate["auto_linked"] = False

        return {
            "publication_id": publication_id,
            "doi": pub.canonical_doi,
            "sources_consulted": sources_consulted,
            "external_authors": [a["name"] for a in external_authors],
            "candidates": candidates,
            "stats": stats
        }

    def infer_authors_batch(
        self,
        publication_ids: List[int],
        auto_link: bool = False,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Infer authors for multiple publications (batch mode).

        Args:
            publication_ids: List of publication IDs
            auto_link: If True, automatically create links (default False for batch)
            threshold: Minimum fuzzy match score

        Returns:
            List of inference results (same format as single mode)
        """
        results = []

        for pub_id in publication_ids:
            try:
                result = self.infer_authors_for_publication(
                    publication_id=pub_id,
                    auto_link=auto_link,
                    threshold=threshold
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to infer authors for publication {pub_id}: {e}")
                # Continue with next publication
                results.append({
                    "publication_id": pub_id,
                    "doi": None,
                    "sources_consulted": [],
                    "external_authors": [],
                    "candidates": [],
                    "stats": {
                        "total_external_authors": 0,
                        "total_matches_found": 0,
                        "auto_linked": 0,
                        "skipped": 1
                    },
                    "error": str(e)
                })

        return results

    def _fetch_authors_from_apis(self, doi: str) -> List[Dict[str, Any]]:
        """
        Fetch author list from OpenAlex and Semantic Scholar.

        Returns:
            List of author dictionaries with name, source, position, and optional ORCID
        """
        authors = []

        # 1. Try OpenAlex first (primary source)
        try:
            openalex_authors = self._fetch_authors_from_openalex(doi)
            authors.extend(openalex_authors)
            logger.info(f"Found {len(openalex_authors)} authors from OpenAlex for DOI {doi}")
        except Exception as e:
            logger.warning(f"OpenAlex API failed for DOI {doi}: {e}")

        # 2. Try Semantic Scholar (complementary source)
        try:
            s2_authors = self._fetch_authors_from_s2(doi)
            # Only add S2 authors if we didn't get any from OpenAlex
            if not authors:
                authors.extend(s2_authors)
                logger.info(f"Found {len(s2_authors)} authors from Semantic Scholar for DOI {doi}")
        except Exception as e:
            logger.warning(f"Semantic Scholar API failed for DOI {doi}: {e}")

        return authors

    def _fetch_authors_from_openalex(self, doi: str) -> List[Dict[str, Any]]:
        """Fetch authors from OpenAlex API."""
        url = f"https://api.openalex.org/works/doi:{doi}"
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            return []

        data = response.json()
        authors = []

        for idx, authorship in enumerate(data.get("authorships", []), start=1):
            author_info = authorship.get("author", {})
            name = author_info.get("display_name")
            if not name:
                continue

            orcid_url = author_info.get("orcid")
            orcid = orcid_url.split("/")[-1] if orcid_url else None

            authors.append({
                "name": name,
                "orcid": orcid,
                "position": idx,
                "source": "openalex"
            })

        return authors

    def _fetch_authors_from_s2(self, doi: str) -> List[Dict[str, Any]]:
        """Fetch authors from Semantic Scholar API."""
        url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
        params = {"fields": "authors,title,year"}

        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            return []

        data = response.json()
        authors = []

        for idx, author in enumerate(data.get("authors", []), start=1):
            name = author.get("name")
            if not name:
                continue

            authors.append({
                "name": name,
                "position": idx,
                "source": "semanticscholar"
            })

        return authors

    def _fuzzy_match_members(
        self,
        external_authors: List[Dict[str, Any]],
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Fuzzy match external authors against CECAN members.

        Args:
            external_authors: List of author dicts from APIs
            threshold: Minimum score to consider a match

        Returns:
            List of candidate matches with scores
        """
        members = self._get_eligible_members()
        candidates = []

        for ext_author in external_authors:
            best_match = None
            best_score = 0.0

            ext_norm = self._normalize_name(ext_author["name"])

            for member in members:
                # Try matching against full_name
                mem_norm = self._normalize_name(member.full_name)
                score = fuzz.token_sort_ratio(ext_norm, mem_norm) / 100.0

                # If member has researcher_details, also try first_name + last_name
                if hasattr(member, 'researcher_details') and member.researcher_details:
                    rd = member.researcher_details
                    if rd.first_name and rd.last_name:
                        alt_name = f"{rd.first_name} {rd.last_name}"
                        alt_norm = self._normalize_name(alt_name)
                        alt_score = fuzz.token_sort_ratio(ext_norm, alt_norm) / 100.0
                        score = max(score, alt_score)

                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = member

            if best_match:
                # Get category from researcher_details if available
                category = "Unknown"
                if hasattr(best_match, 'researcher_details') and best_match.researcher_details:
                    category = best_match.researcher_details.category or "Researcher"
                elif best_match.member_type == "student":
                    category = "Student"

                candidates.append({
                    "external_author": ext_author["name"],
                    "matched_member": {
                        "id": best_match.id,
                        "name": best_match.full_name,
                        "category": category
                    },
                    "score": best_score,
                    "source": ext_author["source"],
                    "position": ext_author.get("position", 0),
                    "auto_linked": False,
                    "skipped_reason": None
                })

        return candidates

    def _normalize_name(self, name: str) -> str:
        """
        Normalize name for fuzzy matching.

        Removes:
        - Accents (á → a, ñ → n)
        - Dots (J. Smith → J Smith)
        - Extra whitespace

        Converts to lowercase.
        """
        if not name:
            return ""

        name = name.lower()

        # Remove accents
        name = ''.join(
            c for c in unicodedata.normalize('NFD', name)
            if unicodedata.category(c) != 'Mn'
        )

        # Remove dots
        name = name.replace('.', ' ')

        # Normalize whitespace
        return ' '.join(name.split())

    def _get_eligible_members(self) -> List[AcademicMember]:
        """
        Get CECAN members eligible for author matching.

        Includes:
        - Researchers with category (Titular, Asociado, Adscrito, Colaborador)
        - Students (active or not)

        Results are cached to avoid repeated DB queries.
        """
        if self._eligible_members_cache is None:
            # Get researchers with researcher_details
            researchers = self.db.query(AcademicMember).join(
                ResearcherDetails,
                AcademicMember.id == ResearcherDetails.member_id
            ).filter(
                ResearcherDetails.category.in_([
                    'Titular', 'Asociado', 'Adscrito', 'Colaborador', 'Principal'
                ])
            ).all()

            # Get students
            students = self.db.query(AcademicMember).filter(
                AcademicMember.member_type == 'student'
            ).all()

            self._eligible_members_cache = researchers + students

            logger.info(f"Cached {len(self._eligible_members_cache)} eligible members for matching")

        return self._eligible_members_cache

    def _create_researcher_publication_link(
        self,
        publication_id: int,
        member_id: int,
        score: float,
        method: str,
        position: int = 0
    ) -> Optional[ResearcherPublication]:
        """
        Create researcher_publication link.

        Args:
            publication_id: Publication ID
            member_id: Academic member ID
            score: Match confidence score (0.0-1.0)
            method: Match method string (e.g., "fuzzy_doi_openalex")
            position: Author position in the list

        Returns:
            Created ResearcherPublication object, or None if failed
        """
        try:
            # Convert score from 0.0-1.0 to 0-100 integer (DB column is Integer)
            score_int = int(score * 100)

            link = ResearcherPublication(
                publication_id=publication_id,
                member_id=member_id,
                match_score=score_int,
                match_method=method
            )

            self.db.add(link)
            self.db.commit()
            self.db.refresh(link)

            logger.info(f"Created link: Publication {publication_id} <-> Member {member_id} (score: {score_int}, method: {method})")

            return link

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create link: {e}")
            return None
