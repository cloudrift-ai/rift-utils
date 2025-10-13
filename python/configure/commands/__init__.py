
from pathlib import Path
import pkgutil
from importlib import import_module
import inspect

from .cmd import BaseCmd

all_commands = []
command_map = {}

def get_all_commands():
    return all_commands

def get_command(name: str) -> BaseCmd | None:
    return command_map.get(name)

def create_command_instance(command_class):
    """Create an instance of a command class, handling special cases."""
    try:
        return command_class()
    except TypeError as e:
        print(f"Could not instantiate {command_class.__name__}: requires constructor parameters")
        return None
    except Exception as e:
        print(f"Error creating instance of {command_class.__name__}: {e}")
        return None

for (_, name, _) in pkgutil.iter_modules([Path(__file__).parent]):
    try:
        imported_module = import_module('.' + name, package=__name__)
    except ImportError as e:
        print("Could not import module " + name + ": " + str(e))
        continue

    for i in dir(imported_module):
        attribute = getattr(imported_module, i)
        if inspect.isclass(attribute) and (not inspect.isabstract(attribute)) and issubclass(attribute, BaseCmd) and attribute.__name__ != "BaseCmd":
            print("Found command class: ", attribute.__name__)
            
            # Create instance instead of adding class
            instance = create_command_instance(attribute)
            if instance:
                all_commands.append(instance)
                #print(f"Added instance: {instance.name()}")
            else:
                print(f"Skipped {attribute.__name__}: could not create instance")

command_map = {cmd.__class__.__name__: cmd for cmd in all_commands}