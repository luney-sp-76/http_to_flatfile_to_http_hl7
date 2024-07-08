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
#     hl7_message = """MSH|^~\\&|HIS|RIH|ADT|RIH|20230523102000||ADT^A31|123456|P|2.4
# EVN|A31|20230523102000
# PID|1||12345679^^^RIH^MR||Doe^John^A||19800101|M|||456 Elm St^^Newtown^CA^90211^USA||555-5678|||||M|N|123-45-6789
# PV1|1|O|^^^RIH||||1234^Smith^John^A|||||||||||||||12345678"""

    hl7_message = """MSH|^~\&|LabSystem|LabFacility|ClinicSystem|ClinicFacility|202407011200||ORU^R01|67890|P|2.4|
PID|1|PK123456|KK12346^^^Hosp^MR||Kong^King^Jr||19331108|M|||123 Jungle Ave^^Skull Island^SI^99999^Pacific|555-1234|||M||KK98765^^^Hosp^MR||123-45-6789|
PV1|1|O|Outpatient^Clinic^1^Hosp^^Room^1|3|||99999^Smith^John^A^III|99999^Johnson^Emily||Consulting^99999|General^99999|||||||||99999^Brown^Charlie|||||||||||||||||||||||||202407011130|
ORC|RE|ORD67890|OBS67890|456||CM||||202407011200|99999^Smith^John^A^III|
OBR|1|ORD67890|OBS67890|5678^Comprehensive Metabolic Panel^L||202407011130|202407011130|||||||99999^Smith^John^A^III|||||||||F||||||||
OBX|1|NM|5892-1^Glucose^LN||95|mg/dL|70-99|N|||F
OBX|2|NM|17861-6^Calcium^LN||9.5|mg/dL|8.5-10.2|N|||F
OBX|3|NM|6690-2^Potassium^LN||4.2|mmol/L|3.5-5.1|N|||F
"""

    # Send HL7 message to server
    response = send_hl7_message(hl7_message)
    print("Response from TCP server:")
    print(response)
