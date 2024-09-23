import socket
import ssl
import time
from bespoke_functions import generate_and_upload, retrieve_patients, generate_fhir_docs, upload_fhir_to_firestore, \
    process_import_folder, IMPORT_FOLDER_PATH
from poll_synthea.main import initialize_firestore, create_orm_message, create_adt_message, create_oru_message, HL7MessageProcessor
from poll_synthea.generators.utilities import PatientInfo
from client import send_hl7_to_server
import os, os.path
import pathlib 
import glob
import subprocess

# Server details 
SERVER_HOST = 'localhost'
SERVER_PORT = 8080
TCP_SERVER_HOST = 'localhost'
TCP_SERVER_PORT = 8081
DUMMY_ULTRA_HOST = 'localhost'
DUMMY_ULTRA_PORT = 8082

# Server processes 
SERVER_PROCESSES = []

# Global firestore client
FIRESTORE_DB = initialize_firestore()

# Folder paths 
BASE_DIR = pathlib.Path.cwd()
HL7_FOLDER_PATH = BASE_DIR / "HL7gen"
WORK_FOLDER_PATH = BASE_DIR / "Work"

# HL7 processor
HL7_PROCESSOR = HL7MessageProcessor(hl7_folder_path=HL7_FOLDER_PATH, db=FIRESTORE_DB)

"""
SCHEMA

------------------------------------------------------------
What functionality should be offered to the user? 

- Retrieve patients from Firestore within a certain age range 
    - Storage of these patients locally? 

- Generate new patients, and choose whether or not to upload them to Firestore 

- Generate ADT, ORM^O01, and ORU^R01 messages 
    - Forward these to the remote server
    - Save them locally in a text file 

------------------------------------------------------------

What functionality should be going on in the background? 

- Reception of messages from other sources, and resulting updates of Firestore 

------------------------------------------------------------
"""

def clear_work_folder():
    
    confirmation = input("THIS ACTION IS IRREVERSIBLE. \nType 'clear work' if you are sure you want to clear the work folder. \n: ")
    
    if confirmation == "clear work":
        folder = pathlib.Path(WORK_FOLDER_PATH)
        for item in folder.iterdir():
            item.unlink()
        print("Work folder cleared.")
    else:
        print("Action aborted.")


def clear_hl7_folder():
    
    confirmation = input("THIS ACTION IS IRREVERSIBLE. \nType 'clear hl7' if you are sure you want to clear the hl7 folder. \n: ")
    
    if confirmation == "clear hl7":
        folder = pathlib.Path(HL7_FOLDER_PATH)
        for item in folder.iterdir():
            item.unlink()
        print("HL7 folder cleared.")
    else:
        print("Action aborted.")


def start_servers(show_servers:bool=False):
    print("Starting servers...")
    servers = ['.\\server.py', '.\\tcp_server.py', '.\\dummy_ultra.py']
    
    if not show_servers:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # Hide the window
        for server in servers:
            proc = subprocess.Popen(f'py {server}', startupinfo=startupinfo, creationflags=subprocess.CREATE_NO_WINDOW)
            SERVER_PROCESSES.append(proc)
    else:
        for server in servers:
            proc = subprocess.Popen(f'start py {server}', shell=True, stdin=None, stdout=None, stderr=None)
            SERVER_PROCESSES.append(proc)
    time.sleep(5)
    print("Servers started.")


def stop_servers():
    print("Stopping servers...")
    for proc in SERVER_PROCESSES:
        if proc.poll() is None:  # None means the process is still running
            print(f"Terminating process {proc.pid}")
            proc.terminate()  # Use terminate to gracefully stop the process
            proc.wait()  # Wait for it to fully exit


def check_server_status() -> None:
    """ Used to notify the user of potential issues communicating with servers. 
    """
    print("Checking HTTP server status...")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((SERVER_HOST, SERVER_PORT))
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
    except socket.error:
        print(f"WARNING: UNABLE TO CONNECT TO SERVER USING HOST {SERVER_HOST} AND PORT {SERVER_PORT}.")
        time.sleep(1)
    else: 
        print("Server is listening.")

    print("Checking TCP server status...")
    try:
        context = ssl.create_default_context()
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile='./keys/ca-cert.pem')
        context.load_cert_chain(certfile="./keys/tcp-client-cert.pem", keyfile="./keys/tcp-client-key.pem")

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            with context.wrap_socket(sock, server_hostname=TCP_SERVER_HOST) as ssock:
                ssock.connect((TCP_SERVER_HOST, TCP_SERVER_PORT))
                ssock.shutdown(socket.SHUT_RDWR)
                ssock.close()
    except socket.error:
        print(f"WARNING: UNABLE TO CONNECT TO SERVER USING HOST {TCP_SERVER_HOST} AND PORT {TCP_SERVER_PORT}.")
        time.sleep(1)
    else: 
        print("TCP server is listening.")
        
    print("Checking dummy ULTRA TCP server status...")
    try:
        context = ssl.create_default_context()
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile='./keys/ca-cert.pem')
        context.load_cert_chain(certfile="./keys/tcp-client-cert.pem", keyfile="./keys/tcp-client-key.pem")

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            with context.wrap_socket(sock, server_hostname=DUMMY_ULTRA_HOST) as ssock:
                ssock.connect((DUMMY_ULTRA_HOST, DUMMY_ULTRA_PORT))
                ssock.shutdown(socket.SHUT_RDWR)
                ssock.close()
    except socket.error:
        print(f"WARNING: UNABLE TO CONNECT TO DUMMY ULTRA SERVER USING HOST {DUMMY_ULTRA_HOST} AND PORT {DUMMY_ULTRA_PORT}.")
        time.sleep(1)
    else: 
        print("TCP server is listening.")


