#!/usr/bin/env python3
"""
Normalize JSONL files to ensure one JSON object per line.
Reads from stdin or file, outputs properly formatted JSONL.
"""

import sys
import json
from json import JSONDecoder


def normalize_jsonl(input_text):
    """
    Parse potentially malformed JSONL and emit one object per line.
    
    Handles:
    - Multiple JSON objects on a single line
    - Missing newlines between objects
    - Trailing/leading whitespace
    """
    decoder = JSONDecoder()
    output_lines = []
    
    # Strip and clean input
    text = input_text.strip()
    if not text:
        return ""
    
    index = 0
    length = len(text)
    
    while index < length:
        # Skip whitespace
        while index < length and text[index].isspace():
            index += 1
        
        if index >= length:
            break
        
        try:
            # Decode one JSON object
            obj, end_index = decoder.raw_decode(text, index)
            # Emit as compact JSON on its own line
            output_lines.append(json.dumps(obj, separators=(',', ':')))
            index = end_index
        except json.JSONDecodeError as e:
            print(f"Error at position {index}: {e}", file=sys.stderr)
            # Try to skip to next potential object
            next_brace = text.find('{', index + 1)
            if next_brace == -1:
                break
            index = next_brace
    
    return '\n'.join(output_lines) + '\n' if output_lines else ''


def main():
    if len(sys.argv) > 1:
        # Read from file
        with open(sys.argv[1], 'r') as f:
            content = f.read()
    else:
        # Read from stdin
        content = sys.stdin.read()
    
    normalized = normalize_jsonl(content)
    sys.stdout.write(normalized)


if __name__ == '__main__':
    main()