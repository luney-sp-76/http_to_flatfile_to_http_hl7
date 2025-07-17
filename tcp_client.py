import socket
import ssl
from pathlib import Path

BASE_DIR = Path.cwd()

keys_dir = BASE_DIR / "keys"
if not keys_dir.exists():
    keys_dir.mkdir(parents=True)


def send_hl7_message(hl7_message, host='localhost', port=6001):
    """
    Sends an HL7 message to a TCP server.

    Args:
        hl7_message (str): The HL7 message to be sent.
        host (str, optional): The hostname
        or IP address of the TCP server.
        Defaults to 'localhost'.
        port (int, optional): The port number of the TCP server.
        Defaults to 8081.

    Returns:
        str: The response received from the TCP server.
    """

    context = ssl.create_default_context()
    context.verify_mode = ssl.CERT_REQUIRED
    ca_cert_path = keys_dir / "ca-cert.pem"
    client_cert_path = keys_dir / "tcp-client-cert.pem"
    client_key_path = keys_dir / "tcp-client-key.pem"

    if not ca_cert_path.exists():
        raise FileNotFoundError(f"CA certificate not found at {ca_cert_path}")
    if not client_cert_path.exists():
        raise FileNotFoundError(
            f"Client certificate not found at {client_cert_path}")
    if not client_key_path.exists():
        raise FileNotFoundError(f"Client key not found at {client_key_path}")

    context.load_verify_locations(cafile=str(ca_cert_path))
    context.load_cert_chain(
        certfile=str(client_cert_path),
        keyfile=str(client_key_path)
    )

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with context.wrap_socket(sock, server_hostname=host) as ssock:
            ssock.connect((host, port))

            # Encrypt the message before sending?
            ssock.sendall(hl7_message.encode('utf-8'))
            response = ssock.recv(1024).decode('utf-8')
            return response


if __name__ == "__main__":
    # Example HL7 message
    hl7_message = (
        "MSH|^~\\&|TST|DOH|ADT|RIH|20230523102000||ADT^A31|123456|P|2.4\n"
        "EVN|A31|20230523102000\n"
        "PID|1||12345678^^^RIH^MR||Doe^John^A||19800101|M|||456 Elm St"
        "^^Newtown^CA^90211^USA||555-5678|||||M|N|123-45-6789\n"
        "PV1|1|O|^^^RIH||||1234^Smith^John^A|||||||||||||||12345678"
    )

    # Send HL7 message to server
    response = send_hl7_message(hl7_message)
    print("Response from TCP server:")
    print(response)
