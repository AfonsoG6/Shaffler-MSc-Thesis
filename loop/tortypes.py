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
    
    @staticmethod
    def is_valid(string: str) -> bool:
        parts = string.split(" ")
        if len(parts) < 6:
            return False
        if not parts[0].isnumeric():
            return False
        if parts[1] not in ["LAUNCHED", "BUILT", "EXTENDED", "FAILED", "CLOSED"]:
            return False
        if len(parts[2].split(",")) not in [1, 2, 3]:
            return False
        if not parts[3].startswith("BUILD_FLAGS="):
            return False
        if not parts[4].startswith("PURPOSE="):
            return False
        if not parts[5].startswith("TIME_CREATED="):
            return False
        return True

    def __init__(self, string: str):
        # Example:
        # 7 BUILT $FF197204099FA0E507FA46D41FED97D3337B4BAA~relay2,$0A9B1B207FD13A6F117F95CAFA358EEE2234F19A~exit1,$A52CA5B56C64D864F6AE43E56F29ACBD5706DDA1~4uthority BUILD_FLAGS=IS_INTERNAL,NEED_CAPACITY,NEED_UPTIME PURPOSE=HS_VANGUARDS TIME_CREATED=2000-01-01T00:10:07.000000
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
    
    @staticmethod
    def is_valid(string: str) -> bool:
        parts = string.split(" ")
        if len(parts) < 4:
            return False
        if not parts[0].isnumeric():
            return False
        if parts[1] not in ["NEW", "NEWRESOLVE", "SENTCONNECT", "SENTRESOLVE", "SUCCEEDED", "DETACHED", "FAILED", "CLOSED"]:
            return False
        if not parts[2].isnumeric():
            return False
        return True
    
    def __init__(self, string: str):
        # Example:
        # 20 SUCCEEDED 3 11.0.0.200:80
        parts = string.split(" ")
        self.id = int(parts[0])
        self.status = parts[1]
        self.circuitStatusId = int(parts[2])
        self.address = parts[3]