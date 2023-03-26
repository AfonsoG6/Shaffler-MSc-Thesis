from http.server import HTTPServer, BaseHTTPRequestHandler
import ssl
import random
import argparse

class RandHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(random.randbytes(1024))

def run_server(server_host:str, server_port:int):
    httpd: HTTPServer = HTTPServer(
            server_address=(server_host, server_port),
            RequestHandlerClass=RandHTTPRequestHandler)

    context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain("./keys/server/cert.pem", "./keys/server/key.pem", "loop")

    httpd.socket = context.wrap_socket(
            sock=httpd.socket,
            server_side=True)

    httpd.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    
    parser.add_argument("--server_host", "-svh", type=str, default="127.0.0.1")
    parser.add_argument("--server_port", "-svp", type=int, default=29999)
    args=parser.parse_args()
    
    run_server(args.server_host, args.server_port)