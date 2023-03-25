from http.server import HTTPServer, BaseHTTPRequestHandler
import ssl
import random

class RandHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(random.randbytes(1024))

def run_server(server_port:int):
    httpd: HTTPServer = HTTPServer(
            server_address=('localhost', server_port),
            RequestHandlerClass=RandHTTPRequestHandler)

    context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain("./keys/server/cert.pem", "./keys/server/key.pem", "loop")

    httpd.socket = context.wrap_socket(
            sock=httpd.socket,
            server_side=True)

    httpd.serve_forever()


if __name__ == '__main__':
    run_server(29999)