import json
import pathlib
from firebase_admin import firestore
from poll_synthea.generators.utilities import PatientInfo, call_for_patients, modify_for_age_range, \
    parse_fhir_message, patient_exists, save_to_firestore, parse_HL7_message, update_following_ORM_O01, \
    update_following_ORU_R01, get_firestore_age_range, under_document_size_limit
from poll_synthea.main import initialize_firestore, create_adt_message
from tcp_client import send_hl7_message
import random

# Paths 
BASE_DIR = pathlib.Path.cwd()
WORK_FOLDER_PATH = BASE_DIR / "Work"
IMPORT_FOLDER_PATH = BASE_DIR / "Import"
UPLOADED_FOLDER_PATH = BASE_DIR / "UploadedPatients"
FAILED_FOLDER_PATH = BASE_DIR / "FailedPatients"
HL7_GEN_FOLDER_PATH = BASE_DIR / "HL7gen"
SENT_HL7_PATH = BASE_DIR / "SentHL7"
FAILED_HL7_PATH = BASE_DIR / "UnsentHL7"


class UltraNotHappyError(Exception):
    pass

class DocumentSizeExceededError(Exception):
    pass

class PatientExistsError(Exception):
    pass


def hl7_to_string(hl7) -> str:
    converted_hl7 = ""
    for child in hl7.children: 
        converted_hl7 = converted_hl7 + f"{child.to_er7()}\n"
    return converted_hl7[:-1]


def generate_fhir_docs(num_of_patients:int=None, age_lower:int=None, age_upper:int=None, sex:str=None) -> None: 
    '''Generates ``x`` fhir documents and places them in the ``Work`` folder. 
    '''
    try: 
        if not num_of_patients:
            num_of_patients = int(input("Number of patients to generate: "))
        if num_of_patients < 1:
            raise Exception
        
        if not age_lower:
            age_lower = int(input("Minimum patient age: "))
        if age_lower < 0:
            raise Exception
        
        if not age_upper:
            age_upper = int(input("Maximum patient age: "))
        if age_upper < age_lower:
            raise Exception
        
        if not sex:
            sex = input("Sex of patients (M/F): ")
        if (sex != "M") and (sex != "F"):
            raise Exception
        
    except Exception: 
        print("Invalid input - returning to main menu. ")
        
    else:
        info = {
            "number_of_patients": num_of_patients,
            "age_from": age_lower, 
            "age_to": age_upper, 
            "sex": sex
        }
        # Generate patients using poll_synthea
        call_for_patients(info=info)


def upload_fhir_to_firestore(db: firestore.client, folder_path:pathlib.Path=WORK_FOLDER_PATH) -> list[PatientInfo] | None: 
    """Parses and uploads all patient records in a given folder to the database, contingent upon a response 
    of 200 from the dummy Ultra server on the receipt of a corresponding ADT^A01 HL7 message.

    Args:
        db (firestore.client): the database client used to access Firestore
        folder_path (pathlib.Path, optional): the folder to look in for Fhir docs. Defaults to WORK_FOLDER_PATH.

    Raises:
        DocumentSizeExceededError: raised if the size of the patient record will exceed the max record size in the database
        PatientExistsError: raised if the patient record already exists in the database
        Exception: raised if there is an error when attempting to construct an ADT^A01 HL7 message using the patient info 
        UltraNotHappyError: raised if the dummy Ultra server does not respond with 200

    Returns:
        list[PatientInfo] | None: a list of successfully uploaded patients. If none are uploaded, returns ``None``
    """
    patient_list = []

    for file in folder_path.glob("*.json"):
            try: 
                with open(file, "r") as f:
                    fhir_message = f.read()

                    # Parse patient information from file 
                    patient_info = parse_fhir_message(db=db, fhir_message=fhir_message)
                    
                    if not under_document_size_limit(db=db, patient_info=patient_info):
                        raise DocumentSizeExceededError()
                    
                    if patient_exists(db=db, patient_info=patient_info):
                        raise PatientExistsError()
                        
                    hl7 = create_adt_message(patient_info=patient_info, messageType="ADT_A01")
                    if not hl7:
                        raise Exception()
                    response = forward_to_ultra(hl7_message=hl7)
                    if response != 200:
                        raise UltraNotHappyError()

            except DocumentSizeExceededError:
                print("Document holding patient info will exceed Firestore size limit - aborting save to database.")
                pathlib.Path(FAILED_FOLDER_PATH).mkdir(exist_ok=True)
                pathlib.Path(file).rename(FAILED_FOLDER_PATH / file.name)
                
            except PatientExistsError:
                print("Patient already exists in the database - aborting save to database.")
                pathlib.Path(UPLOADED_FOLDER_PATH).mkdir(exist_ok=True)
                pathlib.Path(file).rename(FAILED_FOLDER_PATH / file.name)

            except UltraNotHappyError:
                print("Ultra did not successfully receive / process ADT^A01 - aborting save to database.")
                pathlib.Path(FAILED_FOLDER_PATH).mkdir(exist_ok=True)
                pathlib.Path(file).rename(FAILED_FOLDER_PATH / file.name)
                
            except Exception as e: 
                print('Failed to parse Fhir to PatientInfo object: %s', repr(e))
                pathlib.Path(FAILED_FOLDER_PATH).mkdir(exist_ok=True)
                pathlib.Path(file).rename(FAILED_FOLDER_PATH / file.name)
                 
            else:
                response = save_to_firestore(db=db, patient_info=patient_info)
                if response == 200:
                    patient_list.append(patient_info)
                    pathlib.Path(UPLOADED_FOLDER_PATH).mkdir(exist_ok=True)
                    pathlib.Path(file).rename(UPLOADED_FOLDER_PATH / file.name)
                else:
                    pathlib.Path(FAILED_FOLDER_PATH).mkdir(exist_ok=True)
                    pathlib.Path(file).rename(FAILED_FOLDER_PATH / file.name)
                    
    return patient_list


