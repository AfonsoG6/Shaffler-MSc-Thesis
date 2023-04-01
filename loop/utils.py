from threading import Condition, Event, Thread
from datetime import datetime

class StoppableThread(Thread):
    def __init__(self,  *args, **kwargs):
        super(StoppableThread, self).__init__(*args, **kwargs)
        self.stop_event = Event()

    def stop(self):
        self.stop_event.set()
        self.join(0.5)

    def stopped(self):
        return self.stop_event.is_set()

def sleep(time: float) -> None:
    condition: Condition = Condition()
    with condition:
        condition.wait(timeout=time)
        
def log(context: str, message: str) -> None:
    print(f"{datetime.now().strftime('%b %d %H:%M:%S.%f')} [{context}] {message}")