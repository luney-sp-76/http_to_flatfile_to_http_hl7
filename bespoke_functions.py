import json
import pathlib
from firebase_admin import firestore
from poll_synthea.generators.utilities import PatientInfo, call_for_patients, \
    parse_fhir_message, save_to_firestore, parse_HL7_message, update_following_ORM_O01, \
    update_following_ORU_R01, get_firestore_age_range, under_document_size_limit
from poll_synthea.main import initialize_firestore, create_adt_message
from tcp_client import send_hl7_message

# Paths 
BASE_DIR = pathlib.Path.cwd()
WORK_FOLDER_PATH = BASE_DIR / "Work"
UPLOADED_FOLDER_PATH = BASE_DIR / "UploadedPatients"
FAILED_FOLDER_PATH = BASE_DIR / "FailedPatients"


class UltraNotHappyError(Exception):
    pass

class DocumentSizeExceededError(Exception):
    pass


def hl7_to_string(hl7) -> str:
    converted_hl7 = ""
    for child in hl7.children: 
        converted_hl7 = converted_hl7 + f"{child.to_er7()}\n"
    return converted_hl7[:-1]


def generate_fhir_docs() -> None: 
    '''Generates ``x`` fhir documents and places them in the ``Work`` folder. 
    '''
    try: 
        num_of_patients = int(input("Number of patients to generate: "))
        if num_of_patients < 1:
            raise Exception
        age_lower = int(input("Minimum patient age: "))
        if age_lower < 0:
            raise Exception
        age_upper = int(input("Maximum patient age: "))
        if age_upper < age_lower:
            raise Exception
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


def upload_fhir_to_firestore(db: firestore.client) -> list[PatientInfo] | None: 
    patient_list = []

    for file in WORK_FOLDER_PATH.glob("*.json"):
            try: 
                with open(file, "r") as f:
                    fhir_message = f.read()

                    # Parse patient information from file 
                    patient_info = parse_fhir_message(db=db, fhir_message=fhir_message)
                    
                    if not under_document_size_limit(db=db, patient_info=patient_info):
                        raise DocumentSizeExceededError()
                        
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


def generate_and_upload(db: firestore.client) -> list[PatientInfo] | None: 
    """ Generates a number of new fhir documents, parses the relevant patient information 
    from them, and uploads this information to Firestore 

    Args: 
    - db: ``firestore.client``, the client used to communicate with Firestore 

    Returns: 
    - `None`
    """
    generate_fhir_docs()
    patients = upload_fhir_to_firestore(db=db)
    return patients


def retrieve_patients(db: firestore.client) -> list[PatientInfo] | None: 

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
        except Exception as e: 
            print("\nAn error was encountered during the retrieval of patients.", repr(e))
            print("Returning to main menu. ")
        else: 
            print(f"{len(patients)} patients successfully retrieved.")
            return patients


def upload_from_file(db: firestore.client) -> PatientInfo | None: 
    path_to_fhir = input("Local path to the fhir json file: ")
    
    try:
        fhir_file = pathlib.Path(path_to_fhir)
        assert (fhir_file.is_file() and (fhir_file.suffix == ".json"))
        with open(path_to_fhir, "r") as f:
            fhir_message = f.read()

            # Parse patient information from file 
            patient_info = parse_fhir_message(db=db, fhir_message=fhir_message)
            
            if not under_document_size_limit(db=db, patient_info=patient_info):
                        raise DocumentSizeExceededError()
                    
            hl7 = create_adt_message(patient_info=patient_info, messageType="ADT_A01")
            if not hl7:
                raise Exception()
            
            response = forward_to_ultra(hl7_message=hl7)
            if response != 200:
                raise UltraNotHappyError()
            
            response = save_to_firestore(db=db, patient_info=patient_info)
            
    except DocumentSizeExceededError:
                print("Document holding patient info will exceed Firestore size limit - aborting save to database.")
                pathlib.Path(FAILED_FOLDER_PATH).mkdir(exist_ok=True)
                pathlib.Path(fhir_file).rename(FAILED_FOLDER_PATH / fhir_file.name)
            
    except UltraNotHappyError:
                print("Ultra did not successfully receive / process ADT^A01 - aborting save to database.")
                pathlib.Path(FAILED_FOLDER_PATH).mkdir(exist_ok=True)
                pathlib.Path(fhir_file).rename(FAILED_FOLDER_PATH / fhir_file.name)
                
    except AssertionError as e:
        print(f"\nAn internal error was encountered: {repr(e)}")
        print("Returning to main menu. ")
        
    except Exception as e: 
        print(f"\nAn internal error was encountered when attempting to parse and upload the patient information: {repr(e)}")
        if fhir_file:
            pathlib.Path(FAILED_FOLDER_PATH).mkdir(exist_ok=True)
            pathlib.Path(fhir_file).rename(FAILED_FOLDER_PATH / fhir_file.name)
        
    else:
        if response == 200:
            pathlib.Path(UPLOADED_FOLDER_PATH).mkdir(exist_ok=True)
            pathlib.Path(fhir_file).rename(UPLOADED_FOLDER_PATH / fhir_file.name)
            return patient_info
        else:
            pathlib.Path(FAILED_FOLDER_PATH).mkdir(exist_ok=True)
            pathlib.Path(fhir_file).rename(FAILED_FOLDER_PATH / fhir_file.name)
            return None 


