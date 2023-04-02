import socket
from tortypes import *
from utils import log
    
def get_predicted_circuit(circuits: list[CircuitStatus]) -> CircuitStatus|None:
    lowest_id: int = 0
    result: CircuitStatus|None = None

    for circuit in circuits:
        if circuit.purpose == "GENERAL" and (circuit.id < lowest_id or result == None):
            lowest_id = circuit.id
            result = circuit
    
    return result

def get_circuit_by_id(circuits: list[CircuitStatus], id: int) -> CircuitStatus|None:
    for circuit in circuits:
        if circuit.id == id:
            return circuit
    return None

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
    for line in received_lines:
        line = line.removeprefix("250+circuit-status=")
        if line == "250 OK":
            break
        if CircuitStatus.is_valid(line):
            cslst.append(CircuitStatus(line))
    return cslst

def get_stream_status_list(sock: socket.socket) -> list[StreamStatus]:
    sock.sendall(b"getinfo stream-status\n")
    received = sock.recv(4096).decode("ascii")
    print(received)
    received_lines = received.splitlines()
    sslst: list[StreamStatus] = []
    for line in received_lines:
        line = line.removeprefix("250-stream-status=")
        if line == "250 OK":
            break
        if StreamStatus.is_valid(line):
            sslst.append(StreamStatus(line))
    return sslst

def get_predicted_exit_node(control_port: int) -> Node|None:
    sock = connect(control_port)
    cs_lst: list[CircuitStatus] = get_circuit_status_list(sock)
    sock.close()

    cs: CircuitStatus|None = get_predicted_circuit(cs_lst)
    if cs != None:
        return cs.exit
    else:
        return None

def get_exit_nodes_of_current_streams(control_port: int) -> list[Node]:
    sock = connect(control_port)
    cs_lst: list[CircuitStatus] = get_circuit_status_list(sock)
    ss_lst: list[StreamStatus] = get_stream_status_list(sock)
    sock.close()
    nodes: list[Node] = []
    for ss in ss_lst:
        cs: CircuitStatus|None = get_circuit_by_id(cs_lst, ss.circuitStatusId)
        if cs == None:
            continue
        exit: Node|None = cs.exit
        if exit == None:
            continue
        nodes.append(exit)
    return nodes

def get_exit_nodes(control_port: int) -> list[Node]:
    nodes: list[Node] = get_exit_nodes_of_current_streams(control_port)
    if (len(nodes) == 0):
        predicted_node: Node|None = get_predicted_exit_node(control_port)
        if predicted_node != None:
            nodes.append(predicted_node)
    return nodes

def exit_nodes_to_string(exit_nodes: list[Node]) -> str:
    exit_node_str = ""
    for exit_node in exit_nodes:
        exit_node_str += exit_node.fingerprint + ","
    if len(exit_nodes) > 0:
        exit_node_str = exit_node_str[:-1]
    return exit_node_str

def set_exit_nodes(control_port: int, exit_nodes: list[Node]):
    sock = connect(control_port)
    if len(exit_nodes) == 0:
        sock.sendall(b"resetconf ExitNodes\n")
        log("CONTROL", "ExitNodes=")
    else:
        exit_nodes_str = exit_nodes_to_string(exit_nodes)
        sock.sendall(f"setconf ExitNodes={exit_nodes_str}\n".encode("ascii"))
        log("CONTROL", f"ExitNodes={exit_nodes_str}")
    received = sock.recv(1024).decode("ascii")
    print(received)
    sock.close()

def map_address(control_port: int, address: str, exit: Node) -> None:
    sock = connect(control_port)
    log("CONTROL", f"Mapping {address} to {address}.{exit.fingerprint}.exit ({exit.name})")
    sock.sendall(f"mapaddress {address}={address}.{exit.fingerprint}.exit\n".encode("ascii"))
    received = sock.recv(1024).decode("ascii")
    print(received)
    sock.close()

def connect(control_port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", control_port))
    authenticate(sock)
    return sock    