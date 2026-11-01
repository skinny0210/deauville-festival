import copy
import json
from abc import ABC, abstractmethod

from deauville.model import Festival

DATA_PATH = "data/festival.json"


class Storage(ABC):
    """Where the festival lives. The festival itself does not know."""

    @abstractmethod
    def load(self) -> Festival:
        """Read the festival, checking every rule again."""

    @abstractmethod
    def save(self, festival: Festival) -> None:
        """Write the festival."""


class JsonStorage(Storage):
    def __init__(self, path: str = DATA_PATH) -> None:
        self.path = path

    def load(self) -> Festival:
        with open(self.path, encoding="utf-8") as file:
            return Festival.from_data(json.load(file))

    def save(self, festival: Festival) -> None:
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(festival.to_data(), file, ensure_ascii=False, indent=2)
            file.write("\n")


class MemoryStorage(Storage):
    """Keeps the data in memory: handy for tests."""

    def __init__(self, data: dict) -> None:
        self._data = copy.deepcopy(data)

    def load(self) -> Festival:
        return Festival.from_data(copy.deepcopy(self._data))

    def save(self, festival: Festival) -> None:
        self._data = festival.to_data()
