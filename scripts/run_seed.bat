@echo off
chcp 65001 >nul
"C:\Users\Y-Y-H\AppData\Local\Programs\Python\Python312\python.exe" "G:\2027\accounting_system\run_seed.py" > "G:\2027\accounting_system\seed_output.txt" 2>&1
echo DONE > "G:\2027\accounting_system\seed_done.txt"
