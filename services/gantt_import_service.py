"""
GanttImportService - Intelligent Excel Matrix to Gantt Parser
Converts CECAN's Excel matrix format (months as columns with 'x' markers)
into structured Gantt tasks with proper hierarchy and dates.
"""

import re
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy.orm import Session

from core.models import (
    GanttTask, GanttTaskStatus, GanttLink, GanttImportLog, WorkPackage
)

logger = logging.getLogger(__name__)


class TaskLevel(Enum):
    """Hierarchy levels for WBS structure."""
    WORK_PACKAGE = 0
    PROJECT = 1
    ACTIVITY = 2
    SUBTASK = 3
    SUB_SUBTASK = 4


@dataclass
class ParsedTask:
    """Intermediate representation of a parsed task."""
    text: str
    level: TaskLevel
    wbs_code: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    duration: int = 0
    progress: float = 0.0
    row_number: int = 0
    parent_index: Optional[int] = None
    children: List[int] = field(default_factory=list)


class GanttImportService:
    """
    Service for importing Excel Gantt matrices into the database.

    Handles:
    - Matrix-to-date conversion (finding first/last 'x' marks)
    - Hierarchy detection based on indentation and numbering
    - Progress extraction from "Achievement %" columns
    - WBS code generation
    """

    # Month name mappings (Spanish and English)
    MONTH_NAMES = {
        # English
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        # Spanish
        'ene': 1, 'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
        'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 'septiembre': 9,
        'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }

    # Patterns for hierarchy detection
    PATTERNS = {
        'wp': re.compile(r'^WP[-\s]?\d+', re.IGNORECASE),
        'project': re.compile(r'^Proyect[o]?\s*\d+', re.IGNORECASE),
        'activity': re.compile(r'^\((\d+)\)'),
        'subtask_numbered': re.compile(r'^(\d+\.)+\d+'),
        'subtask_indented': re.compile(r'^(\s{2,})'),
    }

    def __init__(self, db: Session, base_year: int = 2025):
        """
        Initialize the import service.

        Args:
            db: SQLAlchemy session
            base_year: Base year for date calculations (default 2025)
        """
        self.db = db
        self.base_year = base_year
        self.month_columns: Dict[int, Tuple[int, int]] = {}  # col_idx -> (month, year)
        self.progress_column: Optional[int] = None
        self.task_column: int = 2  # Usually column B
        self.header_row: int = 7   # Usually row 7

    def import_excel(
        self,
        file_path: str,
        wp_id: Optional[int] = None,
        user_id: Optional[int] = None,
        clear_existing: bool = False
    ) -> Dict[str, Any]:
        """
        Import an Excel file into the Gantt system.

        Args:
            file_path: Path to the Excel file
            wp_id: Optional Work Package ID to associate tasks with
            user_id: User performing the import
            clear_existing: If True, delete existing tasks for this WP first

        Returns:
            Dict with import statistics and any errors
        """
        result = {
            'success': False,
            'tasks_created': 0,
            'tasks_updated': 0,
            'errors': [],
            'warnings': []
        }

        try:
            # Calculate file hash for deduplication
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

            # Load workbook
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb.active

            # Detect structure
            self._detect_structure(ws)

            # Parse all tasks
            parsed_tasks = self._parse_worksheet(ws)

            if not parsed_tasks:
                result['errors'].append('No tasks found in the file')
                return result

            # Build hierarchy
            self._build_hierarchy(parsed_tasks)

            # Clear existing if requested
            if clear_existing and wp_id:
                deleted = self.db.query(GanttTask).filter(
                    GanttTask.wp_id == wp_id
                ).delete()
                logger.info(f"Deleted {deleted} existing tasks for WP {wp_id}")

            # Create database records
            db_tasks = self._create_db_tasks(parsed_tasks, wp_id, user_id)

            result['tasks_created'] = len(db_tasks)
            result['success'] = True

            # Log the import
            import_log = GanttImportLog(
                wp_id=wp_id,
                filename=file_path.split('/')[-1],
                file_hash=file_hash,
                tasks_created=len(db_tasks),
                imported_by=user_id
            )
            self.db.add(import_log)
            self.db.commit()

        except Exception as e:
            logger.error(f"Import error: {str(e)}", exc_info=True)
            result['errors'].append(str(e))
            self.db.rollback()

        return result

    def _detect_structure(self, ws: Worksheet) -> None:
        """
        Auto-detect the Excel structure:
        - Find header row with month names
        - Identify month columns and their years
        - Find progress/achievement column
        """
        # Scan first 15 rows for structure
        for row_idx in range(1, 16):
            year_context = self.base_year

            for col_idx in range(1, min(50, ws.max_column + 1)):
                cell_value = ws.cell(row=row_idx, column=col_idx).value

                if cell_value is None:
                    continue

                cell_str = str(cell_value).strip().lower()

                # Check for year context (e.g., "2024", "2025")
                if re.match(r'^\d{4}$', cell_str):
                    year_context = int(cell_str)
                    continue

                # Check for month names
                for month_name, month_num in self.MONTH_NAMES.items():
                    if cell_str.startswith(month_name):
                        self.month_columns[col_idx] = (month_num, year_context)
                        self.header_row = row_idx
                        break

                # Check for achievement/progress column
                if 'achievement' in cell_str or 'avance' in cell_str or '% year' in cell_str:
                    self.progress_column = col_idx

        logger.info(f"Detected {len(self.month_columns)} month columns, header row: {self.header_row}")
        logger.info(f"Progress column: {self.progress_column}")

    def _parse_worksheet(self, ws: Worksheet) -> List[ParsedTask]:
        """Parse all task rows from the worksheet."""
        tasks = []

        # Start from row after header
        for row_idx in range(self.header_row + 1, ws.max_row + 1):
            task_cell = ws.cell(row=row_idx, column=self.task_column).value

            if not task_cell or str(task_cell).strip() == '':
                continue

            task_text = str(task_cell).strip()

            # Detect hierarchy level
            level, wbs_code = self._detect_level(task_text, len(tasks))

            # Extract dates from matrix
            start_date, end_date = self._extract_dates_from_matrix(ws, row_idx)

            # Calculate duration
            duration = 0
            if start_date and end_date:
                duration = (end_date - start_date).days + 1

            # Extract progress
            progress = self._extract_progress(ws, row_idx)

            task = ParsedTask(
                text=self._clean_task_text(task_text),
                level=level,
                wbs_code=wbs_code,
                start_date=start_date,
                end_date=end_date,
                duration=max(duration, 1),
                progress=progress,
                row_number=row_idx
            )

            tasks.append(task)

        return tasks

    def _detect_level(self, text: str, current_index: int) -> Tuple[TaskLevel, str]:
        """
        Detect the hierarchy level based on text patterns.

        Returns:
            Tuple of (TaskLevel, WBS code string)
        """
        # Check for WP level
        if self.PATTERNS['wp'].match(text):
            return TaskLevel.WORK_PACKAGE, f"WP{current_index + 1}"

        # Check for Project level
        if self.PATTERNS['project'].match(text):
            match = re.search(r'\d+', text)
            num = match.group() if match else str(current_index + 1)
            return TaskLevel.PROJECT, f"P{num}"

        # Check for Activity level (e.g., "(1)", "(2)")
        activity_match = self.PATTERNS['activity'].match(text)
        if activity_match:
            return TaskLevel.ACTIVITY, f"A{activity_match.group(1)}"

        # Check for numbered subtask (e.g., "2.1", "2.1.1")
        subtask_match = self.PATTERNS['subtask_numbered'].match(text)
        if subtask_match:
            wbs = subtask_match.group().replace(' ', '')
            depth = wbs.count('.')
            if depth >= 2:
                return TaskLevel.SUB_SUBTASK, wbs
            return TaskLevel.SUBTASK, wbs

        # Check for indented subtask
        indent_match = self.PATTERNS['subtask_indented'].match(text)
        if indent_match:
            indent_len = len(indent_match.group(1))
            if indent_len >= 4:
                return TaskLevel.SUB_SUBTASK, f"ST{current_index + 1}"
            return TaskLevel.SUBTASK, f"ST{current_index + 1}"

        # Default to activity level
        return TaskLevel.ACTIVITY, f"T{current_index + 1}"

    def _extract_dates_from_matrix(
        self,
        ws: Worksheet,
        row_idx: int
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Extract start and end dates by finding first and last 'x' marks.

        Algorithm:
        - Scan month columns left to right
        - First 'x' found -> start_date (day 1 of that month)
        - Last 'x' found -> end_date (day 28 of that month)
        """
        first_x_col = None
        last_x_col = None

        for col_idx in sorted(self.month_columns.keys()):
            cell_value = ws.cell(row=row_idx, column=col_idx).value

            if cell_value and str(cell_value).strip().lower() == 'x':
                if first_x_col is None:
                    first_x_col = col_idx
                last_x_col = col_idx

        start_date = None
        end_date = None

        if first_x_col and first_x_col in self.month_columns:
            month, year = self.month_columns[first_x_col]
            start_date = datetime(year, month, 1)

        if last_x_col and last_x_col in self.month_columns:
            month, year = self.month_columns[last_x_col]
            # Use day 28 to avoid month-end issues
            end_date = datetime(year, month, 28)

        # If no dates found, try to inherit from context or use defaults
        if not start_date and not end_date:
            # Default to current year, January
            start_date = datetime(self.base_year, 1, 1)
            end_date = datetime(self.base_year, 12, 28)
        elif start_date and not end_date:
            end_date = start_date + timedelta(days=30)
        elif end_date and not start_date:
            start_date = end_date - timedelta(days=30)

        return start_date, end_date

    def _extract_progress(self, ws: Worksheet, row_idx: int) -> float:
        """Extract progress percentage from the achievement column."""
        if not self.progress_column:
            return 0.0

        cell_value = ws.cell(row=row_idx, column=self.progress_column).value

        if cell_value is None:
            return 0.0

        try:
            # Handle both "100" and "100%" formats
            value_str = str(cell_value).replace('%', '').strip()
            progress = float(value_str)

            # Normalize to 0-1 range
            if progress > 1:
                progress = progress / 100.0

            return min(max(progress, 0.0), 1.0)
        except (ValueError, TypeError):
            return 0.0

    def _clean_task_text(self, text: str) -> str:
        """Clean and normalize task text."""
        # Remove leading numbering but preserve the description
        text = re.sub(r'^\s*\(\d+\)\s*', '', text)
        text = re.sub(r'^\s*\d+\.\d+(\.\d+)*\s*', '', text)
        text = text.strip()

        # Capitalize first letter
        if text:
            text = text[0].upper() + text[1:]

        return text

    def _build_hierarchy(self, tasks: List[ParsedTask]) -> None:
        """
        Build parent-child relationships based on detected levels.

        Uses a stack-based approach to track current parent at each level.
        """
        # Stack: [wp_idx, project_idx, activity_idx, subtask_idx]
        parent_stack = [-1, -1, -1, -1, -1]

        for idx, task in enumerate(tasks):
            level_value = task.level.value

            # Find parent based on level
            if level_value > 0:
                # Look for nearest parent at a higher level
                for parent_level in range(level_value - 1, -1, -1):
                    if parent_stack[parent_level] >= 0:
                        task.parent_index = parent_stack[parent_level]
                        tasks[parent_stack[parent_level]].children.append(idx)
                        break

            # Update stack for this level
            parent_stack[level_value] = idx

            # Clear lower levels (they're no longer valid parents)
            for lower_level in range(level_value + 1, len(parent_stack)):
                parent_stack[lower_level] = -1

    def _create_db_tasks(
        self,
        parsed_tasks: List[ParsedTask],
        wp_id: Optional[int],
        user_id: Optional[int]
    ) -> List[GanttTask]:
        """Create database records from parsed tasks."""
        db_tasks = []
        id_mapping = {}  # parsed_index -> db_id

        # First pass: create all tasks without parent references
        for idx, parsed in enumerate(parsed_tasks):
            # Determine task type
            task_type = 'task'
            if parsed.level == TaskLevel.WORK_PACKAGE:
                task_type = 'project'
            elif parsed.level == TaskLevel.PROJECT:
                task_type = 'project'
            elif parsed.duration <= 1 and parsed.progress in [0.0, 1.0]:
                task_type = 'milestone'

            # Determine status
            status = GanttTaskStatus.PENDING
            if parsed.progress >= 1.0:
                status = GanttTaskStatus.COMPLETED
            elif parsed.progress > 0:
                status = GanttTaskStatus.IN_PROGRESS
                # Check if late
                if parsed.end_date and datetime.now() > parsed.end_date:
                    status = GanttTaskStatus.LATE

            db_task = GanttTask(
                wp_id=wp_id,
                text=parsed.text,
                wbs_code=parsed.wbs_code,
                start_date=parsed.start_date,
                end_date=parsed.end_date,
                duration=parsed.duration,
                progress=parsed.progress,
                status=status,
                task_type=task_type,
                sort_order=idx,
                created_by=user_id
            )

            self.db.add(db_task)
            self.db.flush()  # Get the ID

            db_tasks.append(db_task)
            id_mapping[idx] = db_task.id

        # Second pass: set parent references
        for idx, parsed in enumerate(parsed_tasks):
            if parsed.parent_index is not None and parsed.parent_index in id_mapping:
                db_tasks[idx].parent_id = id_mapping[parsed.parent_index]

        self.db.commit()
        return db_tasks

    def preview_import(self, file_path: str) -> Dict[str, Any]:
        """
        Preview what would be imported without actually saving.

        Returns:
            Dict with preview data including task tree and statistics
        """
        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            ws = wb.active

            self._detect_structure(ws)
            parsed_tasks = self._parse_worksheet(ws)
            self._build_hierarchy(parsed_tasks)

            # Convert to serializable format
            tasks_preview = []
            for idx, task in enumerate(parsed_tasks):
                tasks_preview.append({
                    'index': idx,
                    'text': task.text,
                    'level': task.level.name,
                    'wbs_code': task.wbs_code,
                    'start_date': task.start_date.isoformat() if task.start_date else None,
                    'end_date': task.end_date.isoformat() if task.end_date else None,
                    'duration': task.duration,
                    'progress': task.progress,
                    'parent_index': task.parent_index,
                    'children_count': len(task.children)
                })

            return {
                'success': True,
                'total_tasks': len(tasks_preview),
                'tasks': tasks_preview,
                'month_columns_detected': len(self.month_columns),
                'has_progress_column': self.progress_column is not None
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
