from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import socket
import datetime
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

def send_to_tcp_server(hl7_message, tcp_host='localhost', tcp_port=8081):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((tcp_host, tcp_port))
        sock.sendall(hl7_message.encode('utf-8'))
        response = sock.recv(1024).decode('utf-8')
        return response

class HL7HTTPRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            if self.path == '/hl7_http':
                # Save the HL7 message to a flat file
                with open(HL7_FILE_PATH, 'w') as file:
                    file.write(post_data)
                
                # Validate and generate ACK message
                is_valid, validation_error = validate_hl7_message(post_data)
                if is_valid:
                    ack_message = generate_ack(post_data, ack_type='AA')
                else:
                    ack_message = generate_ack(post_data, ack_type='AE', error_message=validation_error)
                
                # Forward the HL7 message to the TCP server
                tcp_response = send_to_tcp_server(post_data)
                print(f"Forwarded HL7 message to TCP server. Response: {tcp_response}")

                response = {
                    'hl7_message': post_data,
                    'ack_message': ack_message,
                    'tcp_response': tcp_response
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))

            elif self.path == '/http_hl7':
                # Save the HL7 message to a flat file
                with open(HL7_FILE_PATH, 'w') as file:
                    file.write(post_data)
                
                # Validate and generate ACK message
                is_valid, validation_error = validate_hl7_message(post_data)
                if is_valid:
                    ack_message = generate_ack(post_data, ack_type='AA')
                else:
                    ack_message = generate_ack(post_data, ack_type='AE', error_message=validation_error)
                
                # Forward the HL7 message to another domain
                domain_response = requests.post('https://testresponse.free.beeceptor.com/hl7', data=post_data, headers={'Content-Type': 'text/plain'})
                print(f"Forwarded HL7 message to another domain. Response: {domain_response.text}")

                response = {
                    'hl7_message': post_data,
                    'ack_message': ack_message,
                    'domain_response': domain_response.text
                }
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'error': str(e)}
            self.wfile.write(json.dumps(response).encode('utf-8'))

def run_server(server_class=HTTPServer, handler_class=HL7HTTPRequestHandler, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting HTTP server on port {port}')
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
