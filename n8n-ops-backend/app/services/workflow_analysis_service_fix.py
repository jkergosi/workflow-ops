# Temporary file to check the exact characters
with open('workflow_analysis_service.py', 'rb') as f:
    lines = f.readlines()
    print(f"Line 351 (bytes): {lines[350]}")
    print(f"Line 392 (bytes): {lines[391]}")

