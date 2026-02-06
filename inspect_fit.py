"""FIT file diagnostic tool - inspects FIT file structure."""
import struct
import sys
from pathlib import Path


def parse_fit_header(data: bytes):
    """Parse FIT file header."""
    if len(data) < 14:
        return None
    
    header_size = data[0]
    protocol_version = data[1]
    profile_version = struct.unpack('<H', data[2:4])[0]
    data_size = struct.unpack('<I', data[4:8])[0]
    data_type = data[8:12].decode('ascii', errors='ignore')
    
    return {
        'header_size': header_size,
        'protocol_version': protocol_version,
        'profile_version': profile_version,
        'data_size': data_size,
        'data_type': data_type,
    }


def parse_messages(data: bytes, offset: int):
    """Parse FIT messages and count them by type."""
    messages = {}
    definitions = {}
    pos = offset
    
    while pos < len(data) - 2:  # Leave room for CRC
        if pos >= len(data):
            break
            
        header = data[pos]
        pos += 1
        
        # Check if it's a definition message
        if header & 0x40:
            local_num = header & 0x0F
            pos += 1  # reserved
            pos += 1  # architecture
            
            if pos + 2 > len(data):
                break
                
            global_num = struct.unpack('<H', data[pos:pos+2])[0]
            pos += 2
            
            num_fields = data[pos]
            pos += 1
            
            field_defs = []
            for _ in range(num_fields):
                if pos + 3 > len(data):
                    break
                field_num = data[pos]
                field_size = data[pos+1]
                field_type = data[pos+2]
                field_defs.append((field_num, field_size, field_type))
                pos += 3
            
            definitions[local_num] = {
                'global_num': global_num,
                'fields': field_defs,
                'data_size': sum(f[1] for f in field_defs)
            }
            
            # Count definition
            if global_num not in messages:
                messages[global_num] = {'definitions': 0, 'data': 0}
            messages[global_num]['definitions'] += 1
            
        else:
            # Data message
            local_num = header & 0x0F
            
            if local_num in definitions:
                defn = definitions[local_num]
                global_num = defn['global_num']
                data_size = defn['data_size']
                
                # Count data message
                if global_num not in messages:
                    messages[global_num] = {'definitions': 0, 'data': 0}
                messages[global_num]['data'] += 1
                
                pos += data_size
            else:
                # Unknown local message, try to skip
                break
    
    return messages


MESSAGE_NAMES = {
    0: 'file_id',
    12: 'sport',
    18: 'session',
    19: 'lap',
    20: 'record',
    21: 'event',
    23: 'device_info',
    26: 'workout',
    27: 'workout_step',
    34: 'activity',
    49: 'file_creator',
    225: 'set',
    264: 'exercise_title',
    312: 'split',
    313: 'split_summary',
}


def inspect_fit(filepath: Path):
    """Inspect FIT file and print structure."""
    with open(filepath, 'rb') as f:
        data = f.read()
    
    print(f"📊 Inspecting: {filepath.name}")
    print(f"   File size: {len(data)} bytes\n")
    
    # Parse header
    header = parse_fit_header(data)
    if not header:
        print("❌ Invalid FIT header")
        return
    
    print("📋 Header:")
    for key, val in header.items():
        print(f"   {key}: {val}")
    
    # Parse messages
    messages = parse_messages(data, header['header_size'])
    
    print(f"\n📨 Messages (by type):")
    print(f"   {'Type':<6} {'Name':<20} {'Definitions':<12} {'Data Messages':<15}")
    print(f"   {'-'*6} {'-'*20} {'-'*12} {'-'*15}")
    
    for msg_num in sorted(messages.keys()):
        name = MESSAGE_NAMES.get(msg_num, f'unknown_{msg_num}')
        defn_count = messages[msg_num]['definitions']
        data_count = messages[msg_num]['data']
        print(f"   {msg_num:<6} {name:<20} {defn_count:<12} {data_count:<15}")
    
    # Check for issues
    print(f"\n🔍 Validation:")
    
    issues = []
    
    # Check for multiple definitions of same type (except variable-length ones)
    variable_length_ok = {264, 26, 12, 27}  # exercise_title, workout, sport, workout_step
    for msg_num, counts in messages.items():
        if msg_num not in variable_length_ok and counts['definitions'] > 1:
            name = MESSAGE_NAMES.get(msg_num, f'unknown_{msg_num}')
            issues.append(f"   ⚠️  Message {msg_num} ({name}): {counts['definitions']} definitions (expected 1)")
    
    # Check for rest sets (type 225)
    if 225 in messages:
        set_defs = messages[225]['definitions']
        if set_defs != 2:
            issues.append(f"   ⚠️  Set messages: {set_defs} definitions (expected 2: active + rest)")
    
    # Check for required messages
    required = [0, 18, 21, 34]  # file_id, session, event, activity
    for msg_num in required:
        if msg_num not in messages or messages[msg_num]['data'] == 0:
            name = MESSAGE_NAMES.get(msg_num, f'unknown_{msg_num}')
            issues.append(f"   ❌ Missing required message: {msg_num} ({name})")
    
    if issues:
        for issue in issues:
            print(issue)
    else:
        print("   ✅ No obvious issues detected")
    
    print()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python inspect_fit.py <file.fit> [file2.fit ...]")
        sys.exit(1)
    
    for arg in sys.argv[1:]:
        filepath = Path(arg)
        if not filepath.exists():
            print(f"❌ File not found: {filepath}")
            continue
        
        inspect_fit(filepath)
        print()
