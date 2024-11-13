import random
import socket
import ssl
import time
from bespoke_functions import generate_and_upload, retrieve_patients, generate_fhir_docs, upload_fhir_to_firestore, \
    process_import_folder, IMPORT_FOLDER_PATH, update_patients, retrieve_patient_by_name, show_created_patients
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
    # Need to reword this
    print("2: Upload all fhir patient docs in the 'work' folder to the database")
    print("3: Generate new patients and upload to database")
    print("4: Import Fhir and HL7 files found in the 'import' folder")
    print("5: Show names, genders, and number of HL7 IDs associated with all uploaded patients")
    print("6: Retrieve patients from the database within a given age range")
    print("7: Search for and retrieve a patient by first and last name")
    print("8: Clear the 'Work' folder, removing all fhir patient records")
    print("9: Exit")


def hl7_message_menu(patients: list[PatientInfo]) -> None: 
    """ Displays messages that may be generated using present patient information
    """
    
    # List of tuples with each tuple containing a panel code and corresponding description
    panel_list = [
        ("17K", "17-KETOSTEROIDS (URINARY)", 5, 25, "mg/24hr"),
        ("17O", "17 ALPHA OH PROG", 20, 100, "ng/dL"),
        ("17P", "17 ALPHA OH PROG - SPS", 20, 100, "ng/dL"),
        ("5NT", "5 NUCLEOTIDASE", 0, 11, "U/L"),
        ("A1A", "ALPHA 1 ANTITRYPSIN STOOL", 1.5, 3.5, "g/L"),
        ("ACA", "ACYL-CARNITINE", 10, 60, "µmol/L"),
        ("ACT", "ACTH", 10, 60, "pg/mL"),
        ("ACU", "ALCOHOL SCREEN - URINE", 0, 400, "mg/dL"),  # Negative or variable if positive
        ("AFA", "AFP (AMNIOTIC FLUID)", 0, 500, "ng/mL"),  # Ranges depend on pregnancy stage and lab
        ("AFM", "AFP (MATERNAL)", 10, 150, "ng/mL"),
        ("AGP", "A1 ACID GLYCOPROTEIN", 0.4, 1.2, "g/L"),
        ("ALD", "ALDOSTERONE", 3, 30, "ng/dL"),
        ("ALI", "ALP. PHOS. ISOENZYMES", 44, 147, "U/L"),  # Total ALP range, isoenzymes vary
        ("ALO", "ALDOLASE", 1.0, 7.5, "U/L"),
        ("ATM", "ACTIVATED CLOTTING TIME +", 80, 120, "seconds"),
        ("HYC", "17-HYDROXYCORTICOSTEROIDS", 3, 12, "mg/24hr"),
        ("PCR", "ACT. PROTEIN C RESISTANCE", 1.0, 5.0, "Ratio"),  # Ratio with no upper bound in standard labs
        ("SAP", "ACID PHOSPHATASE", 0, 3.5, "ng/mL"),
        ("VD3", "1 25 DIHYDROXY VITAMIN D3", 20, 65, "pg/mL")
    ]

    
    try: 
    
        print("\nThe following options may be selected to update the patient record, in both Ultra and the database.")
        
        print("\nSelect a number from the menu below.")
        print("1: Generate ORM^O01 message(s)")
        print("2: Generate ORU^R01 message(s)")
        print("3: No further action")

        choice = input("\n: ")
        
        assert(1 <= int(choice) <= 3)
        
        if choice == "3": pass
        
        else:
            print("\nSelect the type of message to generate using a number from the menu below.")

            for i, pair in enumerate(panel_list):
                print(f"{i+1}: {pair[0]} {pair[1]}")
                
            panel_choice = input("\n: ")
            
            assert(1 <= int(panel_choice) <= len(panel_list))
            
            if choice == "1": 
                # Generate HL7 messages
                for patient in patients: 
                    try: 
                        hl7 = create_orm_message(
                                patient_info=patient, 
                                messageType="ORM_O01", 
                                panel_choice=f"{panel_list[int(panel_choice)-1][0]}^{panel_list[int(panel_choice)-1][1]}^L"
                            )
                        
                        if not hl7:
                            raise Exception("Error encountered during message construction")
                        # Perform action here - could be save to flatfile, send to Ultra, etc.
                        HL7_PROCESSOR.save_hl7_message_to_file(hl7_message=hl7, patient_id=patient.id)
                        # forward_to_ultra(hl7_message=hl7)
                    except Exception as e: 
                        print(f"Message generation for patient {patient.id} failed: {repr(e)}")
                    else:
                        print(f"Message for patient {patient.id} generated successfully")
                # Send HL7 messages to Ultra 
                update_patients(db=FIRESTORE_DB, folder_path=HL7_FOLDER_PATH)

            elif choice == "2": 
                
                sample_lower_bound = panel_list[int(panel_choice)-1][2]
                sample_upper_bound = panel_list[int(panel_choice)-1][3]
                
                # For steps of 0.1...
                sample_finding = str(random.randrange(sample_lower_bound*10, sample_upper_bound*10, 1) / 10)
                sample_finding_units = panel_list[int(panel_choice)-1][4]
                
                print("Selected finding and units alright...")
                
                # Generate HL7 messages
                for patient in patients: 
                    try:
                        hl7 = create_oru_message(patient_info=patient, messageType="ORU_R01", 
                                                 panel_choice=f"{panel_list[int(panel_choice)-1][0]}^{panel_list[int(panel_choice)-1][1]}^L", 
                                                 result=sample_finding, result_type="NM", units=sample_finding_units)
                        if not hl7:
                            raise Exception("Error encountered during message construction")
                        # Perform action here - could be save to flatfile, send to Ultra, etc.
                        HL7_PROCESSOR.save_hl7_message_to_file(hl7_message=hl7, patient_id=patient.id)
                        # forward_to_ultra(hl7_message=hl7)
                    except Exception as e: 
                        print(f"Message generation for patient {patient.id} failed: {repr(e)}")
                    else:
                        print(f"Message for patient {patient.id} generated successfully")
                # Send HL7 messages to Ultra 
                update_patients(db=FIRESTORE_DB, folder_path=HL7_FOLDER_PATH)
            
    except AssertionError:
        print("Unrecognised input - please select a number from the menu below.")
        hl7_message_menu(patients=patients)
            
    except Exception as e:
        print(f"The following exception occurred: {repr(e)}")


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
            if patients:
                hl7_message_menu(patients=patients)
                
        elif choice == "5":
            show_created_patients(db=FIRESTORE_DB)

        elif choice == "6": 
            patients = retrieve_patients(db=FIRESTORE_DB)
            if patients: 
                hl7_message_menu(patients=patients)
                
        elif choice == "7":
            patients = retrieve_patient_by_name(db=FIRESTORE_DB)
            if patients:
                hl7_message_menu(patients=patients)
            
        elif choice == "8":
            clear_work_folder()

        elif choice == "9": 
            stop_servers()
            print("Goodbye.")
            exit = True
            
        else: 
            print("Input not recognised, please try again. ")