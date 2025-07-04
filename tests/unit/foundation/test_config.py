"""Tests for configuration management."""

import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open

from crawler.foundation.config import ConfigManager
from crawler.foundation.errors import ConfigurationError


class TestConfigManager:
    """Test suite for ConfigManager."""
    
    def test_init_with_default_path(self):
        """Test initialization with default config path."""
        config_manager = ConfigManager()
        assert config_manager.config_path is None
        assert isinstance(config_manager._config, dict)
    
    def test_init_with_custom_path(self, temp_dir):
        """Test initialization with custom config path."""
        config_path = temp_dir / "custom_config.yaml"
        config_manager = ConfigManager(config_path=config_path)
        assert config_manager.config_path == config_path
    
    def test_get_setting_existing(self, config_manager):
        """Test getting an existing setting."""
        value = config_manager.get_setting("scrape.timeout")
        assert value == 10
    
    def test_get_setting_with_default(self, config_manager):
        """Test getting a non-existing setting with default."""
        value = config_manager.get_setting("non.existing", default=42)
        assert value == 42
    
    def test_get_setting_nonexisting_no_default(self, config_manager):
        """Test getting a non-existing setting without default."""
        value = config_manager.get_setting("non.existing")
        assert value is None
    
    def test_set_setting_new(self, config_manager):
        """Test setting a new configuration value."""
        config_manager.set_setting("new.setting", "test_value")
        assert config_manager.get_setting("new.setting") == "test_value"
    
    def test_set_setting_existing(self, config_manager):
        """Test updating an existing configuration value."""
        config_manager.set_setting("scrape.timeout", 20)
        assert config_manager.get_setting("scrape.timeout") == 20
    
    def test_get_section_existing(self, config_manager):
        """Test getting an existing configuration section."""
        scrape_config = config_manager.get_section("scrape")
        assert isinstance(scrape_config, dict)
        assert "timeout" in scrape_config
        assert scrape_config["timeout"] == 10
    
    def test_get_section_nonexisting(self, config_manager):
        """Test getting a non-existing configuration section."""
        section = config_manager.get_section("nonexisting")
        assert section is None
    
    def test_get_all_settings(self, config_manager):
        """Test getting all configuration settings."""
        all_settings = config_manager.get_all_settings()
        assert isinstance(all_settings, dict)
        assert "scrape" in all_settings
        assert "crawl" in all_settings
        assert "storage" in all_settings
    
    def test_load_from_file_yaml(self, temp_dir):
        """Test loading configuration from YAML file."""
        config_data = {
            "test": {
                "value": 123,
                "name": "test_config"
            }
        }
        
        config_file = temp_dir / "test_config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        config_manager = ConfigManager(config_path=config_file)
        config_manager.load_from_file()
        
        assert config_manager.get_setting("test.value") == 123
        assert config_manager.get_setting("test.name") == "test_config"
    
    def test_load_from_file_json(self, temp_dir):
        """Test loading configuration from JSON file."""
        import json
        
        config_data = {
            "test": {
                "value": 456,
                "name": "json_config"
            }
        }
        
        config_file = temp_dir / "test_config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        config_manager = ConfigManager(config_path=config_file)
        config_manager.load_from_file()
        
        assert config_manager.get_setting("test.value") == 456
        assert config_manager.get_setting("test.name") == "json_config"
    
    def test_load_from_file_nonexistent(self, temp_dir):
        """Test loading from non-existent file."""
        config_file = temp_dir / "nonexistent.yaml"
        config_manager = ConfigManager(config_path=config_file)
        
        # Should not raise exception, should use defaults
        config_manager.load_from_file()
        assert isinstance(config_manager._config, dict)
    
    def test_save_to_file_yaml(self, temp_dir, config_manager):
        """Test saving configuration to YAML file."""
        config_file = temp_dir / "save_test.yaml"
        config_manager.config_path = config_file
        
        config_manager.set_setting("test.save", "saved_value")
        config_manager.save_to_file()
        
        assert config_file.exists()
        
        # Load and verify
        with open(config_file, 'r') as f:
            saved_data = yaml.safe_load(f)
        
        assert saved_data["test"]["save"] == "saved_value"
    
    def test_save_to_file_json(self, temp_dir, config_manager):
        """Test saving configuration to JSON file."""
        config_file = temp_dir / "save_test.json"
        config_manager.config_path = config_file
        
        config_manager.set_setting("test.save", "json_saved")
        config_manager.save_to_file()
        
        assert config_file.exists()
        
        # Load and verify
        import json
        with open(config_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data["test"]["save"] == "json_saved"
    
    def test_reload_config(self, temp_dir):
        """Test reloading configuration from file."""
        config_data = {"reload": {"test": "initial"}}
        
        config_file = temp_dir / "reload_test.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        config_manager = ConfigManager(config_path=config_file)
        config_manager.load_from_file()
        
        assert config_manager.get_setting("reload.test") == "initial"
        
        # Modify file
        config_data["reload"]["test"] = "modified"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Reload
        config_manager.reload_config()
        assert config_manager.get_setting("reload.test") == "modified"
    
    def test_validate_config_valid(self, config_manager):
        """Test validating a valid configuration."""
        result = config_manager.validate_config()
        assert result["valid"] is True
        assert len(result["errors"]) == 0
    
    def test_validate_config_invalid_timeout(self, config_manager):
        """Test validating configuration with invalid timeout."""
        config_manager.set_setting("scrape.timeout", -1)
        result = config_manager.validate_config()
        assert result["valid"] is False
        assert len(result["errors"]) > 0
    
    def test_validate_config_missing_required(self, config_manager):
        """Test validating configuration with missing required fields."""
        # Remove required section
        config_manager._config.pop("storage", None)
        result = config_manager.validate_config()
        assert result["valid"] is False
        assert len(result["errors"]) > 0
    
    @patch.dict("os.environ", {"CRAWLER_SCRAPE_TIMEOUT": "25"})
    def test_load_from_environment(self):
        """Test loading configuration from environment variables."""
        config_manager = ConfigManager()
        config_manager.load_from_environment()
        
        # Environment variable should override default
        assert config_manager.get_setting("scrape.timeout") == 25
    
    @patch.dict("os.environ", {"CRAWLER_NEW_SETTING": "env_value"})
    def test_load_from_environment_new_setting(self):
        """Test loading new setting from environment variables."""
        config_manager = ConfigManager()
        config_manager.load_from_environment()
        
        assert config_manager.get_setting("new.setting") == "env_value"
    
    def test_merge_configs(self, config_manager):
        """Test merging multiple configurations."""
        new_config = {
            "scrape": {
                "timeout": 30,
                "new_option": True
            },
            "new_section": {
                "value": "merged"
            }
        }
        
        config_manager.merge_config(new_config)
        
        # Existing value should be updated
        assert config_manager.get_setting("scrape.timeout") == 30
        # New option should be added
        assert config_manager.get_setting("scrape.new_option") is True
        # New section should be added
        assert config_manager.get_setting("new_section.value") == "merged"
        # Existing values not in new config should be preserved
        assert config_manager.get_setting("scrape.headless") is True
    
    def test_get_default_config_path(self):
        """Test getting default configuration path."""
        config_manager = ConfigManager()
        default_path = config_manager.get_default_config_path()
        
        assert isinstance(default_path, Path)
        assert default_path.name == "config.yaml"
    
    def test_get_system_config_path(self):
        """Test getting system configuration path."""
        config_manager = ConfigManager()
        system_path = config_manager.get_system_config_path()
        
        assert isinstance(system_path, Path)
        assert "crawler" in str(system_path)
    
    def test_hierarchical_loading(self, temp_dir):
        """Test hierarchical configuration loading (system -> user -> custom)."""
        # Create system config
        system_config = {"system": {"value": "system"}, "common": {"source": "system"}}
        system_file = temp_dir / "system.yaml"
        with open(system_file, 'w') as f:
            yaml.dump(system_config, f)
        
        # Create user config
        user_config = {"user": {"value": "user"}, "common": {"source": "user"}}
        user_file = temp_dir / "user.yaml"
        with open(user_file, 'w') as f:
            yaml.dump(user_config, f)
        
        # Create custom config
        custom_config = {"custom": {"value": "custom"}, "common": {"source": "custom"}}
        custom_file = temp_dir / "custom.yaml"
        with open(custom_file, 'w') as f:
            yaml.dump(custom_config, f)
        
        with patch.object(ConfigManager, 'get_system_config_path', return_value=system_file):
            with patch.object(ConfigManager, 'get_default_config_path', return_value=user_file):
                config_manager = ConfigManager(config_path=custom_file)
                config_manager.load_hierarchical()
                
                # Custom should override user and system
                assert config_manager.get_setting("common.source") == "custom"
                # All values should be present
                assert config_manager.get_setting("system.value") == "system"
                assert config_manager.get_setting("user.value") == "user"
                assert config_manager.get_setting("custom.value") == "custom"


@pytest.mark.integration
class TestConfigManagerIntegration:
    """Integration tests for ConfigManager."""
    
    def test_full_configuration_cycle(self, temp_dir):
        """Test complete configuration lifecycle."""
        config_file = temp_dir / "integration.yaml"
        
        # Create config manager
        config_manager = ConfigManager(config_path=config_file)
        
        # Set some values
        config_manager.set_setting("test.integration", True)
        config_manager.set_setting("test.value", 42)
        
        # Save to file
        config_manager.save_to_file()
        assert config_file.exists()
        
        # Create new instance and load
        new_config_manager = ConfigManager(config_path=config_file)
        new_config_manager.load_from_file()
        
        # Verify values
        assert new_config_manager.get_setting("test.integration") is True
        assert new_config_manager.get_setting("test.value") == 42
        
        # Reload and modify
        new_config_manager.set_setting("test.modified", True)
        new_config_manager.save_to_file()
        
        # Original should reload correctly
        config_manager.reload_config()
        assert config_manager.get_setting("test.modified") is True


class TestConfigManagerEdgeCases:
    """Edge case tests for ConfigManager."""
    
    def test_get_setting_with_empty_key(self, config_manager):
        """Test getting setting with empty key."""
        result = config_manager.get_setting("", default="empty")
        assert result == "empty"
    
    def test_get_setting_with_none_key(self, config_manager):
        """Test getting setting with None key."""
        with pytest.raises(AttributeError):
            config_manager.get_setting(None)
    
    def test_set_setting_with_empty_key(self, config_manager):
        """Test setting with empty key."""
        config_manager.set_setting("", "empty_value")
        # Empty key creates a root-level key
        assert config_manager.get_setting("") == "empty_value"
    
    def test_set_setting_deep_nested(self, config_manager):
        """Test setting deeply nested configuration."""
        config_manager.set_setting("level1.level2.level3.level4.value", "deep")
        assert config_manager.get_setting("level1.level2.level3.level4.value") == "deep"
        assert config_manager.get_setting("level1.level2.level3.level4") == {"value": "deep"}
    
    def test_merge_config_with_conflicting_types(self, config_manager):
        """Test merging configs where same key has different types."""
        # Set a string value
        config_manager.set_setting("conflict.value", "string")
        
        # Merge with dict value
        new_config = {
            "conflict": {
                "value": {"nested": "dict"}
            }
        }
        config_manager.merge_config(new_config)
        
        # Dict should override string
        assert config_manager.get_setting("conflict.value.nested") == "dict"
    
    def test_load_from_file_corrupted_yaml(self, temp_dir):
        """Test loading from corrupted YAML file."""
        config_file = temp_dir / "corrupted.yaml"
        with open(config_file, 'w') as f:
            f.write("invalid: yaml: content: [unclosed")
        
        config_manager = ConfigManager(config_path=config_file)
        # Should not raise exception, should use defaults
        config_manager.load_from_file()
        assert isinstance(config_manager._config, dict)
    
    def test_load_from_file_corrupted_json(self, temp_dir):
        """Test loading from corrupted JSON file."""
        config_file = temp_dir / "corrupted.json"
        with open(config_file, 'w') as f:
            f.write('{"invalid": json, "content"}')
        
        config_manager = ConfigManager(config_path=config_file)
        # Should not raise exception, should use defaults
        config_manager.load_from_file()
        assert isinstance(config_manager._config, dict)
    
    def test_save_to_file_permission_error(self, temp_dir, config_manager):
        """Test saving to file with permission error."""
        # Create read-only directory
        readonly_dir = temp_dir / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)
        
        config_file = readonly_dir / "test.yaml"
        config_manager.config_path = config_file
        
        # Should not raise exception
        config_manager.save_to_file()
        
        # Cleanup
        readonly_dir.chmod(0o755)
    
    def test_validate_config_with_exception(self, config_manager):
        """Test config validation when required sections are missing."""
        # Remove all required sections to force validation failure
        config_manager._config.clear()
        
        result = config_manager.validate_config()
        assert result["valid"] is False
        assert len(result["errors"]) > 0
    
    def test_environment_variable_type_conversion(self):
        """Test automatic type conversion from environment variables."""
        with patch.dict("os.environ", {
            "CRAWLER_TEST_BOOL_TRUE": "true",
            "CRAWLER_TEST_BOOL_FALSE": "false", 
            "CRAWLER_TEST_INT": "123",
            "CRAWLER_TEST_FLOAT": "45.67",
            "CRAWLER_TEST_STRING": "just_a_string"
        }):
            config_manager = ConfigManager()
            config_manager.load_from_environment()
            
            assert config_manager.get_setting("test.bool.true") is True
            assert config_manager.get_setting("test.bool.false") is False
            assert config_manager.get_setting("test.int") == 123
            assert config_manager.get_setting("test.float") == 45.67
            assert config_manager.get_setting("test.string") == "just_a_string"
    
    def test_environment_variable_invalid_conversion(self):
        """Test environment variable conversion with invalid values."""
        with patch.dict("os.environ", {
            "CRAWLER_TEST_INVALID_FLOAT": "not.a.float"
        }):
            config_manager = ConfigManager()
            config_manager.load_from_environment()
            
            # Should keep as string if conversion fails
            assert config_manager.get_setting("test.invalid.float") == "not.a.float"
    
    def test_get_section_with_global_alias(self, config_manager):
        """Test getting section with global alias handling."""
        # Set a global section value
        config_manager.set_setting("global.test", "global_value")
        
        # Should be accessible via "global_" internal name
        section = config_manager.get_section("global")
        assert section is not None
        assert section.get("test") == "global_value"
    
    def test_create_default_config_existing_file(self, temp_dir):
        """Test creating default config when file already exists."""
        config_file = temp_dir / "existing.yaml"
        config_file.write_text("existing: content")
        
        config_manager = ConfigManager()
        created_path = config_manager.create_default_config(config_file)
        
        assert created_path == config_file
        # Should overwrite existing file
        with open(config_file, 'r') as f:
            content = f.read()
        assert "existing: content" not in content
        assert "version:" in content  # Default config content
    
    def test_config_property_with_invalid_data(self, config_manager):
        """Test config property when internal data is invalid."""
        # Corrupt internal config
        original_config = config_manager._config.copy()
        config_manager._config = {"invalid": "structure"}
        config_manager._pydantic_config = None
        
        # Should fallback to default config
        config = config_manager.config
        assert config is not None
        assert hasattr(config, "version")
        
        # Restore original
        config_manager._config = original_config
    
    def test_hierarchical_loading_with_missing_files(self, temp_dir):
        """Test hierarchical loading when some files are missing."""
        # Only create custom config
        custom_config = {"custom": {"only": "value"}}
        custom_file = temp_dir / "custom.yaml"
        with open(custom_file, 'w') as f:
            yaml.dump(custom_config, f)
        
        with patch.object(ConfigManager, 'get_system_config_path', return_value=temp_dir / "nonexistent_system.yaml"):
            with patch.object(ConfigManager, 'get_default_config_path', return_value=temp_dir / "nonexistent_user.yaml"):
                config_manager = ConfigManager(config_path=custom_file)
                config_manager.load_hierarchical()
                
                # Should still work with just the custom config
                assert config_manager.get_setting("custom.only") == "value"
                # Should have default values
                assert config_manager.get_setting("scrape.timeout") is not None
    
    def test_deep_merge_with_lists(self, config_manager):
        """Test deep merge behavior with lists."""
        config_manager.set_setting("test.list", ["original", "items"])
        
        new_config = {
            "test": {
                "list": ["new", "items"]
            }
        }
        config_manager.merge_config(new_config)
        
        # Lists should be replaced, not merged
        result = config_manager.get_setting("test.list")
        assert result == ["new", "items"]
    
    def test_config_path_expansion(self, temp_dir):
        """Test path expansion in configuration values."""
        import os
        
        # Create config with tilde paths
        config_data = {
            "storage": {
                "database_path": "~/test.db",
                "results_dir": "~/results"
            },
            "output": {
                "templates_dir": "~/templates"
            },
            "global": {
                "log_file": "~/logs/test.log"
            }
        }
        
        config_file = temp_dir / "path_test.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        config_manager = ConfigManager(config_path=config_file)
        config_manager.load_from_file()
        
        # Access config property to trigger path expansion
        config = config_manager.config
        
        # Paths should be expanded
        assert not config.storage.database_path.startswith("~")
        assert not config.storage.results_dir.startswith("~")
        assert not config.output.templates_dir.startswith("~")
        if config.global_.log_file:  # log_file can be None
            assert not config.global_.log_file.startswith("~")