def update_patient(db: firestore.client) -> None:
    path_to_hl7 = input("Local path to the HL7 text file: ")
    
    try:
        hl7_file = pathlib.Path(path_to_hl7)
        assert (hl7_file.is_file() and (hl7_file.suffix == ".hl7"))
        with open(path_to_hl7, "r") as f:
            hl7_message = f.read()

            # Parse patient information from file 
            hl7_parsed, patient_info = parse_HL7_message(db=db, msg=hl7_message)
            
            # Forward to Ultra 
            response = forward_to_ultra(hl7_message=hl7_parsed)
            if response != 200:
                raise UltraNotHappyError()
            
            # Update patient in Firestore database 
            if hl7_parsed.msh.msh_9.to_er7() == "ORM^O01":
                update_following_ORM_O01(db=db, patient_info=patient_info)
            elif hl7_parsed.msh.msh_9.to_er7() == "ORU^R01":
                update_following_ORU_R01(db=db, patient_info=patient_info)
            else: 
                print("\nSupport for updates only extends to ORM^O01 and ORU^R01 message types. \nReturning to main menu.")
                
    except UltraNotHappyError:
                print("Ultra did not successfully receive / process HL7 message - aborting save to database.")
           
    except AssertionError as e:
        print(f"\nInvalid local path - file must exist and have the extension '.hl7'")
        print("Returning to main menu. ")
        
    except Exception as e: 
        print(f"\nAn internal error was encountered when attempting to parse and upload the patient information: {repr(e)}")


def forward_to_ultra(hl7_message) -> int: 
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



if __name__ == '__main__':
    db = initialize_firestore()
#     message = """MSH|^~\&|ULTRA|TEST|ULTRA|NUFFIELD|202408050000||ORM^O01|20240805143850140998|T|2.4|||AL|NE
# PID|1||SYN0004S^^^^PAS^MR||Stamm704^Cornell131^Leo278||19940101|M|||08733 Gina Crossing^Suite 71^London^^WC2H^GB|||||||149^047GW
# PV1|1|O|353TD||||^ACON|^ANAESTHETICS CONS^^^^^^L|^ANAESTHETICS CONS^^^^^^^AUSHICPR
# ORC|O|934ZY|1^^70980^408
# OBR|1|934ZY|1^^70980^408|R-ANKLE^Ankle X-ray^L||202407310000|202408010000|||||||||WACON^TEST||||||||BI^UHC|||^^^202407290000^^E"""

#     message = """MSH|^~\&|EHR|HOSPITAL|LAB|HOSPITAL|20240808080000||ORM^O01|20240808120000|P|2.4
# PID|1||DSTRANGE^^^^PAS^MR||Strange^Stephen^V^^Dr.||19751101|M|||177A Bleecker St^^New York^NY^10012||(212)555-1234|||||987-65-4321
# ORC|NW|123456^LAB|654321^LAB||CM||||20240808080000|789012^Palmer^Christine^J^^Dr.|||||177A Bleecker St^^New York^NY^10012||(212)555-1234
# OBR|1||123456^LAB|123-4^Liver Function Test^L||20240808080000|||||||||789012^Palmer^Christine^J^^Dr.|||20240808080000|||||||NW
# """

#     _, patient = parse_HL7_message(msg=message, db=db)

#     update_following_ORM_O01(db=db, patient_info=patient)

#     time.sleep(5)

#     message = """MSH|^~\&|LAB|HOSPITAL|EHR|HOSPITAL|20240808140000||ORU^R01|20240808143000|P|2.4
# PID|1||DSTRANGE^^^^PAS^MR||Strange^Stephen^V^^Dr.||19751101|M|||177A Bleecker St^^New York^NY^10012||(212)555-1234|||||987-65-4321
# ORC|RE|123456^LAB|654321^LAB||CM||||20240808080000|789012^Palmer^Christine^J^^Dr.|||||177A Bleecker St^^New York^NY^10012||(212)555-1234
# OBR|1||123456^LAB|123-4^Liver Function Test^L||20240808080000|20240808120000||||||||789012^Palmer^Christine^J^^Dr.|||20240808120000|||||||F
# OBX|1|NM|12256-3^Alanine Aminotransferase (ALT)^LN||45|U/L|10-40|H|||F||20240808120000
# OBX|2|NM|12257-1^Aspartate Aminotransferase (AST)^LN||30|U/L|10-40|N|||F||20240808120000
# OBX|3|NM|12258-9^Alkaline Phosphatase (ALP)^LN||98|U/L|44-147|N|||F||20240808120000
# OBX|4|NM|12259-7^Bilirubin^LN||1.2|mg/dL|0.3-1.0|H|||F||20240808120000
# """

#     _, patient = parse_HL7_message(msg=message, db=db)

#     update_following_ORU_R01(db=db, patient_info=patient)

    