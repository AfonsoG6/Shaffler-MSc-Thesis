from datetime import datetime

class Node:
    fingerprint: str
    name: str

    def __init__(self, string: str):
        self.fingerprint = string.split("~")[0].replace("$", "")
        self.name = string.split("~")[1]
    
    def __eq__(self, __value: object) -> bool:
        if isinstance(__value, Node):
            return self.fingerprint == __value.fingerprint
        else:
            return False
    
    def __ne__(self, __value: object) -> bool:
        return not self.__eq__(__value)

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

class StreamStatus:
    id: int
    status: str
    circuitStatusId: int
    address: str
    
    def __init__(self, string: str):
        # Example:
        # 20 SUCCEEDED 3 11.0.0.200:80
        parts = string.split(" ")
        self.id = int(parts[0])
        self.status = parts[1]
        self.circuitStatusId = int(parts[2])
        self.address = parts[3]