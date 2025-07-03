"""Configuration management for the Crawler system."""

import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml
from pydantic import BaseModel, Field, field_validator
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


class ScrapeConfig(BaseModel):
    """Default scraping configuration."""
    timeout: int = 30
    retry_count: int = 3
    retry_delay: float = 1.0
    cache_enabled: bool = True
    cache_ttl: int = 3600
    headless: bool = True


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


class LLMConfig(BaseModel):
    """LLM provider configuration."""
    default_provider: str = "openai"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-haiku-20240307"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"


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


class OutputConfig(BaseModel):
    """Output configuration."""
    default_format: str = "markdown"
    templates_dir: str = "~/.crawler/templates"
    create_index: bool = True
    compress_results: bool = False


class GlobalConfig(BaseModel):
    """Global system configuration."""
    log_level: str = "INFO"
    log_file: Optional[str] = "~/.crawler/logs/crawler.log"
    max_workers: int = 10
    api_port: int = 8000
    api_host: str = "localhost"


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
    
    class Config:
        env_prefix = "CRAWLER_"
        env_nested_delimiter = "__"
        case_sensitive = False
        
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
        self.config_path = config_path
        self._config: Optional[CrawlerConfig] = None
        self._load_config()
    
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
    
    def _load_config(self) -> None:
        """Load configuration from file and environment."""
        config_data = {}
        
        # Load from file if it exists
        if self.config_path:
            config_file = Path(self.config_path)
        else:
            config_file = self._get_default_config_path()
        
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                file_data = yaml.safe_load(f) or {}
                config_data.update(file_data)
        
        # Load LLM API keys from environment
        llm_config = config_data.setdefault("llm", {})
        
        if "OPENAI_API_KEY" in os.environ:
            llm_config["openai_api_key"] = os.environ["OPENAI_API_KEY"]
        if "ANTHROPIC_API_KEY" in os.environ:
            llm_config["anthropic_api_key"] = os.environ["ANTHROPIC_API_KEY"]
        if "GEMINI_API_KEY" in os.environ:
            llm_config["gemini_api_key"] = os.environ["GEMINI_API_KEY"]
        
        # Create configuration with environment variable overrides
        self._config = CrawlerConfig(**config_data)
    
    @property
    def config(self) -> CrawlerConfig:
        """Get the current configuration."""
        if self._config is None:
            self._load_config()
        return self._config
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a configuration setting using dot notation.
        
        Args:
            key: Setting key in dot notation (e.g., 'scrape.timeout')
            default: Default value if setting is not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                # Handle aliased fields
                if k == "global":
                    k = "global_"
                    
                if hasattr(value, k):
                    value = getattr(value, k)
                elif isinstance(value, dict) and k in value:
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
        config_dict = self.config.dict()
        
        # Navigate to the parent of the target key
        current = config_dict
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
        
        # Recreate the config object
        self._config = CrawlerConfig(**config_dict)
    
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
        config_dict = default_config.dict(by_alias=True)
        
        # Write to YAML file
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)
        
        return config_path
    
    def reload_config(self) -> None:
        """Reload configuration from file."""
        self._config = None
        self._load_config()


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