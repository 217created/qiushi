"""配置系统测试"""

from qiushi.config import QiushiConfig


def test_default_config():
    """默认配置不报错"""
    config = QiushiConfig()
    assert config.llm.provider == "deepseek"
    assert config.llm.model == "deepseek-chat"


def test_config_roundtrip():
    """配置序列化/反序列化"""
    original = QiushiConfig()
    original.llm.provider = "openai"
    data = original.to_dict()
    restored = QiushiConfig._from_dict(data)
    assert restored.llm.provider == "openai"
