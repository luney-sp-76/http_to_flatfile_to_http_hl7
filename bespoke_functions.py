import pathlib
from firebase_admin import firestore
from poll_synthea.generators.utilities import PatientInfo, call_for_patients, \
    parse_fhir_message, save_to_firestore, parse_HL7_message, increment_id, update_following_ORM_O01, \
    update_following_ORU_R01
from poll_synthea.main import initialize_firestore, create_orm_message
import time

BASE_DIR = pathlib.Path.cwd()
work_folder_path = BASE_DIR / "Work"


def generate_fhir_docs(num_of_docs, age_lower:int=10, age_upper:int=80, sex:str="M") -> None: 
    '''Generates ``x`` fhir documents and places them in the ``Work`` folder. 

    Args:
    - num_of_docs: ``int``, the number of fhir documents to create 
    - age_lower: ``int`` = 10, the lower age limit
    - age_upper: ``int`` = 80, the upper age limit
    - sex: ``str`` = M, male

    '''
    info = {
        "number_of_patients": num_of_docs,
        "age_from": age_lower, 
        "age_to": age_upper, 
        "sex": sex
    }

    # Generate patients using poll_synthea
    call_for_patients(info=info)


def generate_patient_objects(db: firestore.client, num_of_patients: int, age_lower: int=10, age_upper: int=80, sex:str="M") -> list[PatientInfo]:
    '''Generates ``x`` fhir documents and returns a list of patient info objects. 

    Args: 
    - db: ``firestore.client``, the initialised firestore client 
    - num_of_patients: ``int``, the number of patients to generate 
    - age_lower: ``int`` = 10, the lower age limit
    - age_upper: ``int`` = 80, the upper age limit
    - sex: ``str`` = M, male

    Returns: 
    - ``list[PatientInfo]``, a list of ``PatientInfo`` objects parsed from fhir documents. 
    '''

    info = {
        "number_of_patients": num_of_patients,
        "age_from": age_lower, 
        "age_to": age_upper, 
        "sex": sex
    }

    # Generate patients using poll_synthea
    call_for_patients(info=info)

    patient_list = []

    for file in work_folder_path.glob("*.json"):
            try: 
                with open(file, "r") as f:
                    fhir_message = f.read()

                    # Parse patient information from file 
                    patient_info = parse_fhir_message(db=db, fhir_message=fhir_message)

                    patient_list.append(patient_info)

            except Exception as e: 
                 print('Failed to parse Fhir to PatientInfo object: %s', repr(e))

    return patient_list[:num_of_patients]



if __name__ == '__main__':
    db = initialize_firestore()
#     message = """MSH|^~\&|ULTRA|TEST|ULTRA|NUFFIELD|202408050000||ORM^O01|20240805143850140998|T|2.4|||AL|NE
# PID|1||SYN0004S^^^^PAS^MR||Stamm704^Cornell131^Leo278||19940101|M|||08733 Gina Crossing^Suite 71^London^^WC2H^GB|||||||149^047GW
# PV1|1|O|353TD||||^ACON|^ANAESTHETICS CONS^^^^^^L|^ANAESTHETICS CONS^^^^^^^AUSHICPR
# ORC|O|934ZY|1^^70980^408
# OBR|1|934ZY|1^^70980^408|R-ANKLE^Ankle X-ray^L||202407310000|202408010000|||||||||WACON^TEST||||||||BI^UHC|||^^^202407290000^^E"""

    message = """MSH|^~\&|EHR|HOSPITAL|LAB|HOSPITAL|20240808080000||ORM^O01|20240808120000|P|2.4
PID|1||DSTRANGE^^^^PAS^MR||Strange^Stephen^V^^Dr.||19751101|M|||177A Bleecker St^^New York^NY^10012||(212)555-1234|||||987-65-4321
ORC|NW|123456^LAB|654321^LAB||CM||||20240808080000|789012^Palmer^Christine^J^^Dr.|||||177A Bleecker St^^New York^NY^10012||(212)555-1234
OBR|1||123456^LAB|123-4^Liver Function Test^L||20240808080000|||||||||789012^Palmer^Christine^J^^Dr.|||20240808080000|||||||NW
"""

    _, patient = parse_HL7_message(msg=message, db=db)

    update_following_ORM_O01(db=db, patient_info=patient)

    time.sleep(5)

    message = """MSH|^~\&|LAB|HOSPITAL|EHR|HOSPITAL|20240808140000||ORU^R01|20240808143000|P|2.4
PID|1||DSTRANGE^^^^PAS^MR||Strange^Stephen^V^^Dr.||19751101|M|||177A Bleecker St^^New York^NY^10012||(212)555-1234|||||987-65-4321
ORC|RE|123456^LAB|654321^LAB||CM||||20240808080000|789012^Palmer^Christine^J^^Dr.|||||177A Bleecker St^^New York^NY^10012||(212)555-1234
OBR|1||123456^LAB|123-4^Liver Function Test^L||20240808080000|20240808120000||||||||789012^Palmer^Christine^J^^Dr.|||20240808120000|||||||F
OBX|1|NM|12256-3^Alanine Aminotransferase (ALT)^LN||45|U/L|10-40|H|||F||20240808120000
OBX|2|NM|12257-1^Aspartate Aminotransferase (AST)^LN||30|U/L|10-40|N|||F||20240808120000
OBX|3|NM|12258-9^Alkaline Phosphatase (ALP)^LN||98|U/L|44-147|N|||F||20240808120000
OBX|4|NM|12259-7^Bilirubin^LN||1.2|mg/dL|0.3-1.0|H|||F||20240808120000
"""

    _, patient = parse_HL7_message(msg=message, db=db)

    update_following_ORU_R01(db=db, patient_info=patient)

    