import re

# Test the lab suffix stripping regex
token = 'ME3010L'
pattern = r'^([A-Z]{2,4}\d{3,4})[A-Z]$'
result = re.sub(pattern, r'\1', token)
match = re.match(r'^([A-Z]{2,4}\d{3,4})[A-Z]$', token)

print(f'Input: {token}')
print(f'Output: {result}')
print(f'Match: {match}')
if match:
    print(f'Group 1: {match.group(1)}')

# Also test with other cases
test_cases = ['ME3010L', 'ME3011L', 'CS3010L', 'CS3010', 'ME3010', 'OE3E33', 'CS5031']
for tc in test_cases:
    result = re.sub(pattern, r'\1', tc)
    match = re.match(pattern, tc)
    print(f'{tc} -> {result} (matched: {bool(match)})')