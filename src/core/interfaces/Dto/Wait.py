from dataclasses import dataclass

@dataclass
class Wait:
    seconds: int
    
    def __str__(self) -> str:
        return f"Wait {self.seconds} seconds"