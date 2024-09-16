import socketserver
import ssl


class HL7TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        """
        Handles an incoming TCP connection and processes the HL7 message.

        This method is called for each incoming connection to the TCP server.
        """
        try:

            context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile='./keys/tcp-server-cert.pem', keyfile='./keys/tcp-server-key.pem')

            self.request = context.wrap_socket(self.request, server_side=True)

            data = self.request.recv(1024).strip().decode('utf-8', 'ignore')
            
            if not data:
                raise ConnectionAbortedError()
            
            print(f"Received HL7 message:\n{data}")
            
            self.request.sendall("200".encode('utf-8'))
            
        except ConnectionResetError:
            # This will catch the case when the client has shut down the connection
            print("Connection reset - closing the connection.")
            
        except ConnectionAbortedError:
            # This will catch the case when the client has shut down the connection
            print("No data detected - closing the connection.")
            
        except Exception as e:
            error_message = f"Error processing message: {repr(e)}"
            print(error_message)
            self.request.sendall("400".encode("utf-8"))

def run_tcp_server(host='localhost', port=8082):
    """
    Runs the TCP server.

    Args:
        host (str, optional): The hostname or IP address to bind the server to. Defaults to 'localhost'.
        port (int, optional): The port number to bind the server to. Defaults to 8081.
    """
    server = socketserver.TCPServer((host, port), HL7TCPHandler)
    print(f"Starting dummy ULTRA TCP server on {host}:{port}")
    server.serve_forever()

if __name__ == "__main__":
    run_tcp_server()