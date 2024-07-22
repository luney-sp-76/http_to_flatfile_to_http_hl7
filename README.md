# HL7 to HTTP and TCP Conversion and Validation

## Overview

This project provides a complete solution for converting HL7 messages between plain/text HTTP payloads, flat files, and TCP connections. It includes validation of HL7 messages and generation of appropriate ACK messages. The solution is implemented with a simple HTTP server and TCP server.

The project structure comprises of different sub-modules that are combined to create working tcp/ip, http servers and a FHIR patient creation module. To combine the projects use this guide

https://github.blog/2016-02-01-working-with-submodules/

## Features

- Convert HL7 messages from HTTP plain/text to flat files.
- Convert HL7 messages from flat files to HTTP plain/text.
- Validate HL7 messages.
- Generate ACK messages based on the validation results.
- HTTP server with endpoints for conversions and forwarding messages to TCP server.
- TCP server for handling HL7 messages from HTTP server and remote TCP hosts.
- Bi-directional communication between HTTP and TCP servers.

## Requirements

- Python 3.7 or higher
- The `requests` library for HTTP client functionality

## Installation

1. Clone the repository:

    ```sh
    git clone <repository_url>
    cd <repository_directory>
    ```

2. Install the required Python packages:

    ```sh
    pip install -r requirements.txt
    ```

## Usage

### Running the HTTP Server

To start the HTTP server, run the following command:

```sh
python server.py

### Running the TCP server

To Start the TCP server, run the following command:

```sh
python tcp_server.py

### Notes
I added a terminal in my local machine listening on port 8082 to receive messages sent by postman like this in the body as raw text:

```
MSH|^~\\&|HIS|RIH|ADT|RIH|20230523102000||ADT^A31|123456|P|2.4
EVN|A31|20230523102000
PID|1||12345678^^^RIH^MR||Doe^John^A||19800101|M|||456 Elm St^^Newtown^CA^90211^USA||555-5678|||||M|N|123-45-6789
PV1|1|O|^^^RIH||||1234^Smith^John^A|||||||||||||||12345678
```
To this address::
http://localhost:8080/hl7_http

The program converts the message to flat file and sends to the TCP IP port.

The tcp_client.py will send a flat file HL7 to the TCP server which sends it on the HTTP server which passes it to beeceptor as a mock endpoint /hl7

