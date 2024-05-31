import socketserver
import datetime
import socket
import requests

# Define paths for storing the flat files
HL7_FILE_PATH = "hl7_message.txt"

# Conversion functions
def validate_hl7_message(hl7_message):
    segments = hl7_message.strip().replace('\n', '\r').split('\r')
    
    if len(segments) < 2:
        return False, "Message does not contain enough segments"
    
    msh_segment = segments[0].split('|')
    
    if msh_segment[0] != 'MSH':
        return False, "Missing MSH segment"
    if len(msh_segment) < 12:
        return False, "MSH segment does not contain enough fields"
    
    return True, None

def generate_ack(hl7_message, ack_type='AA', error_message=None):
    segments = hl7_message.strip().replace('\n', '\r').split('\r')
    msh_segment = segments[0].split('|')
    if len(msh_segment) < 10:
        raise ValueError("Invalid MSH segment: not enough fields to extract message control ID")

    message_control_id = msh_segment[9]
    
    current_time = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    ack_msh_segment = [
        'MSH', '^~\\&', msh_segment[5], msh_segment[4], msh_segment[3], msh_segment[2],
        current_time, '', 'ACK', message_control_id, 'P', '2.4'
    ]
    
    msa_segment = ['MSA', ack_type, message_control_id]
    if ack_type != 'AA' and error_message:
        msa_segment.append(error_message)
    
    ack_message = '|'.join(ack_msh_segment) + '\r' + '|'.join(msa_segment) + '\r'
    return ack_message

def forward_to_remote_host(hl7_message, remote_host, remote_port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((remote_host, remote_port))
        sock.sendall(hl7_message.encode('utf-8'))
        response = sock.recv(1024).decode('utf-8')
        return response

def send_to_http_server(hl7_message):
    response = requests.post('http://localhost:8080/http_hl7', data=hl7_message, headers={'Content-Type': 'text/plain'})
    return response.text

class HL7TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            data = self.request.recv(1024).strip().decode('utf-8')
            print(f"Received HL7 message:\n{data}")

            # Save the HL7 message to a flat file
            with open(HL7_FILE_PATH, 'w') as file:
                file.write(data)
            
            # Validate and generate ACK message
            is_valid, validation_error = validate_hl7_message(data)
            if is_valid:
                ack_message = generate_ack(data, ack_type='AA')
            else:
                ack_message = generate_ack(data, ack_type='AE', error_message=validation_error)
            
            # Send the ACK message back to the client
            self.request.sendall(ack_message.encode('utf-8'))
            
            # Forward the HL7 message to a remote TCP host
            remote_host = 'localhost'  # Replace with actual remote host
            remote_port = 8082  # Replace with actual remote port
            remote_response = forward_to_remote_host(data, remote_host, remote_port)
            print(f"Forwarded HL7 message to remote TCP host. Response: {remote_response}")
            
            # Forward the HL7 message to the HTTP server
            http_response = send_to_http_server(data)
            print(f"Forwarded HL7 message to HTTP server. Response: {http_response}")
        
        except Exception as e:
            error_message = f"Error processing message: {str(e)}"
            print(error_message)
            self.request.sendall(error_message.encode('utf-8'))

def run_tcp_server(host='localhost', port=8081):
    server = socketserver.TCPServer((host, port), HL7TCPHandler)
    print(f"Starting TCP server on {host}:{port}")
    server.serve_forever()

if __name__ == "__main__":
    run_tcp_server()
