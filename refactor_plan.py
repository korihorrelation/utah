import re

with open('website/scripts/pipeline/promoters.py', 'r', encoding='utf-8') as f:
    code = f.read()

# I will use multi_replace_file_content to do it safely.
