import socket
import argparse
from datetime import datetime

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
    middle: Node | None
    exit: Node | None
    build_flags: list[str]
    purpose: str
    time_created: datetime

    def __init__(self, string: str):
        parts = string.split(" ")
        self.id = int(parts[0])
        self.status = parts[1]
        nodes:list[str] = parts[2].split(",")
        self.entry = Node(nodes[0])
        if len(nodes) == 1:
            self.middle = None
            self.exit = None
        if len(nodes) == 2:
            self.middle = None
            self.exit = Node(nodes[1])
        if len(nodes) == 3:
            self.middle = Node(nodes[1])
            self.exit = Node(nodes[2])
        self.build_flags = parts[3].split("=")[1].split(",")
        self.purpose = parts[4].split("=")[1]
        self.time_created = datetime.fromisoformat(parts[5].split("=")[1])

def get_lowest_id_circuit(circuits: list[CircuitStatus]) -> CircuitStatus|None:
    lowest_id: int = 0
    result: CircuitStatus|None = None

    for circuit in circuits:
        if circuit.purpose == "GENERAL" and (circuit.id < lowest_id or result == None):
            lowest_id = circuit.id
            result = circuit
    
    return result

def authenticate(sock: socket.socket):
    sock.sendall(b"authenticate \"\"\n")
    received = sock.recv(1024).decode("ascii")
    print(received)

def get_circuit_status_list(sock: socket.socket) -> list[CircuitStatus]:
    sock.sendall(b"getinfo circuit-status\n")
    received = sock.recv(4096).decode("ascii")
    print(received)
    received_lines = received.splitlines()
    cslst: list[CircuitStatus] = []
    for line in received_lines[1:]:
        if line[0] == ".":
            break
        cslst.append(CircuitStatus(line))
    return cslst

def get_stream_status_list(sock: socket.socket) -> list[str]:
    sock.sendall(b"getinfo stream-status\n")
    received = sock.recv(4096).decode("ascii")
    print(received)
    received_lines = received.splitlines()
    sslst: list[str] = []
    for line in received_lines[1:]:
        if line[0] == ".":
            break
        sslst.append(line)
    return sslst

def get_exit_node(control_port: int) -> Node|None:
    sock = connect(control_port)
    cs_lst: list[CircuitStatus] = get_circuit_status_list(sock)
    sock.close()

    cs: CircuitStatus|None = get_lowest_id_circuit(cs_lst)
    if cs != None:
        return cs.exit
    else:
        return None

def set_exit_nodes(control_port: int, exit_nodes: list[Node]):
    sock = connect(control_port)
    exit_node_str = ""
    for exit_node in exit_nodes:
        exit_node_str += exit_node.fingerprint + ","
    exit_node_str = exit_node_str[:-1]
    sock.sendall(f"setconf ExitNodes={exit_node_str}\n".encode("ascii"))
    received = sock.recv(1024).decode("ascii")
    print(received)
    sock.close()

def connect(control_port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", control_port))
    authenticate(sock)
    return sock