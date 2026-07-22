# View functions parsing script
import re

print("Parsing reports/views.py to find all view functions...")
with open('D:\accounting_system\reports\views.py', encoding='utf-8') as f:
    lines = f.readlines()

view_functions = []
internal_functions = []

for line in lines:
    line = line.strip()
    if line.startswith('def '):
        func_name = line.split('def ')[1].split('(')[0]

        # Check if it takes 'request' as parameter (user-facing view)
        if '(request)' in line:
            if func_name.startswith('_'):
                internal_functions.append(func_name)
            else:
                view_functions.append(func_name)

print("\n=== View Functions (User-facing) ===")
for view in view_functions:
    print(f"  def {view}(request)")

print("\n=== Internal/Helper Functions ===")
for internal in internal_functions:
    print(f"  def {internal}()")

print(f"\nTotal: {len(view_functions)} view functions + {len(internal_functions)} internal functions")

print(f"\n=== Analysis: Need to test {len(view_functions)} views ===")
for view in view_functions:
    print(f"  - {view}")
