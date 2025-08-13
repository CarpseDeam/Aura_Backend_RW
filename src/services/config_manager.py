# services/config_manager.py
"""
Manages application configuration from a `config.yaml` file.
"""

import logging
import os
import yaml
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CONFIG_FILE_PATH = "config.yaml"

DEFAULT_CONFIG = {
    'llm_provider': 'gemini',
    'plan_temperature': 0.6,
    'build_temperature': 0.1,
    'ollama': {
        'model': 'Qwen3-coder',
        'host': 'http://localhost:11434'
    },
    'gemini': {
        'model': 'gemini-2.5-pro'
        # The API key should NOT be stored here.
        # It will be read from the GOOGLE_API_KEY environment variable.
    }
}


class ConfigManager:
    """
    Handles loading and accessing configuration from a YAML file.
    """

    def __init__(self, config_path: str = CONFIG_FILE_PATH) -> None:
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self._load_or_create_config()

    def _load_or_create_config(self) -> None:
        if not os.path.exists(self.config_path):
            logger.info(f"Config file not found. Creating default '{self.config_path}'.")
            self._create_default_config()

        self._load_config()

    def _create_default_config(self) -> None:
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, sort_keys=False)
            logger.info(f"Default config file created. Please review '{self.config_path}'.")
        except IOError as e:
            logger.error(f"Failed to create default config file: {e}")

    def _load_config(self) -> None:
        try:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
                logger.info(f"Configuration loaded successfully from '{self.config_path}'.")
        except (IOError, yaml.YAMLError) as e:
            logger.error(f"Error loading or parsing config file '{self.config_path}': {e}")
            self.config = DEFAULT_CONFIG
            logger.warning("Falling back to default configuration due to load error.")

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        keys = key.split('.')
        value = self.config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            default_value = DEFAULT_CONFIG
            try:
                for k in keys:
                    default_value = default_value[k]
                logger.debug(f"Config key '{key}' not found in file, returning default value from DEFAULT_CONFIG.")
                return default_value
            except (KeyError, TypeError):
                logger.warning(
                    f"Config key '{key}' not found in file or defaults, returning provided default: {default}.")
                return default