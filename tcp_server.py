import socketserver
import datetime
import socket
import ssl
import requests

# Define paths for storing the flat files
HL7_FILE_PATH = "hl7_message.txt"

# Conversion functions
def validate_hl7_message(hl7_message):
    """
    Validates an HL7 message.

    Args:
        hl7_message (str): The HL7 message to validate.

    Returns:
        tuple: A tuple containing a boolean indicating whether the message is valid and an error message if applicable.
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
    
    Raises:
        ValueError: If the MSH segment of the HL7 message does not contain enough fields.
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


def forward_to_remote_host(hl7_message, remote_host, remote_port):
    """
    Forwards an HL7 message to a remote TCP host.

    Args:
        hl7_message (str): The HL7 message to forward.
        remote_host (str): The hostname or IP address of the remote TCP host.
        remote_port (int): The port number of the remote TCP host.

    Returns:
        str: The response received from the remote TCP host.
    """

    context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile='./keys/tcp_server-cert.pem', keyfile='./keys/tcp_server-key.pem')

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        
        # Wrap the socket in TLS
        with context.wrap_socket(sock, server_side=True) as ssock:

            # Once socked is wrapped, reference the 'ssock' var going forward rather than 'sock'
            ssock.connect((remote_host, remote_port))
            ssock.sendall(hl7_message.encode('utf-8'))
            response = ssock.recv(1024).decode('utf-8')
            return response


def send_to_http_server(hl7_message):

    # Presume encrypt both the contents of the hl7_message, and the http connection down the line - need certs  
    # https://requests.readthedocs.io/en/latest/user/advanced/#ssl-cert-verification

    """
    Sends an HL7 message to an HTTP server.

    Args:
        hl7_message (str): The HL7 message to send.

    Returns:
        str: The response received from the HTTP server.
    """
    response = requests.post('http://localhost:8080/http_hl7', data=hl7_message, headers={'Content-Type': 'text/plain'})
    return response.text

 
class HL7TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        """
        Handles an incoming TCP connection and processes the HL7 message.

        This method is called for each incoming connection to the TCP server.
        """
        try:

            context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile='./keys/tcp-server-cert.pem', keyfile='./keys/tcp-server-key.pem')

            self.request = context.wrap_socket(self.request, server_side=True)

            data = self.request.recv(1024).strip().decode('utf-8')
            print(f"Received HL7 message:\n{data}")

            # Save the HL7 message to a flat file - encrypt? 
            with open(HL7_FILE_PATH, 'w') as file:
                file.write(data)
            
            # Validate and generate ACK message
            is_valid, validation_error = validate_hl7_message(data)
            if is_valid:
                ack_message = generate_ack(data, ack_type='AA')
            else:
                ack_message = generate_ack(data, ack_type='AE', error_message=validation_error)
            
            self.request.sendall(ack_message.encode('utf-8'))
            
            # # Forward the HL7 message to a remote TCP host
            # remote_host = 'localhost'  # Replace with actual remote host
            # remote_port = 8082  # Replace with actual remote port
            # remote_response = forward_to_remote_host(data, remote_host, remote_port)
            # print(f"Forwarded HL7 message to remote TCP host. Response: {remote_response}")
            
            # Forward the HL7 message to the HTTP server
            http_response = send_to_http_server(data)
            print(f"Forwarded HL7 message to HTTP server. Response: {http_response}")
        
        except Exception as e:
            error_message = f"Error processing message: {str(e)}"
            print(error_message)
            self.request.sendall(error_message.encode('utf-8'))

def run_tcp_server(host='localhost', port=8081):
    """
    Runs the TCP server.

    Args:
        host (str, optional): The hostname or IP address to bind the server to. Defaults to 'localhost'.
        port (int, optional): The port number to bind the server to. Defaults to 8081.
    """
    server = socketserver.TCPServer((host, port), HL7TCPHandler)
    print(f"Starting TCP server on {host}:{port}")
    server.serve_forever()

if __name__ == "__main__":
    run_tcp_server()