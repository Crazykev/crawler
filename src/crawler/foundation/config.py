"""Configuration management for the Crawler system."""

import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml
from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings


class BrowserConfig(BaseModel):
    """Browser configuration settings."""
    user_agent: str = "Crawler/1.0"
    headless: bool = True
    timeout: int = 30
    viewport_width: int = 1920
    viewport_height: int = 1080
    proxy_url: Optional[str] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None
    
    model_config = ConfigDict(extra="allow")


class ScrapeConfig(BaseModel):
    """Default scraping configuration."""
    timeout: int = 30
    retry_count: int = 3
    retry_delay: float = 1.0
    cache_enabled: bool = True
    cache_ttl: int = 3600
    headless: bool = True
    
    model_config = ConfigDict(extra="allow")


class CrawlConfig(BaseModel):
    """Default crawling configuration."""
    max_depth: int = 3
    max_pages: int = 100
    max_duration: int = 3600
    delay: float = 1.0
    concurrent_requests: int = 5
    respect_robots: bool = True
    allow_external_links: bool = False
    allow_subdomains: bool = True
    
    model_config = ConfigDict(extra="allow")


class LLMConfig(BaseModel):
    """LLM provider configuration."""
    default_provider: str = "openai"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-haiku-20240307"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"
    
    model_config = ConfigDict(extra="allow")


class StorageConfig(BaseModel):
    """Storage configuration."""
    database_path: str = "~/.crawler/crawler.db"
    results_dir: str = "~/.crawler/results"
    cache_ttl: int = 3600
    session_timeout: int = 1800
    retention_days: int = 30
    
    # SQLite specific settings
    sqlite_wal_mode: bool = True
    sqlite_cache_size: int = 10000
    sqlite_synchronous: str = "NORMAL"
    
    model_config = ConfigDict(extra="allow")


class OutputConfig(BaseModel):
    """Output configuration."""
    default_format: str = "markdown"
    templates_dir: str = "~/.crawler/templates"
    create_index: bool = True
    compress_results: bool = False
    
    model_config = ConfigDict(extra="allow")


class GlobalConfig(BaseModel):
    """Global system configuration."""
    log_level: str = "INFO"
    log_file: Optional[str] = "~/.crawler/logs/crawler.log"
    max_workers: int = 10
    api_port: int = 8000
    api_host: str = "localhost"
    
    model_config = ConfigDict(extra="allow")


