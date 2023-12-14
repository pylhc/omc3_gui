from typing import Iterator, Tuple, Any

EXCLUDED_NAME = "EXCLUDED_ATTRIBUTES"

# Metaclasses ------------------------------------------------------------------

class IterableAttributeNames(type):
    """ Makes the class itself iterable over its attribute names. """


    def __iter__(self) -> Iterator[str]:
        for attr in dir(self):
            if not attr.startswith("__") and attr != EXCLUDED_NAME and attr not in getattr(self, EXCLUDED_NAME, []):
                yield attr


class IterableAttributeValues(type):
    """ Makes the class itself iterable over its attribute values. """
    def __iter__(self) -> Iterator[Any]:
        for attr, value in self.__dict__.items():
            if not attr.startswith("__"):
                yield value


class IterableAttributeItems(type):
    """ Makes the class itself iterable over its attribute name and values. """
    def __iter__(self) -> Iterator[Tuple[str, Any]]:
        for attr, value in self.__dict__.items():
            if not attr.startswith("__"):
                yield attr, value


# Iterable Class ---------------------------------------------------------------


class IterClass(metaclass=IterableAttributeNames):

    EXCLUDED_ATTRIBUTES = ["keys", "values", "items"]
    
    @classmethod
    def keys(cls) -> Iterator[str]:
        for attr in cls:
            yield attr
    
    @classmethod
    def values(cls) -> Iterator[Any]:
        for attr in cls:
            yield getattr(cls, attr)
    
    @classmethod
    def items(cls) -> Iterator[Tuple[str, Any]]:
        for attr in cls:
            yield attr, getattr(cls, attr)