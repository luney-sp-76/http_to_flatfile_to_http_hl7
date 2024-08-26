import socket
import time
from bespoke_functions import generate_and_upload, retrieve_patients, message_menu
from poll_synthea.main import initialize_firestore

# Server details 
SERVER_HOST = 'localhost'
SERVER_PORT = 8080
TCP_SERVER_HOST = 'localhost'
TCP_SERVER_PORT = 8081

# Global firestore client
FIRESTORE_DB = initialize_firestore()

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


def check_server_status() -> None:
    """ Used to notify the user of potential issues communicating with servers. 
    """
    print("Checking server status...")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((SERVER_HOST, SERVER_PORT))
    except socket.error:
        print(f"WARNING: UNABLE TO CONNECT TO SERVER USING HOST {SERVER_HOST} AND PORT {SERVER_PORT}.")
        time.sleep(3)
    else: 
        sock.close()
        print("Server is listening.")

    print("Checking tcp server status...")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((TCP_SERVER_HOST, TCP_SERVER_PORT))
    except socket.error:
        print(f"WARNING: UNABLE TO CONNECT TO SERVER USING HOST {TCP_SERVER_HOST} AND PORT {TCP_SERVER_PORT}.")
        time.sleep(3)
    else: 
        sock.close()
        print("TCP server is listening.")


def menu() -> None:
    """ Displays a menu to the user, enumerating their options. 
    """
    print("1: Generate new patients and upload to database")
    print("2: Retrieve patients from the database within a given age range")
    print("3: Exit")


if __name__ == '__main__':
    check_server_status()
    exit = False 
    while not exit:
        print("\nSelect a number from the menu below.")
        menu()
        choice = input("\n: ")
        if choice == "1": 
            generate_and_upload(db=FIRESTORE_DB)

        elif choice == "2": 
            retrieve_patients(db=FIRESTORE_DB)

        elif choice == "3": 
            print("Goodbye.")
            exit = True
        else: 
            print("Input not recognised, please try again. ")