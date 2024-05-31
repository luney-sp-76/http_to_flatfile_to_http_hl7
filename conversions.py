import datetime

# Conversion functions
def hl7_to_plain_text(hl7_message):
    if not hl7_message:
        raise ValueError("Empty HL7 message")
    
    segments = hl7_message.strip().split('\r')
    if len(segments) < 2:
        raise ValueError("Invalid HL7 message format: not enough segments")

    plain_text = ""
    for segment in segments:
        fields = segment.split('|')
        if len(fields) < 2:
            raise ValueError(f"Invalid segment format: {segment}")
        
        segment_name = fields[0]
        plain_text += f"Segment: {segment_name}\n"
        for i, field in enumerate(fields[1:], start=1):
            plain_text += f"  Field {i}: {field}\n"
        plain_text += "\n"
    
    return plain_text

def plain_text_to_hl7(plain_text):
    if not plain_text:
        raise ValueError("Empty plain text message")
    
    lines = plain_text.strip().split('\n')
    hl7_message = ""
    segment = ""
    
    for line in lines:
        if line.startswith("Segment:"):
            if segment:
                hl7_message += segment.rstrip('|') + '\r'
            segment = line.split(':')[1].strip() + '|'
        elif line.startswith("  Field"):
            field_value = line.split(':')[1].strip()
            segment += field_value + '|'
        else:
            raise ValueError(f"Invalid line format: {line}")
    
    hl7_message += segment.rstrip('|') + '\r'
    return hl7_message

# Validation and ACK functions
def validate_hl7_message(hl7_message):
    segments = hl7_message.strip().split('\r')
    
    if len(segments) < 2:
        return False, "Message does not contain enough segments"
    
    msh_segment = segments[0].split('|')
    
    if msh_segment[0] != 'MSH':
        return False, "Missing MSH segment"
    if len(msh_segment) < 12:
        return False, "MSH segment does not contain enough fields"
    
    return True, None

def generate_ack(hl7_message, ack_type='AA', error_message=None):
    segments = hl7_message.strip().split('\r')
    msh_segment = segments[0].split('|')
    if len(msh_segment) < 10:
        raise ValueError("Invalid MSH segment: not enough fields to extract message control ID")

    message_control_id = msh_segment[9]
    
    current_time = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    ack_msh_segment = [
        'MSH', '^~\\&', msh_segment[5], msh_segment[4], msh_segment[3], msh_segment[2],
        current_time, '', 'ACK', message_control_id, 'P', '2.3'
    ]
    
    msa_segment = ['MSA', ack_type, message_control_id]
    if ack_type != 'AA' and error_message:
        msa_segment.append(error_message)
    
    ack_message = '|'.join(ack_msh_segment) + '\r' + '|'.join(msa_segment) + '\r'
    return ack_message

# Main handling functions
def handle_plain_text_to_hl7(plain_text):
    hl7_message = plain_text_to_hl7(plain_text)
    is_valid, validation_error = validate_hl7_message(hl7_message)
    
    if is_valid:
        ack_message = generate_ack(hl7_message, ack_type='AA')
    else:
        ack_message = generate_ack(hl7_message, ack_type='AE', error_message=validation_error)
    
    return hl7_message, ack_message

def handle_hl7_to_plain_text(hl7_message):
    plain_text = hl7_to_plain_text(hl7_message)
    is_valid, validation_error = validate_hl7_message(hl7_message)
    
    if is_valid:
        ack_message = generate_ack(hl7_message, ack_type='AA')
    else:
        ack_message = generate_ack(hl7_message, ack_type='AE', error_message=validation_error)
    
    return plain_text, ack_message
