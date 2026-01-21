
import os
import ast
import sys

def check_syntax(directory):
    print(f"Checking syntax in {directory}...")
    issues_found = False
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        source = f.read()
                    ast.parse(source, filename=full_path)
                except SyntaxError as e:
                    print(f"[ERROR] Syntax Error in {full_path}:")
                    print(f"   Line {e.lineno}: {e.msg}")
                    print(f"   {e.text.strip() if e.text else ''}")
                    issues_found = True
                except Exception as e:
                    print(f"⚠️ Could not parse {full_path}: {e}")

    if not issues_found:
        print(f"[OK] No syntax errors found in {directory}")

if __name__ == "__main__":
    check_syntax("agents")
    check_syntax("backend/agents")
    check_syntax("backend/supervisor")
