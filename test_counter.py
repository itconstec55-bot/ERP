#!/usr/bin/env python3
import os
import re

filepath = 'D:\\accounting_system\\reports\\tests.py'
if os.path.exists(filepath):
    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    # Split into lines
    lines = content.split('\n')

    # Count test functions
    test_functions = []
    category_counts = {}

    current_class = ''
    for i, line in enumerate(lines):
        line = line.strip()

        # Detect class definitions
        if line.startswith('class '):
            match = re.match(r'class (\w+):', line)
            if match:
                current_class = match.group(1)

        # Detect test methods
        if line.startswith('def test_'):
            match = re.match(r'def test_(\w+)\(', line)
            if match:
                test_name = match.group(1)
                function_name = f"{current_class} : {test_name}"
                test_functions.append(function_name)

                # Group by category
                if current_class not in category_counts:
                    category_counts[current_class] = []
                category_counts[current_class].append(test_name)

    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total test functions: {len(test_functions)}")
    print()

    # Count by category
    print("=" * 60)
    print("TESTS BY CLASS")
    print("=" * 60)
    sorted_categories = sorted(category_counts.items(), key=lambda x: x[0])
    for class_name, tests in sorted_categories:
        print(f"{class_name} : ({len(tests)} tests)")

    print()

    # Detailed listing
    print("=" * 60)
    print("CATALOGUE OF TEST CLASSES")
    print("=" * 60)
    for class_name, tests in sorted_categories:
        print(f"\n{class_name} :")
        sorted_tests = sorted(tests)
        for test in sorted_tests:
            print(f"  • {test}")

    print()
    print("=" * 60)
    print("COMPLETED!")
    print("=" * 60)
