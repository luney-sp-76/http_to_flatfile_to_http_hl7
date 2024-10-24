import socket
import ssl

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

    context = ssl.create_default_context()
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile='./keys/ca-cert.pem')
    context.load_cert_chain(certfile="./keys/tcp-client-cert.pem", keyfile="./keys/tcp-client-key.pem")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with context.wrap_socket(sock, server_hostname=host) as ssock:
            ssock.connect((host, port))

            # Encrypt the message before sending? 
            ssock.sendall(hl7_message.encode('utf-8'))
            response = ssock.recv(1024).decode('utf-8')
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