class CrawlerConfig(BaseSettings):
    """Main configuration class that combines all settings."""
    
    # Version information
    version: str = "1.0"
    
    # Component configurations
    global_: GlobalConfig = Field(default_factory=GlobalConfig, alias="global")
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    scrape: ScrapeConfig = Field(default_factory=ScrapeConfig)
    crawl: CrawlConfig = Field(default_factory=CrawlConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    
    # Profiles for different use cases
    profiles: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    
    model_config = ConfigDict(
        env_prefix="CRAWLER_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="allow"  # Allow extra fields
    )
        
    @field_validator("storage")
    @classmethod
    def expand_storage_paths(cls, v):
        """Expand user paths in storage configuration."""
        if isinstance(v, dict):
            v = StorageConfig(**v)
        
        v.database_path = str(Path(v.database_path).expanduser())
        v.results_dir = str(Path(v.results_dir).expanduser())
        
        if v.database_path.startswith("~"):
            v.database_path = str(Path(v.database_path).expanduser())
        if v.results_dir.startswith("~"):
            v.results_dir = str(Path(v.results_dir).expanduser())
            
        return v
    
    @field_validator("output")
    @classmethod
    def expand_output_paths(cls, v):
        """Expand user paths in output configuration."""
        if isinstance(v, dict):
            v = OutputConfig(**v)
            
        if v.templates_dir.startswith("~"):
            v.templates_dir = str(Path(v.templates_dir).expanduser())
            
        return v
    
    @field_validator("global_")
    @classmethod
    def expand_global_paths(cls, v):
        """Expand user paths in global configuration."""
        if isinstance(v, dict):
            v = GlobalConfig(**v)
            
        if v.log_file and v.log_file.startswith("~"):
            v.log_file = str(Path(v.log_file).expanduser())
            
        return v


class ConfigManager:
    """Manages configuration loading, validation, and access."""
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        self.config_path = Path(config_path) if config_path else None
        self._config: Dict[str, Any] = {}
        self._pydantic_config: Optional[CrawlerConfig] = None
        self._load_default_config()
    
    def _get_default_config_path(self) -> Path:
        """Get the default configuration file path."""
        # Check environment variable first
        env_path = os.getenv("CRAWLER_CONFIG_PATH")
        if env_path:
            return Path(env_path).expanduser()
        
        # Default to ~/.crawler/config.yaml
        config_dir = Path.home() / ".crawler"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "config.yaml"
    
    def get_default_config_path(self) -> Path:
        """Get the default configuration file path."""
        return self._get_default_config_path()
    
    def get_system_config_path(self) -> Path:
        """Get the system configuration file path."""
        return Path("/etc/crawler/config.yaml")
    
    def _load_default_config(self) -> None:
        """Load default configuration as dict."""
        # Create default config using Pydantic model
        default_config = CrawlerConfig()
        self._config = default_config.model_dump(by_alias=True)
        self._pydantic_config = default_config
    
    def _load_config(self) -> None:
        """Load configuration from file and environment (deprecated method)."""
        if self.config_path and self.config_path.exists():
            self.load_from_file()
        self.load_from_environment()
    
    @property
    def config(self) -> CrawlerConfig:
        """Get the current configuration as Pydantic model."""
        if self._pydantic_config is None:
            try:
                self._pydantic_config = CrawlerConfig(**self._config)
            except Exception:
                # Fallback to default if config is invalid
                self._pydantic_config = CrawlerConfig()
        return self._pydantic_config
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a configuration setting using dot notation.
        
        Args:
            key: Setting key in dot notation (e.g., 'scrape.timeout')
            default: Default value if setting is not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                # Handle aliased fields
                if k == "global":
                    k = "global_"
                    
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value
        except (AttributeError, KeyError, TypeError):
            return default
    
    def set_setting(self, key: str, value: Any) -> None:
        """Set a configuration setting (runtime only).
        
        Args:
            key: Setting key in dot notation
            value: Value to set
        """
        keys = key.split('.')
        
        # Navigate to the parent of the target key
        current = self._config
        for k in keys[:-1]:
            if k == "global":
                k = "global_"
            if k not in current:
                current[k] = {}
            current = current[k]
        
        # Set the final value
        final_key = keys[-1]
        if final_key == "global":
            final_key = "global_"
        current[final_key] = value
        
        # Clear cached Pydantic config so it's rebuilt next time
        self._pydantic_config = None
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate the current configuration.
        
        Returns:
            Dictionary with validation results
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        try:
            # Check for required sections in raw config
            required_sections = ["storage", "scrape", "crawl"]
            for section in required_sections:
                if section not in self._config:
                    result["errors"].append(f"Required section '{section}' is missing")
            
            # If we have missing required sections, don't continue validation
            if result["errors"]:
                result["valid"] = False
                return result
            
            # Test configuration instantiation
            config = self.config
            
            # Check required directories exist or can be created
            storage_dir = Path(config.storage.database_path).parent
            if not storage_dir.exists():
                try:
                    storage_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    result["errors"].append(f"Cannot create storage directory: {e}")
            
            results_dir = Path(config.storage.results_dir)
            if not results_dir.exists():
                try:
                    results_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    result["errors"].append(f"Cannot create results directory: {e}")
            
            # Check LLM API keys
            if not config.llm.openai_api_key:
                result["warnings"].append("OpenAI API key not configured")
            if not config.llm.anthropic_api_key:
                result["warnings"].append("Anthropic API key not configured")
            if not config.llm.gemini_api_key:
                result["warnings"].append("Gemini API key not configured")
            
            # Validate numeric ranges
            if config.scrape.timeout <= 0:
                result["errors"].append("Scrape timeout must be positive")
            if config.crawl.max_pages <= 0:
                result["errors"].append("Crawl max_pages must be positive")
            if config.crawl.concurrent_requests <= 0:
                result["errors"].append("Crawl concurrent_requests must be positive")
                
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Configuration validation failed: {e}")
        
        if result["errors"]:
            result["valid"] = False
            
        return result
    
    def get_section(self, section_name: str) -> Optional[Dict[str, Any]]:
        """Get a configuration section.
        
        Args:
            section_name: Name of the section
            
        Returns:
            Section dictionary or None if not found
        """
        section_name = "global_" if section_name == "global" else section_name
        return self._config.get(section_name)
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all configuration settings.
        
        Returns:
            Complete configuration dictionary
        """
        return self._config.copy()
    
    def load_from_file(self) -> None:
        """Load configuration from file."""
        if not self.config_path or not self.config_path.exists():
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if self.config_path.suffix.lower() == '.json':
                    import json
                    file_data = json.load(f)
                else:
                    file_data = yaml.safe_load(f) or {}
            
            # Merge with existing config
            self._deep_merge(self._config, file_data)
            self._pydantic_config = None
        except Exception:
            # Silently ignore file loading errors for now
            pass
    
    def save_to_file(self) -> None:
        """Save configuration to file."""
        if not self.config_path:
            return
        
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                if self.config_path.suffix.lower() == '.json':
                    import json
                    json.dump(self._config, f, indent=2)
                else:
                    yaml.dump(self._config, f, default_flow_style=False, indent=2)
        except Exception:
            # Silently ignore file saving errors for now
            pass
    
    def load_from_environment(self) -> None:
        """Load configuration from environment variables."""
        # Load LLM API keys from environment
        llm_config = self._config.setdefault("llm", {})
        
        if "OPENAI_API_KEY" in os.environ:
            llm_config["openai_api_key"] = os.environ["OPENAI_API_KEY"]
        if "ANTHROPIC_API_KEY" in os.environ:
            llm_config["anthropic_api_key"] = os.environ["ANTHROPIC_API_KEY"]
        if "GEMINI_API_KEY" in os.environ:
            llm_config["gemini_api_key"] = os.environ["GEMINI_API_KEY"]
        
        # Handle CRAWLER_ prefixed environment variables
        for key, value in os.environ.items():
            if key.startswith("CRAWLER_"):
                # Convert CRAWLER_SCRAPE_TIMEOUT to scrape.timeout
                config_key = key[8:].lower().replace("_", ".")
                
                # Try to convert to appropriate type
                try:
                    if value.lower() in ("true", "false"):
                        value = value.lower() == "true"
                    elif value.isdigit():
                        value = int(value)
                    elif "." in value and value.replace(".", "").isdigit():
                        value = float(value)
                except (ValueError, AttributeError):
                    pass
                
                self.set_setting(config_key, value)
        
        self._pydantic_config = None
    
    def merge_config(self, new_config: Dict[str, Any]) -> None:
        """Merge new configuration with existing.
        
        Args:
            new_config: Configuration data to merge
        """
        self._deep_merge(self._config, new_config)
        self._pydantic_config = None
    
    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Deep merge source into target dictionary."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value
    
    def load_hierarchical(self) -> None:
        """Load configuration hierarchically (system -> user -> custom)."""
        # Start with default config
        self._load_default_config()
        
        # Load system config
        system_path = self.get_system_config_path()
        if system_path.exists():
            temp_manager = ConfigManager(system_path)
            temp_manager.load_from_file()
            self.merge_config(temp_manager._config)
        
        # Load user config
        user_path = self.get_default_config_path()
        if user_path.exists():
            temp_manager = ConfigManager(user_path)
            temp_manager.load_from_file()
            self.merge_config(temp_manager._config)
        
        # Load custom config if specified
        if self.config_path and self.config_path.exists():
            temp_manager = ConfigManager(self.config_path)
            temp_manager.load_from_file()
            self.merge_config(temp_manager._config)
        
        # Load environment variables last
        self.load_from_environment()
    
    def create_default_config(self, config_path: Optional[Path] = None) -> Path:
        """Create a default configuration file.
        
        Args:
            config_path: Path to create config file (defaults to standard location)
            
        Returns:
            Path to created config file
        """
        if config_path is None:
            config_path = self._get_default_config_path()
        
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create default configuration
        default_config = CrawlerConfig()
        config_dict = default_config.model_dump(by_alias=True)
        
        # Write to YAML file
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)
        
        return config_path
    
    def reload_config(self) -> None:
        """Reload configuration from file."""
        self._load_default_config()
        if self.config_path and self.config_path.exists():
            self.load_from_file()
        self.load_from_environment()


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> CrawlerConfig:
    """Get the current configuration."""
    return get_config_manager().config