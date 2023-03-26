import socket
import argparse
from datetime import datetime

# '7 BUILT $3FB0BD7827C760FE7F9DD810FCB10322D63AB4CF~relay1,$0A9B1B207FD13A6F117F95CAFA358EEE2234F19A~exit1,$A52CA5B56C64D864F6AE43E56F29ACBD5706DDA1~4uthority BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_VANGUARDS TIME_CREATED=2000-01-01T00:10:07.000000
# '6 BUILT $3FB0BD7827C760FE7F9DD810FCB10322D63AB4CF~relay1,$0A9B1B207FD13A6F117F95CAFA358EEE2234F19A~exit1,$A52CA5B56C64D864F6AE43E56F29ACBD5706DDA1~4uthority BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_VANGUARDS TIME_CREATED=2000-01-01T00:10:06.000000
# '3 BUILT $3FB0BD7827C760FE7F9DD810FCB10322D63AB4CF~relay1,$A52CA5B56C64D864F6AE43E56F29ACBD5706DDA1~4uthority,$0A9B1B207FD13A6F117F95CAFA358EEE2234F19A~exit1 BUILD_FLAGS=NEED_CAPACITY PURPOSE=GENERAL TIME_CREATED=2000-01-01T00:10:03.000000
# '4 BUILT $3FB0BD7827C760FE7F9DD810FCB10322D63AB4CF~relay1,$FF197204099FA0E507FA46D41FED97D3337B4BAA~relay2,$4EBB385C80A2CA5D671E16F1C722FBFB5F176891~exit2 BUILD_FLAGS=NEED_CAPACITY PURPOSE=GENERAL TIME_CREATED=2000-01-01T00:10

class Node:
    fingerprint: str
    name: str
    
    def __init__(self, string: str):
        self.fingerprint = string.split("~")[0].replace("$", "")
        self.name = string.split("~")[1]

class CircuitStatus:
    id: int
    status: str
    entry: Node
    middle: Node
    exit: Node
    build_flags: list[str]
    purpose: str
    time_created: datetime
    
    def __init__(self, string: str):
        parts = string.split(" ")
        self.id = int(parts[0])
        self.status = parts[1]
        nodes:list[str] = parts[2].split(",")
        self.entry = Node(nodes[0])
        self.middle = Node(nodes[1])
        self.exit = Node(nodes[2])
        self.build_flags = parts[3].split("=")[1].split(",")
        self.purpose = parts[4].split("=")[1]
        self.time_created = datetime.fromisoformat(parts[5].split("=")[1])
        
def get_lowest_id_circuit(circuits: list[CircuitStatus]) -> CircuitStatus:
    lowest_id = circuits[0].id
    result: CircuitStatus = circuits[0]
    
    for circuit in circuits:
        if circuit.id < lowest_id:
            lowest_id = circuit.id
            result = circuit
    
    return result

def authenticate(sock: socket.socket):
    sock.sendall(b"authenticate \"\"\n")
    received = sock.recv(1024).decode("ascii")
    print(received)

def get_circuit_status(sock: socket.socket) -> list[CircuitStatus]:
    sock.sendall(b"getinfo circuit-status\n")
    received = sock.recv(1024).decode("ascii")
    print(received)
    received_lines = received.splitlines()
    circuit_status: list[CircuitStatus] = []
    for line in received_lines[1:]:
        circuit_status.append(CircuitStatus(line))
    return circuit_status

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", "-p", type=int, default=-1)
    args = parser.parse_args()
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", args.port))
    authenticate(sock)
    
    circuit_status: list[CircuitStatus] = get_circuit_status(sock)
    print("Retrieved exit node: " + get_lowest_id_circuit(circuit_status).exit.name)
    
    sock.close()