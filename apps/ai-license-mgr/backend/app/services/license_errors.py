from __future__ import annotations


class CustomerNotFoundError(ValueError):
    """客户不存在。"""


class KeyPairNotFoundError(ValueError):
    """密钥对不存在。"""


class LicensePolicyNotFoundError(ValueError):
    """授权策略不存在。"""


class LicenseIssueNotFoundError(ValueError):
    """签发记录不存在。"""


class LicenseToolReleaseNotFoundError(ValueError):
    """工具发布记录不存在。"""