def generate_and_upload(db: firestore.client, num_of_patients:int=None, age_lower:int=None, age_upper:int=None, sex:str=None) -> list[PatientInfo] | None: 
    """Generates a number of new fhir documents, parses the relevant patient information 
    from them, and uploads this information to the database.

    Args:
        db (firestore.client): the database client used to access Firestore

    Returns:
        list[PatientInfo] | None: a list of successfully uploaded patients. If none are uploaded, returns ``None``
    """
    generate_fhir_docs(num_of_patients=num_of_patients, age_lower=age_lower, age_upper=age_upper, sex=sex)
    patients = upload_fhir_to_firestore(db=db)
    return patients


def retrieve_patients(db: firestore.client) -> list[PatientInfo] | None: 
    """Used to retrieve a number of patients from the database within a given age range.

    Args:
        db (firestore.client): the database client used to access Firestore

    Returns:
        list[PatientInfo] | None: a list of successfully retrieved patients. If none are retrieved, returns ``None``
    """
    try: 
        num_of_patients = int(input("Number of patients to retrieve: "))
        assert num_of_patients > 0
        lower = int(input("Minimum patient age: "))
        assert lower > 0
        upper = int(input("Maximum patient age: "))  
        assert lower < upper
    except AssertionError:
        print("\nInvalid input, returning to main menu.")
    except Exception: 
        print("\nUnrecognised input, returning to main menu.")
    else: 
        try: 
            patients = get_firestore_age_range(db=db, num_of_patients=num_of_patients, lower=lower, upper=upper, peter_pan=True)
            while type(patients) == int:
                random_number = random.randint(0,1)
                sex = "F" if random_number == 0 else "M"
                _ = generate_and_upload(db=db, num_of_patients=patients, age_lower=lower, age_upper=upper, sex=sex)
                patients = get_firestore_age_range(db=db, num_of_patients=num_of_patients, lower=lower, upper=upper, peter_pan=True)
                
        except Exception as e: 
            print("\nAn error was encountered during the retrieval of patients.", repr(e))
            print("Returning to main menu. ")
        else: 
            print(f"{len(patients)} patients successfully retrieved.")
            print("Selecting appropriate HL7 IDs...")
            try:
                for patient in patients:
                    patient:PatientInfo
                    prior_max_id = patient.max_hl7v2_id
                    patient = modify_for_age_range(db=db, patient_info=patient, lower=lower, upper=upper)
                    post_max_id = patient.max_hl7v2_id
                    
                    if prior_max_id != post_max_id:
                        print(f"No existing ID found for patient {patient.id} - generating new HL7v2 id...")
                        hl7 = create_adt_message(patient_info=patient, messageType="ADT_A01")
                        if not hl7:
                            raise Exception("Malformed HL7 message")
                        response = forward_to_ultra(hl7_message=hl7)
                        if response != 200:
                            raise UltraNotHappyError()
                        response = save_to_firestore(db=db, patient_info=patient, update_record=True)
                        if response != 200:
                            raise Exception("Unable to save info to the database")
                    
            except UltraNotHappyError as e:
                print("Ultra did not successfully receive / process ADT^A01 - aborting save to database and retrieval of patients.")
                return None
            
            except Exception as e:
                print(f"Failed to assign IDs - {repr(e)}")
                return None
            
            else:
                return patients


