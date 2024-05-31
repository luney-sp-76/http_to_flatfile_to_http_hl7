import requests
import json

# Define paths for storing the flat files
HL7_FILE_PATH = "hl7_message.txt"

def send_plain_text_to_server(plain_text, server_url='http://localhost:8080/hl7_http'):
    response = requests.post(server_url, data=plain_text, headers={'Content-Type': 'text/plain'})
    return response.json()

def send_hl7_to_server(hl7_message, server_url='http://localhost:8080/http_hl7'):
    response = requests.post(server_url, data=hl7_message, headers={'Content-Type': 'text/plain'})
    return response.json()

if __name__ == "__main__":
    # Example HL7 message
    hl7_message = """MSH|^~\&|HIS|RIH|ADT|RIH|20230523102000||ADT^A31|123456|P|2.4
EVN|A31|20230523102000
PID|1||12345678^^^RIH^MR||Doe^John^A||19800101|M|||456 Elm St^^Newtown^CA^90211^USA||555-5678|||||M|N|123-45-6789
PV1|1|O|^^^RIH||||1234^Smith^John^A|||||||||||||||12345678"""

    # Send plain text to server
    response = send_plain_text_to_server(hl7_message)
    print("Response from /hl7_http endpoint:")
    print(json.dumps(response, indent=2))

    # Read HL7 message from file
    with open(HL7_FILE_PATH, 'r') as file:
        hl7_message = file.read()

    # Send HL7 message to server
    response = send_hl7_to_server(hl7_message)
    print("Response from /http_hl7 endpoint:")
    print(json.dumps(response, indent=2))
