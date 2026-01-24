"""
Research Map API Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.session import get_db
from schemas import ResearchMapSnapshotResponse, ResearchMapGenerateRequest, ResearchMapPointResponse
from services.research_map_service import ResearchMapService
from api.routes.auth import get_current_user

router = APIRouter(prefix="/research-map", tags=["Research Map"])


@router.post("/generate", response_model=ResearchMapSnapshotResponse)
def generate_research_map(
    request: ResearchMapGenerateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Generate new 3D research map with UMAP + K-means"""
    service = ResearchMapService(db)

    try:
        snapshot = service.generate_map(
            n_neighbors=request.n_neighbors,
            min_dist=request.min_dist,
            n_clusters=request.n_clusters,
            metric=request.metric
        )

        # Build response with publication data
        points_data = []
        for point in snapshot.points:
            pub = point.publication
            points_data.append(ResearchMapPointResponse(
                id=point.id,
                publication_id=point.publication_id,
                x=point.x,
                y=point.y,
                z=point.z,
                cluster_id=point.cluster_id,
                cluster_label=point.cluster_label,
                title=pub.title or "Untitled",
                authors=pub.authors,
                year=pub.year,
                doi=pub.canonical_doi,
                summary=pub.summary
            ))

        return ResearchMapSnapshotResponse(
            id=snapshot.id,
            created_at=snapshot.created_at,
            parameters=snapshot.parameters,
            total_publications=snapshot.total_publications,
            points=points_data
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating map: {str(e)}")


@router.get("/latest", response_model=ResearchMapSnapshotResponse)
def get_latest_map(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get most recent research map"""
    service = ResearchMapService(db)
    snapshot = service.get_latest_snapshot()

    if not snapshot:
        raise HTTPException(status_code=404, detail="No research maps found. Generate one first.")

    points_data = []
    for point in snapshot.points:
        pub = point.publication
        points_data.append(ResearchMapPointResponse(
            id=point.id,
            publication_id=point.publication_id,
            x=point.x,
            y=point.y,
            z=point.z,
            cluster_id=point.cluster_id,
            cluster_label=point.cluster_label,
            title=pub.title or "Untitled",
            authors=pub.authors,
            year=pub.year,
            doi=pub.canonical_doi,
            summary=pub.summary
        ))

    return ResearchMapSnapshotResponse(
        id=snapshot.id,
        created_at=snapshot.created_at,
        parameters=snapshot.parameters,
        total_publications=snapshot.total_publications,
        points=points_data
    )


@router.get("/{snapshot_id}", response_model=ResearchMapSnapshotResponse)
def get_map_by_id(
    snapshot_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get specific research map by ID"""
    service = ResearchMapService(db)
    snapshot = service.get_snapshot_by_id(snapshot_id)

    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    points_data = []
    for point in snapshot.points:
        pub = point.publication
        points_data.append(ResearchMapPointResponse(
            id=point.id,
            publication_id=point.publication_id,
            x=point.x,
            y=point.y,
            z=point.z,
            cluster_id=point.cluster_id,
            cluster_label=point.cluster_label,
            title=pub.title or "Untitled",
            authors=pub.authors,
            year=pub.year,
            doi=pub.canonical_doi,
            summary=pub.summary
        ))

    return ResearchMapSnapshotResponse(
        id=snapshot.id,
        created_at=snapshot.created_at,
        parameters=snapshot.parameters,
        total_publications=snapshot.total_publications,
        points=points_data
    )
