import os
import pathlib
import unittest 
from unittest.mock import patch 
from bespoke_functions import generate_fhir_docs, BASE_DIR, WORK_FOLDER_PATH, UPLOADED_FOLDER_PATH,\
    FAILED_FOLDER_PATH, upload_fhir_to_firestore, generate_and_upload, hl7_to_string, retrieve_patients, upload_from_file,\
        update_patient, forward_to_ultra
from poll_synthea.generators.utilities import PatientInfo, parse_HL7_message
from poll_synthea.main import initialize_firestore, create_orm_message, create_oru_message, HL7MessageProcessor

FIRESTORE_DB = initialize_firestore()
HL7PROCESSOR = HL7MessageProcessor(hl7_folder_path=BASE_DIR/"HL7gen", db=FIRESTORE_DB)

def clear_uploaded_patients():
    folder = pathlib.Path(UPLOADED_FOLDER_PATH)
    for item in folder.iterdir():
        item.unlink()


def clear_failed_patients():
    folder = pathlib.Path(FAILED_FOLDER_PATH)
    for item in folder.iterdir():
        item.unlink()


def clear_work_folder():
    folder = pathlib.Path(WORK_FOLDER_PATH)
    for item in folder.iterdir():
        item.unlink()


def clear_hl7_folder():
    folder = pathlib.Path(BASE_DIR / "HL7gen")
    for item in folder.iterdir():
        item.unlink() 


