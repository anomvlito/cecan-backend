import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.scripts.excel_to_gantt_parser import ExcelGanttParser

excel_path = r"2025_Cronograma Proy Desigualdades_ WP#1 CECAN_20032025 editado.xlsx"

if not os.path.exists(excel_path):
    print(f"ERROR: File not found: {excel_path}")
    sys.exit(1)

parser = ExcelGanttParser(excel_path)
tasks = parser.parse()

print(f"[OK] Total tasks extracted: {len(tasks)}")
print(f"[OK] First task: {tasks[0]['name']}")
print(f"[OK] Last task: {tasks[-1]['name']}")
print(f"\nTasks with dependencies: {sum(1 for t in tasks if t['dependencies'])}")
print(f"Tasks without dependencies: {sum(1 for t in tasks if not t['dependencies'])}")

# Verify all tasks have required fields
required_fields = ['id', 'name', 'start', 'end', 'dependencies', 'custom_class']
for i, task in enumerate(tasks):
    for field in required_fields:
        if field not in task:
            print(f"ERROR: Task {i} missing field '{field}'")
            sys.exit(1)

print(f"\n[OK] All {len(tasks)} tasks have required fields")
print("\n*** PARSER VALIDATION SUCCESSFUL ***")
