# User Manual for `user_interface.py`

## Introduction

This manual provides instructions for running and using the `user_interface.py` program. The program interacts with three server-side applications and an online [Firestore](https://firebase.google.com/docs/firestore) database, as well as providing a command-line interface for user input and interaction.

## Prerequisites

Before running the main program (`user_interface.py`), the following server programs must be executed:

- `server.py`
- `tcp_server.py`
- `dummy_ultra.py`

These programs should be running concurrently to ensure that `user_interface.py` operates correctly. 

### Steps to Run Prerequisite Programs

1. **Open a terminal window.**
2. Navigate to the directory where the programs are located.
3. Run each of the following commands in separate terminal windows:
   
    ```bash
    python server.py
    ```

    ```bash 
    python tcp_server.py
    ```

    ```bash 
    python dummy_ultra.py
    ```

Ensure that these server programs are running before proceeding to the next step.

## Running the Main Program
Once the servers are running, follow these steps to start the main program:

1. Open a new terminal window.
2. Navigate to the directory where the user_interface.py program is located.
3. Run the main program using the following command:

    ```bash
    python user_interface.py
    ```

<a id="main-menu"></a>
### Main menu
Upon running the user_interface.py program, the system will perform the following checks:

- ``HTTP server status check``: checks that the HTTP server is running. 
- ``TCP server status check``: checks that the TCP server is running, as it will be used to receive requests to transmit HL7 messages to the dummy Ultra server.
- ``Dummy Ultra server status check``: checks that the dummy Ultra server is running, as it will be receiving HL7 messages forwarded by the TCP server, simulating an instance of [Ultra](https://cirdan.com/laboratory-solutions/ultra/). 

If any of these checks fail, the user is notified of the failure, along with the hostname and port number used in the check. 

Once all checks have been carried out, the program presents the user with a command-line interface (CLI) with nine options - to select an option, simply enter the number into the terminal when prompted, and press enter.

The nine options available to the user are detailed below: 

<a id="opt1"></a>
#### 1. Generate fhir docs and store in the 'work' folder

If [option 1](#opt1) is selected, the user is asked to provide the following information: 
- number of patients (fhir documents) to generate
- a lower age limit for the generated patients
- an upper age limit for the generated patients 
- the sex the patients should belong to (M/F)

If this information is successfully provided, the program will then proceed to generate the fhir documents, and store them in the 'Work' folder, which can be found in the base directory. If the folder does not exist prior to the selection of this option, it will be created. If there is an issue with the provided information, the user is provided with an error message, and returned to the [main menu](#main-menu). 

**Note**: if a fhir document contains a record of a patient who is now deceased, the fhir document generator will automatically create an additional patient record, one which contains the medical information of a currently living patient. In this case, the user will end up with more than the requested number of patients in the 'Work' folder. 

<a id="opt2"></a>
#### 2. Upload all patients in the 'work' folder to the database

If [option 2](#opt2) is selected, the program will look for fhir documents in the 'Work' folder. The following steps are carried out for each document: 

- The document is read, and relevant patient information is parsed from their record.
- The size of the resultant object is calculated to ensure upload to the Firestore database is viable at a later point.
- If the size of the PatientInfo obejct is acceptable, an ADT^A01 HL7 message is generated and sent to the dummy Ultra server via the TCP server.
- The TCP server returns an HL7 ACK message, along with the status code returned by the dummy Ultra server.
- Provided the HL7 message is successfully received by the dummy Ultra server, the patient information is then uploaded to the Firestore database.
- Following a successful upload to the Firestore database, the original fhir document will be moved to the 'UploadedPatients' folder within the base directory. 

As mentioned above, patient records which are successfully receieved and acknowledged by the dummy Ultra, and then uploaded to the Firestore database, are moved to the 'UploadedPatients' folder within the base directory. If the folder does not exist prior to the successful processing of patient information, it will be created. 

There are several possible points of failure within this process: 
- The generated fhir document contains too much patient information to upload to the Firestore database - in this case, the transmission to the dummy Ultra server, along with the upload to the Firestore database, will be aborted. 
- The generated ADT^A01 HL7 message is not received or acknolwedged successfully by the dummy Ultra server - in this case, the user is notified of the exception, and upload of the patient record to the Firestore dabatase is aborted. This design decision has been made in an effort to move towards the atomicity of transactions, as described in the [ACID properties](https://www.databricks.com/glossary/acid-transactions#:~:text=ACID%20is%20an%20acronym%20that,operations%20are%20called%20transactional%20systems.).
    - Further work should be done to ensure the atomicity of transactions, as currently there are no steps taken in the case where patient information reaches Ultra, but fails to be uploaded to the Firestore database.

If a patient record is not successfully received or acknowledged by the dummy Ultra server, or fails to be uploaded to the Firestore database, the fhir document will instead be moved to a different folder, 'FailedPatients', also found in the base directory. Much like the previously discussed folders, if it does not exist prior to its requirement, it will be created. 

<a id="opt3"></a>
#### 3. Generate new patients and upload to database

If [option 3](#opt3) is selected, the processes discussed above (options 1 & 2) will be streamlined into a single operation. The user is asked to provide the following information: 

- number of patients (fhir documents) to generate
- a lower age limit for the generated patients
- an upper age limit for the generated patients 
- the sex the patients should belong to (M/F)

The program will then generate the patient records and store them in the 'Work' folder, found in the base directory. Each record in the 'Work' folder is then read and parsed, its size calculated, its content transmitted to the dummy Ultra server, and the patient information uploaded to the Firestore database.

Each process carried out as a result of selecting this option is contingent on the success of the previous operation, as detailed in [option 1](#opt1) and [option 2](#opt2). 

<a id="opt4"></a>
#### 4. Extract and upload patient information from a specific Fhir file (.json)

If [option 4](#opt4) is selected, the user has the ability to select a specific patient record to send to both Ultra and the Firestore database - in order to provide the program with access to this record, the path to this file (relative to the base directory) must be provided. 

An alternative to using this option is to simply place the target patient record in the 'Work' folder, and then to select [option 2](#opt2). 

**Note**: the patient record provided must be a 'fhir' document with the json extension ``.json``. 

<a id="opt5"></a>
#### 5. Update a patient in the database with a specific HL7 message file (.hl7)

If [option 5](#opt5) is selected, the user has the ability to update a patient record in both the dummy Ultra and the Firestore database with a specific HL7 message. Similarly to the [previous option](#opt4), the path to this file (relative to the base directory) must be provided in order to allow the program to access the message. 

Example use-case:
- A patient record is received by the dummy Ultra server, and uploaded to the Firestore database. 
- Option 5 is then selected, and the path to an HL7 message is provided. 
    - The message (ORM^O01) details an observation request for patient x.
- The message is parsed, sent to the dummy Ultra server, and following a successful transmission, used to update the patient information in the Firestore database. 
- The patient record found in the Firestore database would now reflect the reception of the observation request 

**Note**: the HL7 message provided must be a text-based file with the extension ``.hl7``.

**Note**: generic HL7 messages of types ADT^A01, ORM^O01 and ORU^R01 can be generated following the upload or retrieval of patient records to / from the Firestore database - more information on this can be found in the [HL7 message sub-menu section](#hl7sub). 

<a id="opt6"></a>
#### 6. Retrieve patients from the database within a given age range

If [option 6](#opt6) is selected, the user has the ability to retrieve patient records from the database within a specific age range, for the purposes of generating several generic HL7 messages at once. 

The user is asked to provide the following information: 

- number of patient documents to retrieve from the Firestore database
- a lower age limit for the retrieved patients
- an upper age limit for the retrieved patients


If this information is successfully provided, the program will then proceed to retrieve the patient documents, and store them in memory. 
The user will then have the ability to generate one of the following HL7 messages for each of the retrieved patients: 
- ``ADT^A01``
- ``ORM^O01``
- ``ORU^R01``

Further detail regarding the ability to generate generic HL7 messages, as well as where these messages are stored, is provided in the [HL7 message sub-menu section](#hl7sub).

If there is an issue with the provided information, the user is provided with an error message, and returned to the [main menu](#main-menu).

<a id="opt7"></a>
#### 7. Clear the 'Work' folder, removing all fhir patient records

If [option 7](#opt7) is selected, the program will prepare to delete the contents of the 'Work' folder. Prior to the deletion of any patient records found in the 'Work' folder, the user is prompted to enter a phrase in the terminal, in an effort to confirm that the selection of this option is an intentional choice. 

Following the successful entering of the phrase, the program will then delete all files within the 'Work' folder, and return the user to the [main menu](#main-menu). If the phrase is entered incorrectly, no action is taken to remove the contents of the 'Work' folder, and the user is returned to the [main menu](#main-menu). 

<a id="opt8"></a>
#### 8. Clear the 'HL7gen' folder, removing all hl7 messages

If [option 8](#opt8) is selected, the program will prepare to delete the contents of the 'HL7gen' folder. Prior to the deletion of any HL7 messages found in the 'HL7gen' folder, the user is prompted to enter a phrase in the terminal, in an effort to confirm that the selection of this option is an intentional choice. 

Following the successful entering of the phrase, the program will then delete all files within the 'HL7gen' folder, and return the user to the [main menu](#main-menu). If the phrase is entered incorrectly, no action is taken to remove the contents of the 'HL7gen' folder, and the user is returned to the [main menu](#main-menu). 

**Note**: further information regarding the 'HL7gen' folder can be found in the [HL7 message sub-menu section](#hl7sub). 

<a id="opt9"></a>
#### 9. Exit

If [option 9](#opt9) is selected, the execution of the program will cease. From this point, the user may close the terminal without worries of unexpected behaviour. 



<a id="hl7sub"></a>
### HL7 message sub-menu

Upon the successful upload/retrieval of patient records to/from the Firestore database, the user will have the option to generate generic HL7 messages using each patient's information immediately afterwards. Generated messages are stored in the 'HL7gen' folder, located in the base directory. If this folder does not exist prior to generation of messages, it will be created automatically as required. 

These options are presented in a sub-menu, and are numbered 1-4, as detailed below: 

<a id="sub-opt1"></a>
#### 1: Generate ADT^A01 message(s)

An [A01 event](https://hl7-definition.caristix.com/v2/HL7v2.3/TriggerEvents/ADT_A01) is intended to be used for "Admitted" patients only. An A01 event is sent as a result of a patient undergoing the admission process which assigns the patient to a bed. It signals the beginning of a patient’s stay in a healthcare facility. Normally, this information is entered in the primary Patient Administration system and broadcast to the nursing units and ancillary systems. It includes short stay and "John Doe" (e.g. patient name is unknown) admissions.

If the user selects [option 1](#sub-opt1), a generic ADT^A01 message will be generated - see the example below: 

```hl7
MSH|^~\&|ULTRA|TEST|ULTRA|NUFFIELD|202409110000||ADT^A01|20240911194204257448|T|2.4|||AL|NE
EVN|A01|202409080000
PID|1||SYN0000O^^^PAS^MR||Cummerata161^Clement78^Nicky270||2014-01-01|M|||2623 Village Trail^Room 378^Upton^^WF9^GB|||||||611^690XZ
PV1|1|O|085JG||||^ACON|^ANAESTHETICS CONS^^^^^^L|^ANAESTHETICS CONS^^^^^^^AUSHICPR
```

Once generated, the message will be stored in the 'HL7gen' folder in the base directory; the file name given as the current date time, followed by the ID of the patient targeted by the HL7 message. 

**Note**: in the scope of this project, ADT^A01 messages are primarly used to notify Ultra of a new patient. This is the message type that is sent to the dummy Ultra server prior to the upload of new patient records to the Firestore database; patient records can be uploaded using [option 2](#opt2), [option 3](#opt3), or [option 4](#opt4) in the [main menu](#main-menu).  

<a id="sub-opt2"></a>
#### 2: Generate ORM^O01 message(s)

The [HL7 ORM-O01 message](https://rhapsody.health/resources/hl7-orm-message/) functions as a general order message that is used to transmit information about an order. There is only one type of ORM message – the ORM-O01 message. Trigger events for the ORM-O01 message involve changes to an order such as new orders, cancellations, information updates, discontinuation, etc. ORM messages are among the most widely used message types in the HL7 standard.

If the user selects [option 2](#sub-opt2), a generic ORM^O01 message will be generated - see the example below: 

```hl7
MSH|^~\&|ULTRA|TEST|ULTRA|NUFFIELD|202409100000||ORM^O01|20240910005249015592|T|2.4|||AL|NE
PID|1||SYN0000O^^^PAS^MR||Cummerata161^Clement78^Nicky270||2014-01-01|M|||2623 Village Trail^Room 378^Upton^^WF9^GB|||||||565^778KB
PV1|1|O|526DY||||^ACON|^ANAESTHETICS CONS^^^^^^L|^ANAESTHETICS CONS^^^^^^^AUSHICPR
ORC|O|PL-962ba933-1f5e-4573-9356-c54db2299ab5|FL-cd6f4f8d-bef3-404e-8925-aa0225b9fbb5
OBR|1|PL-962ba933-1f5e-4573-9356-c54db2299ab5|FL-cd6f4f8d-bef3-404e-8925-aa0225b9fbb5|R-ANKLE^Ankle X-ray^L||202409060000|202409030000|||||||||WACON^TEST||||||||BI^UHC|||^^^202409070000^^E
```

Once generated, the message will be stored in the 'HL7gen' folder in the base directory; the file name given as the current date time, followed by the ID of the patient targeted by the HL7 message. 

**Note**: currently, generic ORM^O01 messages will always request an ankle x-ray observation. 

<a id="sub-opt3"></a>
#### 3: Generate ORU^R01 message(s)

The [HL7 Observation Result (ORU) R01 message](https://rhapsody.health/resources/hl7-oru-message/) transmits observations and results from the producing system/filler (i.e. LIS, EKG system) to the ordering system/placer (i.e. HIS, physician office application). It may also be used to transmit result data from the producing system to a medical record archival system, or to another system not part of the original order process. ORU messages are also sometimes used to register or link to clinical trials, or for medical reporting purposes for drugs and devices.

If the user selects [option 3](#sub-opt3), a generic ORU^R01 message will be generated - see the example below: 

```hl7
MSH|^~\&|ULTRA|TEST|ULTRA|NUFFIELD|202409110000||ORU^R01|20240911200034776395|T|2.4|||AL|NE
PID|1||SYN0000O^^^PAS^MR||Cummerata161^Clement78^Nicky270||2014-01-01|M|||2623 Village Trail^Room 378^Upton^^WF9^GB|||||||040^384HT
PV1|1|O|700AM||||^ACON|^ANAESTHETICS CONS^^^^^^L|^ANAESTHETICS CONS^^^^^^^AUSHICPR
ORC|O|PL-301f7880-a8ef-41ab-8be6-be15ea46c996|FL-2e7e7f4d-ae3e-4050-a094-32a0a13b69ab
OBR|1|PL-301f7880-a8ef-41ab-8be6-be15ea46c996|FL-2e7e7f4d-ae3e-4050-a094-32a0a13b69ab|R-ANKLE^Ankle X-ray^L||202409050000|202409100000|||||||||WACON^TEST||||||||BI^UHC|||^^^202409080000^^E
OBX|1|TX|R-ANKLE^Ankle X-ray^L||Normal findings, no fracture detected||||||F
```

Once generated, the message will be stored in the 'HL7gen' folder in the base directory; the file name given as the current date time, followed by the ID of the patient targeted by the HL7 message. 

**Note**: currently, generic ORU^R01 messages will always provide observation results following an ankle x-ray observation, and state that there was no fracture detected. 

**Note**: currently, there is no requirement that ORU^R01 messages must match an observation request previously received. 

<a id="sub-opt4"></a>
#### 4: No further action

If the user selects [option 4](#sub-opt4), no further action will be taken at this point, and they will be returned to the [main menu](#main-menu). 

**Note**: once the user is returned to the [main menu](#main-menu), the patients that were generated or retrieved will be cleared from memory, and no further action may be taken using these patients' information to generate HL7 messages at this point. If the user wishes to generate more HL7 messages, they must either generate and upload more patient records, or retrieve existing patient records from the Firestore database. 