class Test(unittest.TestCase):
    
    
    def test_hl7_to_string(self):
        
        hl7_strings = [
            """MSH|^~\&|ULTRA|TEST|ULTRA|NUFFIELD|202409100000||ORM^O01|20240910005249913362|T|2.4|||AL|NE
PID|1||SYN0003G^^^PAS^MR||Zemlak964^Kevin729^None||2010-01-01|M|||538 Pawling Parkway^Room 677^Birmingham^^B12^GB|||||||069^040AU
PV1|1|O|550DL||||^ACON|^ANAESTHETICS CONS^^^^^^L|^ANAESTHETICS CONS^^^^^^^AUSHICPR
ORC|O|PL-14149ac6-7105-4e8d-92f5-31c325a16e6e|FL-0b41dd57-9236-4238-90fa-de1253cd9305
OBR|1|PL-14149ac6-7105-4e8d-92f5-31c325a16e6e|FL-0b41dd57-9236-4238-90fa-de1253cd9305|R-ANKLE^Ankle X-ray^L||202409060000|202409030000|||||||||WACON^TEST||||||||BI^UHC|||^^^202409060000^^E""",
            """MSH|^~\&|ULTRA|TEST|ULTRA|NUFFIELD|202409110000||ADT^A01|20240911194204257448|T|2.4|||AL|NE
EVN|A01|202409080000
PID|1||SYN0000O^^^PAS^MR||Cummerata161^Clement78^Nicky270||2014-01-01|M|||2623 Village Trail^Room 378^Upton^^WF9^GB|||||||611^690XZ
PV1|1|O|085JG||||^ACON|^ANAESTHETICS CONS^^^^^^L|^ANAESTHETICS CONS^^^^^^^AUSHICPR""",
            """MSH|^~\&|ULTRA|TEST|ULTRA|NUFFIELD|202409110000||ORU^R01|20240911200034776395|T|2.4|||AL|NE
PID|1||SYN0000O^^^PAS^MR||Cummerata161^Clement78^Nicky270||2014-01-01|M|||2623 Village Trail^Room 378^Upton^^WF9^GB|||||||040^384HT
PV1|1|O|700AM||||^ACON|^ANAESTHETICS CONS^^^^^^L|^ANAESTHETICS CONS^^^^^^^AUSHICPR
ORC|O|PL-301f7880-a8ef-41ab-8be6-be15ea46c996|FL-2e7e7f4d-ae3e-4050-a094-32a0a13b69ab
OBR|1|PL-301f7880-a8ef-41ab-8be6-be15ea46c996|FL-2e7e7f4d-ae3e-4050-a094-32a0a13b69ab|R-ANKLE^Ankle X-ray^L||202409050000|202409100000|||||||||WACON^TEST||||||||BI^UHC|||^^^202409080000^^E
OBX|1|TX|R-ANKLE^Ankle X-ray^L||Normal findings, no fracture detected||||||F"""
        ]
        
        for hl7_string in hl7_strings:
            with self.subTest(hl7_string=hl7_string):
                hl7_string = hl7_string.replace("\r", "\n")
                hl7_object, _ = parse_HL7_message(msg=hl7_string, db=FIRESTORE_DB)
                new_hl7_string = hl7_to_string(hl7_object)
                new_hl7_string = new_hl7_string.replace("\r", "\n")
                self.assertEqual(hl7_string, new_hl7_string)
    
    
    @patch('builtins.input')
    def test_generate_fhir_docs(self, mock_input):
        """Testing the ``generate_fhir_docs`` function from ``bespoke_functions.py``. Using two sets 
        of test cases - one valid, one invalid - with three tests per case. 

        Args:
            mock_input (unittest.mock.MagicMock): Used to substitute variables for user input. Generated as a result of the ``@patch`` decorator.
        """
        
        valid_test_cases = [
            (['3', '10', '80', 'M'], 3),
            (['3', '30', '30', 'F'], 3),
            (['3', '1', '99', 'M'], 3)
        ]
        
        for inputs, new_files in valid_test_cases:
            with self.subTest(inputs=inputs, new_files=new_files):
                mock_input.side_effect = inputs
        
                num_files_before = len([name for name in os.listdir(WORK_FOLDER_PATH)])
                
                generate_fhir_docs()
                
                num_files_after = len([name for name in os.listdir(WORK_FOLDER_PATH)])
                
                self.assertTrue(num_files_before - new_files <= num_files_after)
        
        invalid_test_cases = [
            ['0', '10', '80', 'M'],
            ['3', '30', '29', 'F'],
            ['3', '1', '99', 'H']
        ]
        
        for inputs in invalid_test_cases:
            with self.subTest(inputs=inputs):
                mock_input.side_effect = inputs
        
                num_files_before = len([name for name in os.listdir(WORK_FOLDER_PATH)])
                
                generate_fhir_docs()
                
                num_files_after = len([name for name in os.listdir(WORK_FOLDER_PATH)])
                
                self.assertTrue(num_files_before == num_files_after)
        
        
    @patch('builtins.input')
    def test_upload_to_firestore(self, mock_input):
        """Testing the ``upload_to_firestore`` function from ``bespoke_functions.py``. Using one 
        set of test cases, which holds three valid tests. Invalid tests are not required, as input is 
        only passed to the ``generate_fhir_docs`` function, which has been tested above. 

        Args:
            mock_input (unittest.mock.MagicMock): Used to substitute variables for user input. Generated as a result of the ``@patch`` decorator.
        """
        
        valid_test_cases = [
            ['5', '1', '99', 'M'],
            ['10', '1', '99', 'F'],
            ['15', '1', '99', 'M']
        ]
        
        for inputs in valid_test_cases:
            with self.subTest(inputs=inputs):
                
                clear_work_folder()
                clear_uploaded_patients()
                clear_failed_patients()
                # clear_hl7_folder()
                
                mock_input.side_effect = inputs
                
                generate_fhir_docs()
                
                new_files = len([name for name in os.listdir(WORK_FOLDER_PATH)])
                
                patient_list = upload_fhir_to_firestore(db=FIRESTORE_DB)
                
                work_folder_count = len([name for name in os.listdir(WORK_FOLDER_PATH)])
                uploaded_patients_count = len([name for name in os.listdir(UPLOADED_FOLDER_PATH)])
                failed_patients_count = len([name for name in os.listdir(FAILED_FOLDER_PATH)])
                # hl7_gen_count = len([name for name in os.listdir(BASE_DIR / "HL7gen")])
                
                self.assertEqual(work_folder_count, 0)
                self.assertEqual(uploaded_patients_count + failed_patients_count, new_files)
                # self.assertEqual(uploaded_patients_count, hl7_gen_count)
                if patient_list:
                    self.assertEqual(len(patient_list), uploaded_patients_count)
              
        clear_work_folder()
        clear_uploaded_patients()
        clear_failed_patients()
        # clear_hl7_folder()  
                
                
    @patch('builtins.input')
    def test_generate_and_upload(self, mock_input):
        """Testing the ``generate_and_upload`` function from ``bespoke_functions.py``. Using one 
        set of test cases, which holds three valid tests. Invalid tests are not required, as input is 
        only passed to the ``generate_fhir_docs`` function, which has been tested above. 

        Args:
            mock_input (unittest.mock.MagicMock): Used to substitute variables for user input. Generated as a result of the ``@patch`` decorator.
        """
        
        clear_work_folder()
        
        valid_test_cases = [
            (['5', '1', '99', 'M'], 5),
            (['10', '1', '99', 'F'], 10),
            (['15', '1', '99', 'M'], 15),
        ]
        
        for inputs, new_files in valid_test_cases:
            with self.subTest(inputs=inputs, new_files=new_files):
                
                clear_uploaded_patients()
                clear_failed_patients()
                # clear_hl7_folder()
                
                mock_input.side_effect = inputs
                
                patient_list = generate_and_upload(db=FIRESTORE_DB)
                
                work_folder_count = len([name for name in os.listdir(WORK_FOLDER_PATH)])
                uploaded_patients_count = len([name for name in os.listdir(UPLOADED_FOLDER_PATH)])
                failed_patients_count = len([name for name in os.listdir(FAILED_FOLDER_PATH)])
                # hl7_gen_count = len([name for name in os.listdir(BASE_DIR / "HL7gen")])
                
                self.assertEqual(work_folder_count, 0)

                # Accounting for additional generated documents in the case of deceased patients 
                self.assertTrue(uploaded_patients_count + failed_patients_count >= new_files)
                
                # self.assertEqual(uploaded_patients_count, hl7_gen_count)
                if patient_list:
                    self.assertEqual(len(patient_list), uploaded_patients_count)
                
        clear_uploaded_patients()
        clear_failed_patients()
        # clear_hl7_folder()  
        
    
    @patch('builtins.input')
    def test_retrieve_patients(self, mock_input):
        
        valid_test_cases = [
            (['5', '1', '99'], 5),
            (['10', '1', '99'], 10),
            (['15', '1', '99'], 15),
        ]
        
        for inputs, retrieved_patients in valid_test_cases:
            with self.subTest(inputs=inputs, retrieve_patients=retrieved_patients):
                
                mock_input.side_effect = inputs
                
                patient_list = retrieve_patients(db=FIRESTORE_DB)
                
                if patient_list:
                    self.assertEqual(len(patient_list), retrieved_patients)
                    for patient in patient_list:
                        self.assertTrue(type(patient) == PatientInfo)
                        
        invalid_test_cases = [
            ['5', '1', '-1'],
            ['0', '1', '99'],
            ['15', '1', ''],
            ['15', '1', 'f'],
            ['LM', '1', '99']
        ]
        
        for inputs in invalid_test_cases:
            with self.subTest(inputs=inputs):
                
                mock_input.side_effect = inputs
                
                patient_list = retrieve_patients(db=FIRESTORE_DB)
                
                self.assertIsNone(patient_list)
        

    @patch('builtins.input')
    def test_upload_from_file(self, mock_input):
        
        clear_work_folder()
        
        valid_test_cases = [
            ['3', '10', '80', 'M'],
            ['3', '30', '30', 'F'],
            ['3', '1', '99', 'M']
        ]
        
        for inputs in valid_test_cases:
            
            with self.subTest(inputs=inputs):
                mock_input.side_effect = inputs
                
                generate_fhir_docs()
                
                for file in WORK_FOLDER_PATH.glob("*.json"):
                    
                    uploaded_count = len([name for name in os.listdir(UPLOADED_FOLDER_PATH)])
                    
                    mock_input.side_effect = [str(WORK_FOLDER_PATH / file.name)]
                    
                    patient = upload_from_file(db=FIRESTORE_DB)
                    
                    new_uploaded_count = len([name for name in os.listdir(UPLOADED_FOLDER_PATH)])
                    
                    if patient:
                        self.assertTrue(type(patient) == PatientInfo)
                        self.assertTrue(uploaded_count + 1 == new_uploaded_count)
    
    
    @patch("builtins.input")
    def test_update_patient(self, mock_input):
        
        clear_hl7_folder()
        
        # Write more test cases - how to prove this function works? 
        request = ['1', '10', '80']
        
        mock_input.side_effect = request
        patient_list = retrieve_patients(db=FIRESTORE_DB)
        
        self.assertIsNotNone(patient_list)
        patient_info = patient_list[0]
        
        orm = create_orm_message(patient_info=patient_info, messageType="ORM_O01")
        HL7PROCESSOR.save_hl7_message_to_file(hl7_message=orm, patient_id=patient_info.id)
        
        oru = create_oru_message(patient_info=patient_info, messageType="ORU_R01")
        HL7PROCESSOR.save_hl7_message_to_file(hl7_message=oru, patient_id=patient_info.id)
        
        for file in (BASE_DIR / "HL7gen").glob("*.json"):
            mock_input.side_effect = [str(BASE_DIR / "HL7gen" / file.name)]
            
            update_patient(db=FIRESTORE_DB)
    
    # How to test server function? 
    # - function tests the reception of messages anyway...?
    @patch('builtins.input')
    def test_forward_to_ultra(self, mock_input):
        
        requests = [
            ['5', '1', '99'],
            ['10', '1', '99'],
            ['15', '1', '99']
        ]
        
        for inputs in requests:
            with self.subTest(inputs=inputs):
                
                mock_input.side_effect = inputs
                patient_list = retrieve_patients(db=FIRESTORE_DB)
                
                for patient in patient_list:
                    hl7_object = create_orm_message(patient_info=patient, messageType="ORM_O01")
                    
                    result = forward_to_ultra(hl7_message=hl7_object)
                    
                    self.assertEqual(200, result)

if __name__ == '__main__':
    unittest.main()
    