from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import socket
import datetime
import ssl
import requests
from poll_synthea.generators.utilities import parse_HL7_message, save_to_firestore, \
    parse_fhir_message, update_following_ORM_O01, update_following_ORU_R01
from poll_synthea.main import initialize_firestore

# Define paths for storing the flat files
HL7_FILE_PATH = "hl7_message.txt"
FHIR_FILE_PATH = "fhir_doc.json"

# Global firestore client
FIRESTORE_DB = initialize_firestore()

# Conversion functions
def validate_hl7_message(hl7_message):
    """
    Validates an HL7 message.

    Args:
        hl7_message (str): The HL7 message to validate.

    Returns:
        tuple: A tuple containing a boolean indicating whether the message is valid and an error message if it is not valid.
    """
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
    """
    Generates an ACK (Acknowledgment) message for an HL7 message.

    Args:
        hl7_message (str): The HL7 message to generate the ACK for.
        ack_type (str, optional): The type of ACK. Defaults to 'AA'.
        error_message (str, optional): The error message to include in the ACK if the ACK type is not 'AA'. Defaults to None.

    Returns:
        str: The generated ACK message.
    """
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
    """
    Sends an HL7 message to a TCP server.

    Args:
        hl7_message (str): The HL7 message to send.
        tcp_host (str, optional): The TCP server host. Defaults to 'localhost'.
        tcp_port (int, optional): The TCP server port. Defaults to 8081.

    Returns:
        str: The response from the TCP server.
    """

    context = ssl.create_default_context()
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile='./keys/ca-cert.pem')
    context.load_cert_chain(certfile="./keys/tcp-client-cert.pem", keyfile="./keys/tcp-client-key.pem")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with context.wrap_socket(sock, server_hostname=tcp_host) as ssock:
            ssock.connect((tcp_host, tcp_port))

            ssock.sendall(hl7_message.encode('utf-8'))
            response = ssock.recv(1024).decode('utf-8')
            return response
        

class HL7HTTPRequestHandler(BaseHTTPRequestHandler):
    """
    Custom HTTP request handler for HL7 messages.
    """

    def do_POST(self):
        """
        Handles POST requests.
        """
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

                print(f"Post data received: \n{post_data}")

                hl7, patient_info = parse_HL7_message(msg=post_data, db=FIRESTORE_DB)

                if patient_info:
                    if hl7.msh.msh_9.to_er7() == "ADT^A01":
                        print("Received patient information - preparing to upload to firestore...")
                        response_code = save_to_firestore(db=FIRESTORE_DB, patient_info=patient_info)
                    elif hl7.msh.msh_9.to_er7() == "ORM^O01":
                        print("Received patient observation request - preparing to update patient info...")
                        response_code = update_following_ORM_O01(db=FIRESTORE_DB, patient_info=patient_info)
                    elif hl7.msh.msh_9.to_er7() == "ORU^R01": 
                        print("Received patient observation result - preparing to update patient info...")
                        response_code = update_following_ORU_R01(db=FIRESTORE_DB, patient_info=patient_info)
                    else: 
                        print("Unsupported message type.")
                        response_code = 500
                        
                # # Forward the HL7 message to another domain?
                # domain_response = requests.post('https://testresponse.free.beeceptor.com/hl7', data=post_data, headers={'Content-Type': 'text/plain'})
                # print(f"Forwarded HL7 message to another domain. Response: {domain_response.text}")

                # Response to original POST request
                response = {
                    'hl7_message': post_data,
                    'ack_message': ack_message,
                    'domain_response': response_code
                }
                
                self.send_response(response_code)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))

            elif self.path == '/fhir':
                # Save the fhir document to a flat file
                with open(FHIR_FILE_PATH, 'w') as file:
                    file.write(post_data)

                # Validate and generate ACK message
                patient_info = None
                try:
                    patient_info = parse_fhir_message(db=FIRESTORE_DB, fhir_message=post_data)
                except Exception as e:
                    print(f"Unable to parse fhir doc: {repr(e)}")

                if patient_info:
                    ack_message = "Parsing success."
                    # Attempt to upload to Firestore - will work provided patient does not already exist 
                    response_code = save_to_firestore(db=FIRESTORE_DB, patient_info=patient_info)
                else:
                    ack_message = "Parsing failure."
                    response_code = 400

                print(f"Post data received: \n{post_data[:100]}...")

                # Response to original POST request
                response = {
                    'fhir_message': post_data[:100],
                    'ack_message': ack_message, 
                    'domain_response': response_code
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
    """
    Runs the HTTP server.

    Args:
        server_class (class, optional): The HTTP server class. Defaults to HTTPServer.
        handler_class (class, optional): The request handler class. Defaults to HL7HTTPRequestHandler.
        port (int, optional): The port to run the server on. Defaults to 8080.
    """
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting HTTP server on port {port}')
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
