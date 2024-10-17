import os
import importlib
from crewai_tools import BaseTool as CrewAIBaseTool
from langchain.tools import BaseTool as LangChainBaseTool
import logging
import crewai_tools
from typing import Optional
from django.core.cache import cache

logger = logging.getLogger(__name__)

def get_available_tools():
    tools_dir = os.path.join('apps', 'agents', 'tools')
    available_tools = []

    for root, dirs, files in os.walk(tools_dir):
        for item in dirs + files:
            if item.endswith('.py') and not item.startswith('__'):
                rel_path = os.path.relpath(os.path.join(root, item), tools_dir)
                module_path = os.path.splitext(rel_path)[0].replace(os.path.sep, '.')
                available_tools.append(module_path)

    return available_tools

def get_tool_classes(tool_path):
    module_path = f"apps.agents.tools.{tool_path}"
    if module_path.endswith('.py'):
        module_path = module_path[:-3]
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        logger.error(f"Failed to import module {module_path}: {e}")
        return []
    
    tool_classes = []
    for name, obj in module.__dict__.items():
        if isinstance(obj, type) and name.endswith('Tool'):
            try:
                if issubclass(obj, (CrewAIBaseTool, LangChainBaseTool)) or (hasattr(obj, '_run') and callable(getattr(obj, '_run'))):
                    if not any(issubclass(other, obj) and other != obj for other in module.__dict__.values() if isinstance(other, type)):
                        tool_classes.append(obj)
            except TypeError:
                # This can happen if obj is not a class or doesn't inherit from the expected base classes
                logger.warning(f"Skipping {name} as it's not a valid tool class")
    
    logger.debug(f"Found tool classes for {tool_path}: {[cls.__name__ for cls in tool_classes]}")
    return tool_classes

def get_tool_description(tool_class_obj):
    logger.debug(f"Attempting to get description for {tool_class_obj}")

    if hasattr(tool_class_obj, 'description'):
        description = getattr(tool_class_obj, 'description')
        if isinstance(description, str):
            logger.debug(f"Found description class attribute: {description}")
            return description

    if hasattr(tool_class_obj, 'name'):
        name = getattr(tool_class_obj, 'name')
        if isinstance(name, str):
            logger.debug(f"Found name class attribute: {name}")
            return name

    if hasattr(tool_class_obj, '__annotations__') and 'description' in tool_class_obj.__annotations__:
        description = tool_class_obj.__annotations__['description']
        if isinstance(description, str):
            logger.debug(f"Found description in class annotations: {description}")
            return description

    if hasattr(tool_class_obj, 'model_fields') and 'description' in tool_class_obj.model_fields:
        description = tool_class_obj.model_fields['description'].default
        if isinstance(description, str):
            logger.debug(f"Found description in model_fields: {description}")
            return description

    if tool_class_obj.__doc__:
        docstring = tool_class_obj.__doc__.strip()
        logger.debug(f"Found docstring: {docstring}")
        return docstring

    #  Corrected schema handling: Access the description directly if it exists.
    if hasattr(tool_class_obj, 'schema') and callable(tool_class_obj.schema):
        try:
            schema = tool_class_obj.schema()
            if isinstance(schema, dict) and 'description' in schema and isinstance(schema['description'], str):
                 logger.debug(f"Found description in schema: {schema['description']}")
                 return schema['description']
        except Exception as e:
            logger.warning(f"Error getting schema for {tool_class_obj.__name__}: {str(e)}")


    default_description = f"A tool of type {tool_class_obj.__name__}"
    logger.debug(f"Using default description: {default_description}")
    return default_description

def get_tool_class_obj(tool_class, tool_subclass):
    module = importlib.import_module(f"apps.agents.tools.{tool_class}.{tool_class}")
    return getattr(module, tool_subclass)

def load_tool(tool_model) -> Optional[CrewAIBaseTool]:
    logger.info(f"Attempting to load tool: {tool_model.tool_class}.{tool_model.tool_subclass}")
    cache_key = f"tool_class_{tool_model.tool_class}_{tool_model.tool_subclass}"
    cached_tool = cache.get(cache_key)
    
    if cached_tool:
        logger.info(f"Retrieved tool from cache: {tool_model.tool_class}.{tool_model.tool_subclass}")
        tool_instance = cached_tool() if callable(cached_tool) else cached_tool
        logger.info(f"Loaded tool instance: {tool_instance}")
        return tool_instance

    try:
        # Check if it's a pre-built CrewAI tool
        if hasattr(crewai_tools, tool_model.tool_class):
            logger.info(f"Loading pre-built CrewAI tool: {tool_model.tool_class}")
            tool_class = getattr(crewai_tools, tool_model.tool_class)
            tool_instance = tool_class()
            cache.set(cache_key, tool_instance, timeout=3600)
            return tool_instance

        # If not, try to import a custom tool
        full_module_path = f"apps.agents.tools.{tool_model.tool_class}"
        logger.info(f"Attempting to import custom tool module: {full_module_path}")
        module = importlib.import_module(full_module_path)
        tool_class = getattr(module, tool_model.tool_subclass)
        
        if issubclass(tool_class, CrewAIBaseTool):
            logger.info(f"Loaded custom CrewAI tool: {tool_model.tool_subclass}")
            tool_instance = tool_class()
            cache.set(cache_key, tool_instance, timeout=3600)
            logger.info(f"Cached and returned tool instance: {tool_instance}")
            return tool_instance
        elif issubclass(tool_class, LangChainBaseTool):
            logger.info(f"Loaded and wrapped LangChain tool: {tool_model.tool_subclass}")
            # Wrap LangChain tool in CrewAI compatible class
            class WrappedLangChainTool(CrewAIBaseTool):
                name = tool_class.name
                description = get_tool_description(tool_class)

                def _run(self, *args, **kwargs):
                    return tool_class()(*args, **kwargs)

            tool_instance = WrappedLangChainTool()
            cache.set(cache_key, tool_instance, timeout=3600)
            logger.info(f"Cached and returned wrapped tool instance: {tool_instance}")
            return tool_instance
        else:
            raise ValueError(f"Unsupported tool class: {tool_class}")

    except ImportError as e:
        logger.error(f"Error importing tool module {full_module_path}: {str(e)}")
    except AttributeError as e:
        logger.error(f"Error finding tool class {tool_model.tool_subclass} in module {full_module_path}: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error loading tool {full_module_path}.{tool_model.tool_subclass}: {str(e)}")
    
    return None
