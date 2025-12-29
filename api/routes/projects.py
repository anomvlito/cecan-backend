
from fastapi import APIRouter, HTTPException
import os
import sys
from pathlib import Path

# Ensure backend directory is in sys.path to allow imports if needed
# (FastAPI usually handles this if run from root/backend)

from scripts.excel_to_gantt_parser import ExcelGanttParser
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Hardcode path for now, or move to config
# Assuming execution from backend/ or root
# We need to robustly find the excel file
EXCEL_FILENAME = "2025_Cronograma Proy Desigualdades_ WP#1 CECAN_20032025 editado.xlsx"

def get_excel_path():
    """
    Locates the Excel file by searching in prioritized paths:
    1. Current working directory
    2. data/ folder in current directory
    3. Project root (dynamically resolved)
    4. Hardcoded absolute path (fallback)
    """
    filename = EXCEL_FILENAME
    cwd = Path(os.getcwd())
    
    # Calculate dynamic project root: backend/api/routes/projects.py -> ... -> cecan-agent
    # __file__ is inside routes, so .parent is routes, .parent.parent is api, ...
    current_file = Path(__file__).resolve()
    # parents[0] = routes, parents[1] = api, parents[2] = backend, parents[3] = cecan-agent
    project_root = current_file.parents[3]
    
    possible_paths = [
        cwd / filename,
        cwd / "data" / filename,
        project_root / filename,
         # Fallback absolute path requested by user
        Path(r"d:\0 one drive fgortega microsoft\OneDrive - Universidad Católica de Chile\0 antigravity\cecan-agent") / filename
    ]
    
    for p in possible_paths:
        if p.exists():
            logger.info(f"Excel file found at: {p}")
            return str(p)
            
    logger.error(f"Excel file not found. Searched in: {[str(p) for p in possible_paths]}")
    return None

@router.get("/projects/wp1/gantt")
async def get_wp1_gantt_data():
    """
    Returns the parsed Gantt data for WP1 from the Excel file.
    """
    try:
        # Import here to avoid startup errors if the script has issues
        from scripts.excel_to_gantt_parser import ExcelGanttParser
        
        file_path = get_excel_path()
        if not file_path:
            raise HTTPException(status_code=404, detail="Cronograma Excel file not found")
        
        parser = ExcelGanttParser(file_path)
        tasks = parser.parse()
        return tasks
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate Gantt data: {str(e)}")
        # If it's an ImportError, it might be due to missing dependencies or path issues
        if isinstance(e, ImportError):
             raise HTTPException(status_code=500, detail=f"Configuration Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing Gantt data: {str(e)}")
