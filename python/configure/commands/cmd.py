from abc import ABC, abstractmethod

class BaseCmd(ABC):
    """ Base class for all commands."""

    def name(self) -> str:
        return self.__class__.__name__
    
    def description(self) -> str:
        return "No description provided."

    @abstractmethod
    def execute(self) -> bool:
        return False