def process_import_folder(db: firestore.client) -> list[PatientInfo] | None:
    """Used to process all files in the 'import' folder. Each Fhir doc will be read and parsed, 
    and the patient record therein will be uploaded to the database, contingent on a response of 200
    from the dummy Ultra server once the corresponding ADT^A01 message is sent. Each HL7 message will be 
    read and parsed, forwarded to the dummy Ultra server, and then used to update patient records in the 
    database, provided the dummy Ultra server responds with 200.

    Args:
        db (firestore.client): the database client used to access Firestore

    Returns:
        list[PatientInfo] | None: all ``PatientInfo`` objects generated during parsing that were successfully received by the 
                                  Ultra server, and uploaded to the database. If all uploads fail, returns ``None``
    """
    patient_list = upload_fhir_to_firestore(db=db, folder_path=IMPORT_FOLDER_PATH)
    update_patients(db=db)
    return patient_list


def update_patients(db: firestore.client) -> None:
    """Used to read and parse the HL7 messages found in the 'import' folder, forward 
    them to the dummy Ultra server, and update patients in the database provided the Ultra 
    server responds with 200. 

    Args:
        db (firestore.client): the database client used to access Firestore

    Raises:
        UltraNotHappyError: raised if the dummy Ultra server does not respond with 200
    """
    for file in IMPORT_FOLDER_PATH.glob("*.hl7"):
        try:
            with open(file, "r") as f:
                hl7_message = f.read()

            # Parse patient information from file 
            hl7_parsed, patient_info = parse_HL7_message(db=db, msg=hl7_message)
            
            # Forward to Ultra 
            response = forward_to_ultra(hl7_message=hl7_parsed)
            if response != 200:
                raise UltraNotHappyError()
            else:
                pathlib.Path(SENT_HL7_PATH).mkdir(exist_ok=True)
                pathlib.Path(file).rename(SENT_HL7_PATH / file.name)
            
            # Update patient in Firestore database 
            if hl7_parsed.msh.msh_9.to_er7() == "ORM^O01":
                update_following_ORM_O01(db=db, patient_info=patient_info)
                    
            elif hl7_parsed.msh.msh_9.to_er7() == "ORU^R01":
                update_following_ORU_R01(db=db, patient_info=patient_info)
            else: 
                print("\nSupport for updates to the database only extends to ORM^O01 and ORU^R01 message types. ")
                pathlib.Path(FAILED_HL7_PATH).mkdir(exist_ok=True)
                pathlib.Path(file).rename(FAILED_HL7_PATH / file.name)
                    
        except UltraNotHappyError:
            print("Ultra did not successfully receive / process HL7 message - aborting save to database.")
            pathlib.Path(FAILED_HL7_PATH).mkdir(exist_ok=True)
            pathlib.Path(file).rename(FAILED_HL7_PATH / file.name)
            
        except Exception as e: 
            print(f"\nAn internal error was encountered when attempting to parse and upload the patient information: {repr(e)}")
            pathlib.Path(FAILED_HL7_PATH).mkdir(exist_ok=True)
            pathlib.Path(file).rename(FAILED_HL7_PATH / file.name)


def forward_to_ultra(hl7_message) -> int: 
    """Forwards an HL7 message to the dummy Ultra server via the TCP server. Reads the response 
    from both the TCP server and the dummy Ultra server, and returns an appropriate HTTP response code.

    Args:
        hl7_message (_type_): a ``hl7apy`` message object

    Raises:
        Exception: raised if no response is received from the TCP server
        Exception: raised if the response from the TCP server is not formatted correctly
        Exception: raised if no response is received from the dummy Ultra server
        Exception: raised if the response from the dummy Ultra server is not 200

    Returns:
        int: an appropriate HTTP response code based on the responses from the TCP and dummy Ultra servers
    """
    try:
        hl7_to_send = hl7_to_string(hl7=hl7_message)
        response = json.loads(send_hl7_message(hl7_message=hl7_to_send))
        
        if not response:
            raise Exception("No response from TCP server.")
        
        if not response['tcp_server_response']:
            raise Exception("A server-side error occurred.")
        
        print(f"Response from TCP server: {response['tcp_server_response']}")
        
        if not response['dummy_ultra_response']:
            raise Exception("No response from Ultra server.")
        print(f"Response from ULTRA server: {response['dummy_ultra_response']}")
    
        if response['dummy_ultra_response'] != "200":
            raise Exception("Bad response from Ultra server.")
            
    except Exception as e: 
        print(f"Exception occurred: {repr(e)}")
        return 400
    else: 
        return 200