def main_menu() -> None:
    """ Displays a menu to the user, enumerating their options. 
    """
    print("\nSelect a number from the menu below.")
    print("1: Generate fhir docs and store in the 'work' folder")
    print("2: Upload all patients in the 'work' folder to the database")
    print("3: Generate new patients and upload to database")
    print("4: Import Fhir and HL7 files in the 'import' folder")
    print("5: Retrieve patients from the database within a given age range")
    print("6: Clear the 'Work' folder, removing all fhir patient records")
    print("7: Exit")


def hl7_message_menu(patients: list[PatientInfo]) -> None: 
    """ Displays messages that may be generated using present patient information
    """
    
    print("\nSelect a number from the menu below.\nGenerated HL7 messages are stored in the 'HL7gen' folder.")
    print("1: Generate ADT^A01 message(s)")
    print("2: Generate ORM^O01 message(s)")
    print("3: Generate ORU^R01 message(s)")
    print("4: No further action")

    choice = input("\n: ")
    if choice == "1": 
        for patient in patients: 
            try:
                hl7 = create_adt_message(patient_info=patient, messageType="ADT_A01")

                # Perform action here - could be save to flatfile, send to Ultra, etc.
                HL7_PROCESSOR.save_hl7_message_to_file(hl7_message=hl7, patient_id=patient.id)
                # forward_to_ultra(hl7_message=hl7)
            except Exception as e: 
                print(f"Message generation for patient {patient.id} failed: {repr(e)}")
            else:
                print(f"Message for patient {patient.id} generated successfully")

    elif choice == "2": 
        for patient in patients: 
            try: 
                hl7 = create_orm_message(patient_info=patient, messageType="ORM_O01")

                # Perform action here - could be save to flatfile, send to Ultra, etc.
                HL7_PROCESSOR.save_hl7_message_to_file(hl7_message=hl7, patient_id=patient.id)
                # forward_to_ultra(hl7_message=hl7)
            except Exception as e: 
                print(f"Message generation for patient {patient.id} failed: {repr(e)}")
            else:
                print(f"Message for patient {patient.id} generated successfully")

    elif choice == "3": 
        for patient in patients: 
            try:
                hl7 = create_oru_message(patient_info=patient, messageType="ORU_R01")

                # Perform action here - could be save to flatfile, send to Ultra, etc.
                HL7_PROCESSOR.save_hl7_message_to_file(hl7_message=hl7, patient_id=patient.id)
                # forward_to_ultra(hl7_message=hl7)
            except Exception as e: 
                print(f"Message generation for patient {patient.id} failed: {repr(e)}")
            else:
                print(f"Message for patient {patient.id} generated successfully")

    elif choice == "4": 
        pass 

    else: 
        print("Unrecognised input - please select a number from the menu below.")
        hl7_message_menu(patients=patients)


if __name__ == '__main__':
    start_servers()
    check_server_status()
    pathlib.Path(IMPORT_FOLDER_PATH).mkdir(exist_ok=True)
    exit = False 
    while not exit:
        main_menu()
        choice = input("\n: ")
        
        if choice == "1":
            generate_fhir_docs()
            
        if choice == "2":
            patients = upload_fhir_to_firestore(db=FIRESTORE_DB)
            if patients:
                hl7_message_menu(patients=patients)
        
        elif choice == "3": 
            patients = generate_and_upload(db=FIRESTORE_DB)
            if patients: 
                hl7_message_menu(patients=patients)
            
        elif choice == "4":
            patients = process_import_folder(db=FIRESTORE_DB)
            if patients: hl7_message_menu(patients=patients)

        elif choice == "5": 
            patients = retrieve_patients(db=FIRESTORE_DB)
            if patients: hl7_message_menu(patients=patients)
            
        elif choice == "6":
            clear_work_folder()

        elif choice == "7": 
            stop_servers()
            print("Goodbye.")
            exit = True
            
        else: 
            print("Input not recognised, please try again. ")