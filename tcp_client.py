import socket
import ssl

"""
Example of client secure socket using certs and host name 
from https://docs.python.org/3/library/ssl.html

hostname = 'www.python.org'
# PROTOCOL_TLS_CLIENT requires valid cert chain and hostname
context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
context.load_verify_locations('path/to/cabundle.pem')

with socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0) as sock:
    with context.wrap_socket(sock, server_hostname=hostname) as ssock:
        print(ssock.version())
"""

def send_hl7_message(hl7_message, host='localhost', port=8081):
    """
    Sends an HL7 message to a TCP server.

    Args:
        hl7_message (str): The HL7 message to be sent.
        host (str, optional): The hostname or IP address of the TCP server. Defaults to 'localhost'.
        port (int, optional): The port number of the TCP server. Defaults to 8081.

    Returns:
        str: The response received from the TCP server.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with ssl.wrap_socket(sock, ssl_version=ssl.PROTOCOL_TLS, ciphers="ADH-AES256-SHA") as wsock:
            wsock.connect((host, port))

            # Encrypt the message before sending? 
            wsock.sendall(hl7_message.encode('utf-8'))
            response = wsock.recv(1024).decode('utf-8')
            return response

if __name__ == "__main__":
    # Example HL7 message
    hl7_message = """MSH|^~\\&|HIS|RIH|ADT|RIH|20230523102000||ADT^A31|123456|P|2.4
EVN|A31|20230523102000
PID|1||12345678^^^RIH^MR||Doe^John^A||19800101|M|||456 Elm St^^Newtown^CA^90211^USA||555-5678|||||M|N|123-45-6789
PV1|1|O|^^^RIH||||1234^Smith^John^A|||||||||||||||12345678"""

    # Send HL7 message to server
    response = send_hl7_message(hl7_message)
    print("Response from TCP server:")
    print(response)
