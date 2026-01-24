"""
Research Map Service - UMAP + K-means clustering for 3D visualization
"""
import numpy as np
from sklearn.cluster import KMeans
from umap import UMAP
from sqlalchemy.orm import Session
from typing import List, Dict
import google.generativeai as genai
import os

from core.models import Publication, ResearchMapSnapshot, ResearchMapPoint
from services.rag_service import get_semantic_engine


class ResearchMapService:
    def __init__(self, db: Session):
        self.db = db
        self.rag_engine = get_semantic_engine()
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model = genai.GenerativeModel("gemini-2.0-flash-exp")

    def generate_map(
        self,
        n_neighbors: int = 15,
        min_dist: float = 0.1,
        n_clusters: int = 5,
        metric: str = "cosine"
    ) -> ResearchMapSnapshot:
        """Generate new 3D research map with clustering using Scholar embeddings"""

        # 1. Get all ScholarPaperData with embeddings
        from core.models import ScholarPaperData, ScholarEnrichmentStatus
        
        scholar_entries = self.db.query(ScholarPaperData).filter(
            ScholarPaperData.embedding_vector.isnot(None),
            ScholarPaperData.publication_id.isnot(None) # Ensure linked to publication
        ).all()

        if len(scholar_entries) < 5:
             # Fallback to loose check or error
             raise ValueError(f"Need at least 10 publications with valid Scholar embeddings for visualization. Found {len(scholar_entries)}.")

        # 2. Extract embeddings and IDs
        embeddings = []
        pub_ids = []
        
        for entry in scholar_entries:
            if entry.embedding_vector:
                embeddings.append(entry.embedding_vector)
                pub_ids.append(entry.publication_id)

        if not embeddings:
             raise ValueError("No embeddings found in ScholarPaperData.")
             
        embeddings = np.array(embeddings)
        print(f"Generated map using {len(embeddings)} embeddings from Semantic Scholar.")

        # 3. UMAP dimensionality reduction to 3D
        reducer = UMAP(
            n_components=3,
            n_neighbors=min(n_neighbors, len(embeddings) - 1),
            min_dist=min_dist,
            metric=metric,
            random_state=42
        )
        coords_3d = reducer.fit_transform(embeddings)

        # 4. K-means clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_ids = kmeans.fit_predict(coords_3d)

        # 5. Generate cluster labels with AI
        cluster_labels = self._generate_cluster_labels(pub_ids, cluster_ids, n_clusters)

        # 6. Save snapshot
        snapshot = ResearchMapSnapshot(
            parameters={
                "n_neighbors": n_neighbors,
                "min_dist": min_dist,
                "n_clusters": n_clusters,
                "metric": metric,
                "source": "scholar_specter_v1"
            },
            total_publications=len(pub_ids)
        )
        self.db.add(snapshot)
        self.db.flush()

        # 7. Save points
        for i, pub_id in enumerate(pub_ids):
            point = ResearchMapPoint(
                snapshot_id=snapshot.id,
                publication_id=pub_id,
                x=float(coords_3d[i][0]),
                y=float(coords_3d[i][1]),
                z=float(coords_3d[i][2]),
                cluster_id=int(cluster_ids[i]),
                cluster_label=cluster_labels[cluster_ids[i]]
            )
            self.db.add(point)

        self.db.commit()
        self.db.refresh(snapshot)

        return snapshot

    def _generate_cluster_labels(
        self,
        pub_ids: List[int],
        cluster_ids: np.ndarray,
        n_clusters: int
    ) -> Dict[int, str]:
        """Generate semantic labels for clusters using AI"""

        labels = {}

        for cluster_id in range(n_clusters):
            # Get publications in this cluster
            mask = cluster_ids == cluster_id
            cluster_pub_ids = [pub_ids[i] for i, is_in_cluster in enumerate(mask) if is_in_cluster]

            # Get titles and summaries
            pubs = self.db.query(Publication).filter(
                Publication.id.in_(cluster_pub_ids[:10])  # Sample max 10
            ).all()

            titles = [p.title for p in pubs if p.title]
            summaries = [p.summary for p in pubs if p.summary]

            # Generate label with AI
            prompt = f"""Analyze these research paper titles and summaries from a cluster.
Generate a SHORT label (2-4 words max) that captures the main research theme.

Titles:
{chr(10).join(f"- {t}" for t in titles[:5])}

Summaries:
{chr(10).join(f"- {s[:200]}..." for s in summaries[:3])}

Return ONLY the label, nothing else. Examples: "Cancer Immunotherapy", "AI in Healthcare", "Climate Modeling"
"""

            try:
                response = self.model.generate_content(prompt)
                label = response.text.strip().strip('"').strip("'")
                labels[cluster_id] = label[:50]  # Max 50 chars
            except Exception as e:
                print(f"Error generating label for cluster {cluster_id}: {e}")
                labels[cluster_id] = f"Cluster {cluster_id + 1}"

        return labels

    def get_latest_snapshot(self) -> ResearchMapSnapshot:
        """Get most recent snapshot"""
        return self.db.query(ResearchMapSnapshot)\
            .order_by(ResearchMapSnapshot.created_at.desc())\
            .first()

    def get_snapshot_by_id(self, snapshot_id: int) -> ResearchMapSnapshot:
        """Get specific snapshot"""
        return self.db.query(ResearchMapSnapshot)\
            .filter(ResearchMapSnapshot.id == snapshot_id)\
            .first()
