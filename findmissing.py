import os
import re

def find_missing_numbers(folder_path, prefix_word):
    # Build regex dynamically based on user input, allowing optional space(s) after the word
    pattern = re.compile(r'^' + re.escape(prefix_word) + r'\s*(\d+)\.', re.IGNORECASE)

    numbers = []

    # Scan all files in the folder
    for filename in os.listdir(folder_path):
        match = pattern.match(filename)
        if match:
            numbers.append(int(match.group(1)))

    if not numbers:
        print("No matching files found.")
        return

    numbers.sort()
    # print(f"Found numbers: {numbers}")

    # Find missing numbers
    full_range = set(range(numbers[0], numbers[-1] + 1))
    missing = sorted(full_range - set(numbers))

    if missing:
        print(f"Missing numbers: {missing}")
    else:
        print("No numbers are missing.")

if __name__ == "__main__":
    folder = input("Masukkan path folder PDF: ").strip()
    prefix = input("Masukkan prefix kata (contoh: Bab, Chapter, Ch): ").strip()
    find_missing_numbers(folder, prefix)
